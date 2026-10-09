"""Durable database queue, shared by inline development worker and Celery workers."""

import asyncio
from datetime import timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.core.logging import get_logger
from app.db.engine import get_engine
from app.models.domain import Lead
from app.models.sales import EmailDraft, Followup, Job, Meeting, Message, WorkflowRun
from app.providers import calendar, email
from app.repositories.sales import SalesRepository
from app.schemas.sales import DraftInput
from app.services.sales import STOPPED, SalesService, now
from app.workflows.sales import generate

logger = get_logger(__name__)


def sessions():
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def process_workflow(identifier: UUID) -> None:
    async with sessions()() as db:
        service = SalesService(db)
        await service.repo.settings(lock=True)
        run = await service.repo.get(WorkflowRun, identifier, lock=True)
        if run.status in {"needs_review", "completed", "cancelled"}:
            return
        lead, campaign = await service.allowed(run.lead_id, run.campaign_id)
        prefs = await service.repo.settings()
        lead_data = {
            "name": " ".join(filter(None, [lead.first_name, lead.last_name]))
            or lead.email.split("@")[0],
            "email": lead.email,
            "company": lead.company.name,
            "domain": lead.company.domain,
            "industry": lead.company.industry,
            "title": lead.title,
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "website_research": lead.research if (lead.research or {}).get("evidence") else None,
        }
        campaign_data = {"offer": campaign.offer, "tone": campaign.tone}
        prefs_data = {"sender": prefs.sender, "company": prefs.company}
        checkpoint = dict(run.output)
        run.status = "running"
        run.error = None
        await db.commit()

    async def persist(stage: str, result: dict):
        async with sessions()() as db:
            repo = SalesRepository(db)
            run = await repo.get(WorkflowRun, identifier, lock=True)
            run.stage = stage
            run.output = {**run.output, stage: result}
            await db.commit()

    output = await asyncio.wait_for(
        generate(lead_data, campaign_data, prefs_data, checkpoint, persist),
        timeout=settings.JOB_LEASE_SECONDS - 30,
    )
    value = DraftInput(
        subject=output["draft"]["subject_line"],
        body=output["draft"]["email_body"],
        expected_revision=1,
    )
    async with sessions()() as db:
        service = SalesService(db)
        await service.repo.settings(lock=True)
        run = await service.repo.get(WorkflowRun, identifier, lock=True)
        lead, _ = await service.allowed(run.lead_id, run.campaign_id)
        if not await db.scalar(select(EmailDraft.id).where(EmailDraft.workflow_id == run.id)):
            confidence = min(
                float(output[k].get("confidence_score", 0))
                for k in ["enrichment", "research", "draft"]
            )
            confidence = max(0, min(1, confidence))
            draft = EmailDraft(
                lead_id=run.lead_id,
                campaign_id=run.campaign_id,
                workflow_id=run.id,
                subject=value.subject,
                body=value.body,
                status="needs_review",
                revision=1,
                confidence=confidence,
                requires_review=True,
            )
            db.add(draft)
            await db.flush()
            run.output = {
                **output,
                "draft_id": str(draft.id),
                "provider": settings.AI_PROVIDER,
                "research_verified": False,
            }
            lead.confidence = confidence
            lead.research = {
                **output["research"],
                "source": "Local test provider"
                if settings.AI_PROVIDER == "local"
                else "Unverified LLM inference",
            }
        run.status = "needs_review"
        run.stage = "human_review"
        service.activity("workflow_ready", run, "Research and draft saved for human review")
        await db.commit()


async def process_email(identifier: UUID, expected_revision: int | None = None) -> None:
    async with sessions()() as db:
        service = SalesService(db)
        await service.repo.settings(lock=True)
        draft = await service.repo.get(EmailDraft, identifier, lock=True)
        if expected_revision is not None and draft.revision != expected_revision:
            return
        if draft.status in {"sent", "cancelled", "delivery_unknown"}:
            return
        if draft.status == "sending" and settings.EMAIL_PROVIDER == "smtp":
            draft.status = "delivery_unknown"
            draft.failure = "Worker interrupted during SMTP delivery; reconcile before retrying"
            await db.commit()
            return
        if draft.status not in {"queued", "sending"} or draft.approved_revision != draft.revision:
            return
        try:
            lead, _ = await service.allowed(draft.lead_id, draft.campaign_id, active=True)
        except Exception:
            draft.status = "cancelled"
            draft.failure = "Contact or campaign is no longer eligible"
            await db.commit()
            return
        prefs = await service.repo.settings()
        draft.status = "sending"
        await db.commit()  # Persist ambiguity marker BEFORE the external SMTP operation.
        try:
            provider_id = await email.deliver(draft, lead, prefs.sender)
        except email.DeliveryUncertainError as exc:
            draft.status = "delivery_unknown"
            draft.failure = str(exc)
            await db.commit()
            return
        except Exception:
            # Known failures before DATA (or explicit SMTP rejection) are safe to re-approve.
            draft.status = "failed"
            draft.failure = "Delivery failed; check provider configuration before re-approving"
            draft.revision += 1
            draft.approved_revision = None
            await db.commit()
            return
        # Reacquire the workspace and contact locks after provider I/O.
        await service.repo.settings(lock=True)
        lead = await service.repo.get(Lead, draft.lead_id, lock=True)
        draft = await service.repo.get(EmailDraft, identifier, lock=True)
        draft.status = "sent"
        draft.sent_at = now()
        draft.provider_message_id = provider_id
        if lead.status == "new":
            lead.status = "contacted"
        db.add(
            Message(
                lead_id=lead.id,
                draft_id=draft.id,
                direction="outgoing",
                intent="outreach",
                subject=draft.subject,
                body=draft.body,
                status="sent",
            )
        )
        service.activity("email_sent", draft, "Email accepted by configured delivery provider")
        await db.commit()


async def process_calendar(identifier: UUID) -> None:
    async with sessions()() as db:
        service = SalesService(db)
        await service.repo.settings(lock=True)
        meeting = await service.repo.get(Meeting, identifier, lock=True)
        lead = await service.repo.get(Lead, meeting.lead_id)
        if meeting.sync_status == "synced":
            return
        try:
            result = await calendar.sync(meeting, lead)
        except Exception:
            meeting.sync_status = "failed"
            meeting.error = "Calendar sync failed; check credentials, availability and retry"
            await db.commit()
            raise
        meeting.provider_event_id = result["event_id"]
        meeting.join_url = result["join_url"]
        meeting.sync_status = "synced"
        meeting.error = None
        service.activity(
            "calendar_synced", meeting, "Meeting synchronized with configured calendar provider"
        )
        await db.commit()


async def due_followups() -> int:
    async with sessions()() as db:
        service = SalesService(db)
        await service.repo.settings(lock=True)
        due = (
            await db.scalars(
                select(Followup)
                .where(Followup.status == "scheduled", Followup.due_at <= now())
                .order_by(Followup.due_at)
                .limit(100)
                .with_for_update(skip_locked=True)
            )
        ).all()
        for f in due:
            lead = await service.repo.get(Lead, f.lead_id)
            if lead.status in STOPPED or lead.status in {"meeting_booked", "unresponsive"}:
                f.status = "cancelled"
                continue
            if await db.scalar(
                select(Message.id)
                .where(
                    Message.lead_id == lead.id,
                    Message.direction == "incoming",
                    Message.created_at > f.created_at,
                )
                .limit(1)
            ):
                f.status = "cancelled"
                continue
            try:
                _, campaign = await service.allowed(f.lead_id, f.campaign_id, active=True)
            except Exception:
                logger.info("followup_held", followup_id=str(f.id))
                continue  # Paused campaigns hold plans until eligible again.
            name = lead.first_name or "there"
            draft = EmailDraft(
                lead_id=lead.id,
                campaign_id=campaign.id,
                subject=f"Following up with {lead.company.name}",
                body=f"Hi {name},\n\nJust following up on our conversation. {campaign.offer}\n\nWould a short call be useful?",
                status="needs_review",
                revision=1,
                confidence=1,
                requires_review=False,
            )
            db.add(draft)
            await db.flush()
            f.draft_id = draft.id
            f.status = "ready_for_review"
            service.activity("followup_ready", f, "Due followup prepared for human approval")
        await db.commit()
        return len(due)


async def process_next() -> bool:
    factory = sessions()
    async with factory() as db:
        threshold = now() - timedelta(seconds=settings.JOB_LEASE_SECONDS)
        statement = (
            select(Job)
            .where(
                or_(
                    (Job.status == "queued") & (Job.available_at <= now()),
                    (Job.status == "processing") & (Job.locked_at < threshold),
                )
            )
            .order_by(Job.available_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = (await db.scalars(statement)).first()
        if not job:
            return False
        job.status = "processing"
        job.locked_at = now()
        job.attempts += 1
        identifier, kind, resource = job.id, job.kind, UUID(job.resource_id)
        expected_revision = int(job.dedupe_key.rsplit(":", 1)[1]) if kind == "email" else None
        await db.commit()
    try:
        if kind in {"discovery", "inspect"}:
            from app.services.discovery import discover, inspect_prospect

            await (discover(resource) if kind == "discovery" else inspect_prospect(resource))
        elif kind == "email":
            await process_email(resource, expected_revision)
        else:
            await {"workflow": process_workflow, "calendar": process_calendar}[kind](resource)
        async with factory() as db:
            job = await db.get(Job, identifier)
            job.status = "completed"
            job.error = None
            if kind == "email":
                draft = await db.get(EmailDraft, resource)
                if draft and draft.status in {"failed", "delivery_unknown"}:
                    job.status = "failed"
                    job.error = draft.failure
            job.locked_at = None
            await db.commit()
    except Exception as exc:
        logger.warning(
            "job_failed", job_id=str(identifier), kind=kind, error_type=type(exc).__name__
        )
        async with factory() as db:
            job = await db.get(Job, identifier)
            job.error = "Operation failed; check provider configuration and server logs"
            job.locked_at = None
            if job.attempts >= settings.WORKER_MAX_ATTEMPTS:
                job.status = "failed"
            else:
                job.status = "queued"
                job.available_at = now() + timedelta(seconds=2**job.attempts)
            if kind == "workflow":
                run = await db.get(WorkflowRun, resource)
                if run:
                    run.error = job.error
                    run.status = "failed" if job.status == "failed" else "queued"
            await db.commit()
    return True


async def drain(max_jobs: int = 100) -> int:
    await due_followups()
    count = 0
    while count < max_jobs and await process_next():
        count += 1
    return count


async def poll() -> None:
    while True:
        try:
            await drain(20)
        except Exception as exc:
            logger.warning("worker_poll_failed", error_type=type(exc).__name__)
        await asyncio.sleep(settings.WORKER_POLL_SECONDS)

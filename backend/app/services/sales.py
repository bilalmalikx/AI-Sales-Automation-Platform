"""Sales rules; routes only validate transport and call these transactional methods."""

import csv
import io
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, RateLimitException, ValidationException
from app.models.domain import Lead
from app.models.sales import (
    Activity,
    Campaign,
    CampaignLead,
    EmailDraft,
    Followup,
    Job,
    Meeting,
    Message,
    SuppressedEmail,
    WebhookEvent,
    WorkflowRun,
)
from app.repositories.sales import SalesRepository
from app.schemas.sales import CampaignResponse

STOPPED = {"unsubscribed", "lost", "won", "unresponsive"}


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SalesService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SalesRepository(session)

    def activity(self, action: str, obj, description: str) -> None:
        self.session.add(Activity(action=action, resource_id=str(obj.id), description=description))

    async def enqueue(self, kind: str, obj, key: str) -> Job:
        existing = await self.session.scalar(select(Job).where(Job.dedupe_key == key))
        if existing:
            return existing
        job = Job(kind=kind, resource_id=str(obj.id), dedupe_key=key, available_at=now())
        self.session.add(job)
        await self.session.flush()
        return job

    async def allowed(self, lead_id: UUID, campaign_id: UUID, active: bool = False):
        lead = await self.repo.get(Lead, lead_id, lock=True)
        campaign = await self.repo.get(Campaign, campaign_id, lock=True)
        if lead.status in STOPPED:
            raise ConflictException("Outreach is stopped for this contact")
        if active and campaign.status != "active":
            raise ConflictException("Activate the campaign before sending")
        membership = await self.session.get(CampaignLead, (campaign_id, lead_id))
        if not membership:
            raise ValidationException("Lead is not assigned to this campaign")
        return lead, campaign

    async def campaign_response(self, campaign) -> CampaignResponse:
        ids = list(
            (
                await self.session.scalars(
                    select(CampaignLead.lead_id).where(CampaignLead.campaign_id == campaign.id)
                )
            ).all()
        )
        sent = await self.session.scalar(
            select(func.count())
            .select_from(EmailDraft)
            .where(EmailDraft.campaign_id == campaign.id, EmailDraft.status == "sent")
        )
        replies = await self.session.scalar(
            select(func.count())
            .select_from(Message)
            .join(EmailDraft, Message.draft_id == EmailDraft.id)
            .where(EmailDraft.campaign_id == campaign.id, Message.direction == "incoming")
        )
        return CampaignResponse(
            **{
                k: getattr(campaign, k)
                for k in (
                    "id",
                    "name",
                    "audience",
                    "offer",
                    "tone",
                    "status",
                    "created_at",
                    "updated_at",
                )
            },
            lead_ids=ids,
            sent=sent,
            replies=replies,
        )

    async def save_campaign(self, value, identifier: UUID | None = None):
        await self.repo.settings(lock=True)
        ids = list(dict.fromkeys(value.lead_ids))
        for lead_id in ids:
            lead = await self.repo.get(Lead, lead_id)
            if lead.status == "unsubscribed":
                raise ConflictException("Unsubscribed contacts cannot join campaigns")
        campaign = (
            await self.repo.get(Campaign, identifier, lock=True)
            if identifier
            else Campaign(status="draft")
        )
        for key, val in value.model_dump(exclude={"lead_ids"}).items():
            setattr(campaign, key, val)
        self.session.add(campaign)
        await self.session.flush()
        await self.session.execute(
            delete(CampaignLead).where(CampaignLead.campaign_id == campaign.id)
        )
        self.session.add_all(
            [CampaignLead(campaign_id=campaign.id, lead_id=lead_record) for lead_record in ids]
        )
        self.activity("campaign_updated", campaign, "Campaign and audience saved")
        await self.session.commit()
        return await self.campaign_response(campaign)

    async def campaign_status(self, identifier: UUID, status: str):
        await self.repo.settings(lock=True)
        campaign = await self.repo.get(Campaign, identifier, lock=True)
        if status == "active" and not await self.session.scalar(
            select(CampaignLead.lead_id).where(CampaignLead.campaign_id == identifier).limit(1)
        ):
            raise ValidationException("Assign at least one lead before activating")
        campaign.status = status
        self.activity("campaign_status", campaign, f"Campaign {status}")
        await self.session.commit()
        return await self.campaign_response(campaign)

    async def start_workflow(self, value, key: str):
        await self.repo.settings(lock=True)
        existing = await self.session.scalar(
            select(WorkflowRun).where(WorkflowRun.idempotency_key == key)
        )
        if existing:
            if existing.lead_id != value.lead_id or existing.campaign_id != value.campaign_id:
                raise ConflictException("Idempotency key already belongs to another request")
            return existing
        await self.allowed(value.lead_id, value.campaign_id)
        run = WorkflowRun(
            lead_id=value.lead_id,
            campaign_id=value.campaign_id,
            idempotency_key=key,
            status="queued",
            stage="queued",
            output={},
        )
        self.session.add(run)
        await self.session.flush()
        await self.enqueue("workflow", run, f"workflow:{run.id}")
        self.activity("workflow_queued", run, "Research and draft workflow queued")
        await self.session.commit()
        return run

    async def edit_draft(self, identifier: UUID, value):
        await self.repo.settings(lock=True)
        draft = await self.repo.get(EmailDraft, identifier, lock=True)
        if draft.status not in {"needs_review", "approved", "failed", "cancelled"}:
            raise ConflictException("This draft can no longer be edited")
        if draft.revision != value.expected_revision:
            raise ConflictException("Draft changed; reload before editing")
        draft.subject, draft.body = value.subject, value.body
        draft.revision += 1
        draft.approved_revision = None
        draft.status = "needs_review"
        draft.failure = None
        self.activity("draft_updated", draft, "Draft changed; approval invalidated")
        await self.session.commit()
        return draft

    async def approve(self, identifier: UUID, value):
        await self.repo.settings(lock=True)
        draft = await self.repo.get(EmailDraft, identifier, lock=True)
        if draft.status not in {"needs_review", "approved", "failed", "cancelled"}:
            raise ConflictException("Draft cannot be approved in its current state")
        if draft.revision != value.expected_revision:
            raise ConflictException("Draft changed; reload before approving")
        if draft.requires_review and not value.acknowledge_low_confidence:
            raise ValidationException(
                "Explicit acknowledgement is required for low-confidence or unverified research"
            )
        if draft.status == "cancelled":
            draft.revision += 1  # A cancelled queue entry must never be reused.
        draft.approved_revision = draft.revision
        draft.status = "approved"
        self.activity("draft_approved", draft, "Human approved the current draft revision")
        await self.session.commit()
        return draft

    async def send(self, identifier: UUID):
        prefs = await self.repo.settings(lock=True)
        draft = await self.repo.get(EmailDraft, identifier, lock=True)
        if draft.status in {"queued", "sending", "sent"}:
            return draft
        if draft.status != "approved" or draft.approved_revision != draft.revision:
            raise ConflictException("Approve the current draft before sending")
        await self.allowed(draft.lead_id, draft.campaign_id, active=True)
        local = datetime.now(ZoneInfo(prefs.timezone))
        start = (
            local.replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(UTC)
            .replace(tzinfo=None)
        )
        end = (
            (local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
            .astimezone(UTC)
            .replace(tzinfo=None)
        )
        reserved = await self.session.scalar(
            select(func.count())
            .select_from(EmailDraft)
            .where(
                EmailDraft.queued_at >= start,
                EmailDraft.queued_at < end,
                EmailDraft.status.in_(["queued", "sending", "sent", "delivery_unknown"]),
            )
        )
        if reserved >= prefs.daily_limit:
            raise RateLimitException("Daily sending limit reached")
        draft.status, draft.queued_at = "queued", now()
        draft.failure = None
        await self.enqueue("email", draft, f"email:{draft.id}:{draft.revision}")
        self.activity("email_queued", draft, "Approved email queued for delivery")
        await self.session.commit()
        return draft

    async def unsubscribe(self, lead_id: UUID):
        await self.repo.settings(lock=True)
        lead = await self.repo.get(Lead, lead_id, lock=True)
        lead.status = "unsubscribed"
        if not await self.session.get(SuppressedEmail, lead.email.lower()):
            self.session.add(SuppressedEmail(email=lead.email.lower(), reason="unsubscribed"))
        for followup in (
            await self.session.scalars(
                select(Followup).where(Followup.lead_id == lead_id, Followup.status == "scheduled")
            )
        ).all():
            followup.status = "cancelled"
        for draft in (
            await self.session.scalars(
                select(EmailDraft).where(
                    EmailDraft.lead_id == lead_id, EmailDraft.status == "queued"
                )
            )
        ).all():
            draft.status = "cancelled"
        self.activity(
            "lead_unsubscribed", lead, "Outreach stopped and scheduled followups cancelled"
        )
        await self.session.commit()
        return {"status": "unsubscribed", "lead_id": str(lead_id)}

    async def reply(self, lead_id: UUID, value):
        await self.repo.settings(lock=True)
        lead = await self.repo.get(Lead, lead_id, lock=True)
        if lead.status in STOPPED:
            raise ConflictException("Outreach is stopped for this contact")
        campaign = await self.session.scalar(
            select(Campaign)
            .join(CampaignLead)
            .where(CampaignLead.lead_id == lead_id, Campaign.status == "active")
            .order_by(Campaign.created_at.desc())
            .limit(1)
        )
        if not campaign:
            raise ConflictException("An active campaign is required")
        draft = EmailDraft(
            lead_id=lead_id,
            campaign_id=campaign.id,
            subject=value.subject,
            body=value.body,
            status="approved",
            confidence=1,
            requires_review=False,
            revision=1,
            approved_revision=1,
        )
        self.session.add(draft)
        await self.session.flush()
        # A manual reply is explicitly authored by the operator; the send action remains separate.
        self.activity("reply_drafted", draft, "Manual reply saved; delivery requires send action")
        await self.session.commit()
        return draft

    async def book(self, value, identifier: UUID | None = None):
        await self.repo.settings(lock=True)  # Serialize overlapping reservations across leads.
        lead = await self.repo.get(Lead, value.lead_id, lock=True)
        if lead.status in STOPPED:
            raise ConflictException("Cannot book a stopped contact")
        if value.start_at <= now():
            raise ValidationException("Meeting must be in the future")
        end = value.start_at + timedelta(minutes=value.duration_minutes)
        conditions = [
            Meeting.status == "scheduled",
            Meeting.start_at < end,
            Meeting.end_at > value.start_at,
        ]
        if identifier:
            conditions.append(Meeting.id != identifier)
        if await self.session.scalar(select(Meeting.id).where(*conditions).limit(1)):
            raise ConflictException("Meeting time overlaps another booking")
        meeting = (
            await self.repo.get(Meeting, identifier, lock=True)
            if identifier
            else Meeting(revision=0)
        )
        if identifier and meeting.status == "cancelled":
            raise ConflictException("Cancelled meetings cannot be rescheduled")
        meeting.lead_id, meeting.title = value.lead_id, value.title
        meeting.start_at, meeting.end_at, meeting.timezone = value.start_at, end, value.timezone
        meeting.status, meeting.sync_status = "scheduled", "pending"
        meeting.revision += 1
        self.session.add(meeting)
        await self.session.flush()
        lead.status = "meeting_booked"
        for f in (
            await self.session.scalars(
                select(Followup).where(Followup.lead_id == lead.id, Followup.status == "scheduled")
            )
        ).all():
            f.status = "cancelled"
        await self.enqueue("calendar", meeting, f"calendar:{meeting.id}:{meeting.revision}")
        self.activity("meeting_booked", meeting, "Meeting reservation saved; calendar sync queued")
        await self.session.commit()
        return meeting

    async def cancel_meeting(self, identifier: UUID):
        await self.repo.settings(lock=True)
        meeting = await self.repo.get(Meeting, identifier, lock=True)
        if meeting.status == "cancelled":
            return meeting
        meeting.status, meeting.sync_status = "cancelled", "pending"
        meeting.revision += 1
        await self.enqueue("calendar", meeting, f"calendar:{meeting.id}:{meeting.revision}")
        lead = await self.repo.get(Lead, meeting.lead_id, lock=True)
        if lead.status == "meeting_booked" and not await self.session.scalar(
            select(Meeting.id)
            .where(
                Meeting.lead_id == lead.id, Meeting.status == "scheduled", Meeting.id != identifier
            )
            .limit(1)
        ):
            lead.status = "qualified"
        self.activity("meeting_cancelled", meeting, "Meeting cancellation queued for calendar")
        await self.session.commit()
        return meeting

    async def schedule(self, value):
        await self.repo.settings(lock=True)
        lead, campaign = await self.allowed(value.lead_id, value.campaign_id)
        if lead.status in {"meeting_booked", "new"}:
            raise ConflictException("Followups require a contacted lead without a booked meeting")
        if value.due_at <= now():
            raise ValidationException("Followup must be in the future")
        for f in (
            await self.session.scalars(
                select(Followup).where(Followup.lead_id == lead.id, Followup.status == "scheduled")
            )
        ).all():
            f.status = "cancelled"
        followup = Followup(
            lead_id=lead.id, campaign_id=campaign.id, due_at=value.due_at, status="scheduled"
        )
        self.session.add(followup)
        await self.session.flush()
        self.activity(
            "followup_scheduled",
            followup,
            "Followup scheduled; due drafts still require human approval",
        )
        await self.session.commit()
        return followup

    async def cancel_followup(self, identifier: UUID):
        await self.repo.settings(lock=True)
        followup = await self.repo.get(Followup, identifier, lock=True)
        if followup.status == "scheduled":
            followup.status = "cancelled"
        await self.session.commit()
        return followup

    async def webhook(self, value):
        await self.repo.settings(lock=True)
        existing = await self.session.scalar(
            select(WebhookEvent).where(WebhookEvent.event_id == value.event_id)
        )
        if existing:
            if existing.kind != value.kind or existing.draft_id != value.draft_id:
                raise ConflictException("Event ID was already used with a different payload")
            return {"status": "duplicate"}
        draft = await self.repo.get(EmailDraft, value.draft_id, lock=True)
        lead = await self.repo.get(Lead, draft.lead_id, lock=True)
        if value.kind == "replied" and not value.body:
            raise ValidationException("Incoming reply requires a body")
        self.session.add(WebhookEvent(event_id=value.event_id, kind=value.kind, draft_id=draft.id))
        if value.kind == "delivered":
            draft.delivered_at = now()
        elif value.kind == "opened":
            draft.opened_at = draft.opened_at or now()
        elif value.kind == "bounced":
            draft.failure = "Recipient bounced"
            if lead.status != "unsubscribed":
                lead.status = "unresponsive"
        elif value.kind == "replied":
            self.session.add(
                Message(
                    lead_id=lead.id,
                    draft_id=draft.id,
                    direction="incoming",
                    intent=value.intent,
                    subject=draft.subject,
                    body=value.body,
                    status="received",
                )
            )
            if lead.status not in STOPPED and lead.status != "meeting_booked":
                lead.status = "replied"
        if value.kind == "unsubscribed" or (
            value.kind == "replied" and value.intent == "unsubscribe"
        ):
            return await self.unsubscribe(lead.id)
        if value.kind in {"replied", "bounced"}:
            for f in (
                await self.session.scalars(
                    select(Followup).where(
                        Followup.lead_id == lead.id, Followup.status == "scheduled"
                    )
                )
            ).all():
                f.status = "cancelled"
        self.activity("email_" + value.kind, draft, "Email provider event received")
        await self.session.commit()
        return {"status": "processed"}

    async def analytics(self) -> dict:
        async def count(model, *conditions):
            return await self.session.scalar(
                select(func.count()).select_from(model).where(*conditions)
            )

        campaigns = (
            await self.session.scalars(select(Campaign).order_by(Campaign.created_at))
        ).all()
        stages = (
            await self.session.execute(select(Lead.status, func.count()).group_by(Lead.status))
        ).all()
        return {
            "leads": await count(Lead),
            "active_campaigns": await count(Campaign, Campaign.status == "active"),
            "emails_sent": await count(EmailDraft, EmailDraft.status == "sent"),
            "replies": await count(Message, Message.direction == "incoming"),
            "meetings": await count(Meeting, Meeting.status == "scheduled"),
            "drafts": await count(EmailDraft),
            "pending_jobs": await count(Job, Job.status.in_(["queued", "processing"])),
            "pipeline": dict(stages),
            "campaigns": [
                (await self.campaign_response(c)).model_dump(mode="json") for c in campaigns
            ],
        }

    async def export_leads(self) -> str:
        rows = (await self.session.scalars(select(Lead).order_by(Lead.created_at))).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "name", "email", "company", "title", "industry", "status"])

        def safe(value):
            text = str(value or "")
            return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text

        for lead in rows:
            writer.writerow(
                [
                    safe(v)
                    for v in [
                        lead.id,
                        " ".join(filter(None, [lead.first_name, lead.last_name])),
                        lead.email,
                        lead.company.name,
                        lead.title,
                        lead.company.industry,
                        lead.status,
                    ]
                ]
            )
        return output.getvalue()

    async def reconcile_delivery(self, identifier: UUID, value):
        await self.repo.settings(lock=True)
        draft = await self.repo.get(EmailDraft, identifier, lock=True)
        if draft.status != "delivery_unknown":
            raise ConflictException("Only uncertain SMTP deliveries can be reconciled")
        if value.action == "confirmed_sent":
            draft.status, draft.sent_at = "sent", now()
            if not await self.session.scalar(
                select(Message.id)
                .where(Message.draft_id == draft.id, Message.direction == "outgoing")
                .limit(1)
            ):
                self.session.add(
                    Message(
                        lead_id=draft.lead_id,
                        draft_id=draft.id,
                        direction="outgoing",
                        intent="outreach",
                        subject=draft.subject,
                        body=draft.body,
                        status="sent",
                    )
                )
            lead = await self.repo.get(Lead, draft.lead_id, lock=True)
            if lead.status == "new":
                lead.status = "contacted"
        else:
            if not value.acknowledge_duplicate_risk:
                raise ValidationException(
                    "Explicit acknowledgement of possible duplicate delivery is required"
                )
            draft.revision += 1
            draft.approved_revision = None
            draft.status = "needs_review"
        draft.failure = None
        self.activity("delivery_reconciled", draft, "Operator reconciled uncertain SMTP delivery")
        await self.session.commit()
        return draft

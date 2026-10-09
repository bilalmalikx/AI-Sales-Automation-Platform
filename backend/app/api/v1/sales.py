"""Authenticated sales API. Business operations live in services, not routes."""

import json
from html import escape
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictException, ValidationException
from app.core.security import require_auth, verify_token, verify_webhook
from app.db.session import get_db
from app.models.domain import Company, Lead
from app.models.sales import (
    Activity,
    Campaign,
    EmailDraft,
    Followup,
    Job,
    Meeting,
    Message,
    WorkflowRun,
)
from app.repositories.sales import SalesRepository
from app.schemas.sales import (
    ActivityResponse,
    Approval,
    CampaignInput,
    CampaignResponse,
    CampaignStatus,
    DraftInput,
    DraftResponse,
    FollowupInput,
    FollowupResponse,
    JobResponse,
    MeetingInput,
    MeetingResponse,
    MessageResponse,
    Page,
    Preferences,
    Reconciliation,
    ReplyInput,
    WebhookInput,
    WorkflowInput,
    WorkflowResponse,
)
from app.services.sales import SalesService

router = APIRouter(dependencies=[Depends(require_auth)])
public = APIRouter(tags=["Public links and webhooks"])
DB = Annotated[AsyncSession, Depends(get_db)]
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get("/campaigns", response_model=Page[CampaignResponse], tags=["Campaigns"])
async def campaigns(db: DB, page: PageNumber = 1, page_size: PageSize = 50):
    service = SalesService(db)
    result = await service.repo.page(Campaign, CampaignResponse, page, page_size)
    result.items = [
        await service.campaign_response(await service.repo.get(Campaign, c.id))
        for c in result.items
    ]
    return result


@router.post("/campaigns", response_model=CampaignResponse, status_code=201, tags=["Campaigns"])
async def create_campaign(value: CampaignInput, db: DB):
    return await SalesService(db).save_campaign(value)


@router.get("/campaigns/{identifier}", response_model=CampaignResponse, tags=["Campaigns"])
async def get_campaign(identifier: UUID, db: DB):
    service = SalesService(db)
    return await service.campaign_response(await service.repo.get(Campaign, identifier))


@router.put("/campaigns/{identifier}", response_model=CampaignResponse, tags=["Campaigns"])
async def update_campaign(identifier: UUID, value: CampaignInput, db: DB):
    return await SalesService(db).save_campaign(value, identifier)


@router.patch("/campaigns/{identifier}/status", response_model=CampaignResponse, tags=["Campaigns"])
async def campaign_status(identifier: UUID, value: CampaignStatus, db: DB):
    return await SalesService(db).campaign_status(identifier, value.status)


@router.post("/workflows", response_model=WorkflowResponse, status_code=202, tags=["AI workflow"])
async def start_workflow(
    value: WorkflowInput,
    db: DB,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=100)],
):
    return await SalesService(db).start_workflow(value, idempotency_key)


@router.get("/workflows", response_model=Page[WorkflowResponse], tags=["AI workflow"])
async def workflows(db: DB, page: PageNumber = 1, page_size: PageSize = 50):
    return await SalesRepository(db).page(WorkflowRun, WorkflowResponse, page, page_size)


@router.get("/workflows/{identifier}", response_model=WorkflowResponse, tags=["AI workflow"])
async def workflow(identifier: UUID, db: DB):
    return await SalesRepository(db).get(WorkflowRun, identifier)


@router.get("/emails", response_model=Page[DraftResponse], tags=["Email review"])
async def emails(db: DB, page: PageNumber = 1, page_size: PageSize = 50, status: str | None = None):
    return await SalesRepository(db).page(
        EmailDraft, DraftResponse, page, page_size, [EmailDraft.status == status] if status else []
    )


@router.get("/emails/{identifier}", response_model=DraftResponse, tags=["Email review"])
async def email(identifier: UUID, db: DB):
    return await SalesRepository(db).get(EmailDraft, identifier)


@router.put("/emails/{identifier}", response_model=DraftResponse, tags=["Email review"])
async def edit_email(identifier: UUID, value: DraftInput, db: DB):
    return await SalesService(db).edit_draft(identifier, value)


@router.post("/emails/{identifier}/approve", response_model=DraftResponse, tags=["Email review"])
async def approve(identifier: UUID, value: Approval, db: DB):
    return await SalesService(db).approve(identifier, value)


@router.post(
    "/emails/{identifier}/send",
    response_model=DraftResponse,
    status_code=202,
    tags=["Email review"],
)
async def send(identifier: UUID, db: DB):
    return await SalesService(db).send(identifier)


@router.get("/inbox", response_model=Page[MessageResponse], tags=["Inbox"])
async def inbox(
    db: DB, page: PageNumber = 1, page_size: PageSize = 50, lead_id: UUID | None = None
):
    return await SalesRepository(db).page(
        Message, MessageResponse, page, page_size, [Message.lead_id == lead_id] if lead_id else []
    )


@router.post(
    "/inbox/{lead_id}/reply", response_model=DraftResponse, status_code=201, tags=["Inbox"]
)
async def reply(lead_id: UUID, value: ReplyInput, db: DB):
    return await SalesService(db).reply(lead_id, value)


@router.post("/inbox/{lead_id}/suggest", tags=["Inbox"])
async def suggest(lead_id: UUID, db: DB):
    repo = SalesRepository(db)
    lead = await repo.get(Lead, lead_id)
    prefs = await repo.settings()
    return {
        "body": f"Hi {lead.first_name or 'there'},\n\nThanks for your reply. I would be happy to walk through the workflow. What time works well for you?\n\nBest,\n{prefs.sender}",
        "source": "template",
    }


@router.post("/leads/{lead_id}/unsubscribe", tags=["Leads"])
async def unsubscribe(lead_id: UUID, db: DB):
    return await SalesService(db).unsubscribe(lead_id)


@router.get("/leads/export/csv", tags=["Leads"])
async def export_leads(db: DB):
    return PlainTextResponse(
        await SalesService(db).export_leads(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=salesway-leads.csv"},
    )


@router.get("/meetings", response_model=Page[MeetingResponse], tags=["Meetings"])
async def meetings(db: DB, page: PageNumber = 1, page_size: PageSize = 50):
    return await SalesRepository(db).page(Meeting, MeetingResponse, page, page_size)


@router.get("/meetings/{identifier}", response_model=MeetingResponse, tags=["Meetings"])
async def get_meeting(identifier: UUID, db: DB):
    return await SalesRepository(db).get(Meeting, identifier)


@router.post("/meetings", response_model=MeetingResponse, status_code=201, tags=["Meetings"])
async def book(value: MeetingInput, db: DB):
    return await SalesService(db).book(value)


@router.put("/meetings/{identifier}", response_model=MeetingResponse, tags=["Meetings"])
async def reschedule(identifier: UUID, value: MeetingInput, db: DB):
    return await SalesService(db).book(value, identifier)


@router.post("/meetings/{identifier}/cancel", response_model=MeetingResponse, tags=["Meetings"])
async def cancel_meeting(identifier: UUID, db: DB):
    return await SalesService(db).cancel_meeting(identifier)


@router.get("/followups", response_model=Page[FollowupResponse], tags=["Followups"])
async def followups(db: DB, page: PageNumber = 1, page_size: PageSize = 50):
    return await SalesRepository(db).page(Followup, FollowupResponse, page, page_size)


@router.get("/followups/{identifier}", response_model=FollowupResponse, tags=["Followups"])
async def get_followup(identifier: UUID, db: DB):
    return await SalesRepository(db).get(Followup, identifier)


@router.post("/followups", response_model=FollowupResponse, status_code=201, tags=["Followups"])
async def followup(value: FollowupInput, db: DB):
    return await SalesService(db).schedule(value)


@router.post("/followups/{identifier}/cancel", response_model=FollowupResponse, tags=["Followups"])
async def cancel_followup(identifier: UUID, db: DB):
    return await SalesService(db).cancel_followup(identifier)


@router.get("/settings", response_model=Preferences, tags=["Workspace"])
async def preferences(db: DB):
    p = await SalesRepository(db).settings()
    return Preferences(**{k: getattr(p, k) for k in Preferences.model_fields})


@router.put("/settings", response_model=Preferences, tags=["Workspace"])
async def save_preferences(value: Preferences, db: DB):
    p = await SalesRepository(db).settings(lock=True)
    for key, val in value.model_dump().items():
        setattr(p, key, val)
    await db.commit()
    return value


@router.get("/analytics", tags=["Analytics"])
async def analytics(db: DB):
    return await SalesService(db).analytics()


@router.get("/analytics/export", tags=["Analytics"])
async def export_report(db: DB):
    return Response(
        json.dumps(await SalesService(db).analytics()),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=salesway-report.json"},
    )


@router.get("/activity", response_model=Page[ActivityResponse], tags=["Workspace"])
async def activity(db: DB, page: PageNumber = 1, page_size: PageSize = 50):
    return await SalesRepository(db).page(Activity, ActivityResponse, page, page_size)


@router.get("/pipeline", tags=["Workspace"])
async def pipeline(db: DB):
    return (await SalesService(db).analytics())["pipeline"]


@router.get("/search", tags=["Workspace"])
async def search(db: DB, q: Annotated[str, Query(min_length=1, max_length=200)]):
    from sqlalchemy import or_

    from app.services.lead import LeadService

    query = (
        select(Lead)
        .join(Lead.company)
        .where(
            or_(
                Lead.email.ilike(f"%{q}%"),
                Lead.first_name.ilike(f"%{q}%"),
                Lead.last_name.ilike(f"%{q}%"),
                Company.name.ilike(f"%{q}%"),
            )
        )
        .limit(20)
    )
    return {
        "leads": [
            LeadService(db).response(lead_record) for lead_record in (await db.scalars(query)).all()
        ]
    }


@router.get("/notifications", tags=["Workspace"])
async def notifications(db: DB):
    data = await SalesService(db).analytics()
    drafts = await db.scalar(
        select(func.count()).select_from(EmailDraft).where(EmailDraft.status == "needs_review")
    )
    return {
        "replies": data["replies"],
        "drafts_to_review": drafts,
        "pending_jobs": data["pending_jobs"],
    }


@router.get("/integrations", tags=["Workspace"])
async def integrations():
    return {
        "ai": {
            "provider": settings.AI_PROVIDER,
            "configured": settings.AI_PROVIDER == "local" or bool(settings.OPENAI_API_KEY),
        },
        "email": {
            "provider": settings.EMAIL_PROVIDER,
            "configured": settings.EMAIL_PROVIDER == "local"
            or bool(settings.SMTP_HOST and settings.DEFAULT_FROM_EMAIL),
        },
        "calendar": {
            "provider": settings.CALENDAR_PROVIDER,
            "configured": settings.CALENDAR_PROVIDER == "local"
            or bool(settings.GOOGLE_REFRESH_TOKEN),
        },
        "live_delivery_enabled": settings.LIVE_DELIVERY_ENABLED,
        "worker_mode": settings.WORKER_MODE,
    }


@router.get("/jobs", response_model=Page[JobResponse], tags=["Operations"])
async def jobs(db: DB, page: PageNumber = 1, page_size: PageSize = 50):
    return await SalesRepository(db).page(Job, JobResponse, page, page_size)


@router.post("/jobs/{identifier}/retry", response_model=JobResponse, tags=["Operations"])
async def retry_job(identifier: UUID, db: DB):
    from app.services.sales import now

    repo = SalesRepository(db)
    await repo.settings(lock=True)
    job = await repo.get(Job, identifier, lock=True)
    if job.status != "failed" or job.kind == "email":
        raise ConflictException(
            "Only failed workflow/calendar jobs can be retried; email needs renewed approval"
        )
    job.status = "queued"
    job.attempts = 0
    job.available_at = now()
    job.error = None
    await db.commit()
    return job


@public.post("/webhooks/email")
async def email_webhook(
    request: Request,
    db: DB,
    x_webhook_timestamp: Annotated[str, Header()],
    x_webhook_signature: Annotated[str, Header()],
):
    body = await request.body()
    if len(body) > 100000:
        raise ValidationException("Webhook payload too large")
    verify_webhook(body, x_webhook_timestamp, x_webhook_signature)
    try:
        value = WebhookInput.model_validate_json(body)
    except ValueError as exc:
        raise ValidationException("Invalid webhook payload") from exc
    return await SalesService(db).webhook(value)


@public.get("/public/unsubscribe/{lead_id}", response_class=HTMLResponse)
async def unsubscribe_info(lead_id: UUID, token: str):
    verify_token(lead_id, "unsubscribe", token)
    action = (
        f"{settings.API_V1_PREFIX}/public/unsubscribe/{lead_id}?token={escape(token, quote=True)}"
    )
    return HTMLResponse(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Stop outreach</title><main><h1>Stop outreach</h1>"
        "<p>Confirm to stop email outreach to this contact.</p>"
        f'<form method="post" action="{action}"><button type="submit">Unsubscribe</button></form>'
        "</main></html>",
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@public.post("/public/unsubscribe/{lead_id}")
async def public_unsubscribe(lead_id: UUID, token: str, db: DB):
    verify_token(lead_id, "unsubscribe", token)
    return await SalesService(db).unsubscribe(lead_id)


@router.post("/emails/{identifier}/reconcile", response_model=DraftResponse, tags=["Email review"])
async def reconcile(identifier: UUID, value: Reconciliation, db: DB):
    return await SalesService(db).reconcile_delivery(identifier, value)

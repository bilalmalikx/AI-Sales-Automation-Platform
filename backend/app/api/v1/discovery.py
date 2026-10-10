from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, Header

from app.api.v1.sales import DB, PageNumber, PageSize
from app.core.config import settings
from app.core.security import require_auth
from app.models.discovery import DiscoveryRun, Prospect
from app.repositories.sales import SalesRepository
from app.schemas.discovery import (
    DiscoveryInput,
    DiscoveryResponse,
    ProspectOutreachInput,
    ProspectResponse,
)
from app.schemas.sales import Page, WorkflowResponse
from app.services import discovery

router = APIRouter(
    prefix="/discovery", tags=["Business discovery"], dependencies=[Depends(require_auth)]
)


@router.post("/runs", response_model=DiscoveryResponse, status_code=202)
async def start(
    value: DiscoveryInput,
    db: DB,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=100)],
):
    return await discovery.start(db, value, idempotency_key)


@router.get("/runs", response_model=Page[DiscoveryResponse])
async def runs(db: DB, page: PageNumber = 1, page_size: PageSize = 50):
    return await SalesRepository(db).page(DiscoveryRun, DiscoveryResponse, page, page_size)


@router.get("/runs/{identifier}", response_model=DiscoveryResponse)
async def run(identifier: UUID, db: DB):
    return await SalesRepository(db).get(DiscoveryRun, identifier)


@router.get("/prospects", response_model=Page[ProspectResponse])
async def prospects(
    db: DB,
    page: PageNumber = 1,
    page_size: PageSize = 50,
    run_id: UUID | None = None,
    contact_only: bool = False,
):
    conditions = [Prospect.run_id == run_id] if run_id else []
    if contact_only:
        conditions.append(Prospect.contact_available.is_(True))
        conditions.append(Prospect.status.not_in(["excluded", "cancelled"]))
    return await SalesRepository(db).page(Prospect, ProspectResponse, page, page_size, conditions)


@router.get("/prospects/{identifier}", response_model=ProspectResponse)
async def prospect(identifier: UUID, db: DB):
    return await SalesRepository(db).get(Prospect, identifier)


@router.post("/runs/{identifier}/cancel", response_model=DiscoveryResponse)
async def cancel(identifier: UUID, db: DB):
    repo = SalesRepository(db)
    await repo.settings(lock=True)
    r = await repo.get(DiscoveryRun, identifier, lock=True)
    r.status = "cancelled"
    await db.commit()
    return r


@router.get("/configuration")
async def configuration():
    return {
        "apify_configured": bool(settings.APIFY_API_TOKEN),
        "dataset_configured": bool(settings.APIFY_DATASET_ID),
        "daily_limit": settings.DISCOVERY_DAILY_LIMIT,
        "run_budget_usd": settings.DISCOVERY_RUN_BUDGET_USD,
        "ai_provider": settings.AI_PROVIDER,
        "ai_configured": bool(settings.OPENAI_API_KEY),
        "ai_endpoint": urlsplit(settings.LLM_BASE_URL).hostname,
        "ai_model": settings.OPENAI_MODEL,
        "ai_calls_per_run": settings.DISCOVERY_AI_MAX_CALLS,
    }


@router.post("/prospects/{identifier}/retry", response_model=ProspectResponse)
async def retry(identifier: UUID, db: DB):
    from uuid import uuid4

    from app.core.exceptions import ConflictException
    from app.services.sales import SalesService

    repo = SalesRepository(db)
    await repo.settings(lock=True)
    p = await repo.get(Prospect, identifier, lock=True)
    if p.status != "inspection_failed":
        raise ConflictException("Only failed inspections can be retried")
    r = await repo.get(DiscoveryRun, p.run_id, lock=True)
    if r.status == "cancelled":
        raise ConflictException("This discovery run was cancelled")
    if not p.evidence.get("website", {}).get("pages"):
        p.evidence = {
            key: value for key, value in p.evidence.items() if key not in {"website", "app"}
        }
        p.analysis = {}
        p.emails = []
        p.contact_available = False
        p.app_status = "not_checked"
    p.status = "queued"
    p.stage = "website_inspection"
    p.reason = None
    r.status = "inspecting"
    r.stage = "website_inspection"
    r.processed = max(0, r.processed - 1)
    await SalesService(db).enqueue("inspect", p, f"inspect:{p.id}:{uuid4()}")
    await db.commit()
    return p


@router.post(
    "/prospects/{identifier}/prepare-outreach", response_model=WorkflowResponse, status_code=202
)
async def prepare_outreach(
    identifier: UUID,
    value: ProspectOutreachInput,
    db: DB,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=100)],
):
    return await discovery.prepare_outreach(db, identifier, value.campaign_id, idempotency_key)

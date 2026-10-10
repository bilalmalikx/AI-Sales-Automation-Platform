from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.sales import Input, Record


class DiscoveryInput(Input):
    industry: str = Field(default="car wash", min_length=2, max_length=100)
    location: str = Field(default="London", min_length=2, max_length=200)
    country: Literal["GB", "US"] = "GB"
    limit: int = Field(default=10, ge=1, le=100)
    mode: Literal["fresh", "dataset"] = "fresh"
    generate_drafts: bool = True


class DiscoveryResponse(Record):
    parameters: dict
    status: str
    stage: str
    total: int
    processed: int
    ai_calls: int
    provider_run_id: str | None
    dataset_id: str | None
    provider_cost: float
    error: str | None


class ProspectResponse(Record):
    run_id: UUID
    company: str
    website: str | None
    country: str
    city: str
    phone: str
    status: str
    stage: str
    contact_available: bool
    emails: list
    app_status: str
    score: int
    evidence: dict
    analysis: dict
    reason: str | None
    lead_id: UUID | None
    campaign_id: UUID | None


class ProspectOutreachInput(Input):
    campaign_id: UUID
    reviewed_contact: Literal[True]

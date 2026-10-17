from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, computed_field

from app.schemas.sales import Input, Record, TimeInput


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
    budget_reserved_usd: float


class DiscoveryScheduleInput(TimeInput):
    name: str = Field(min_length=1, max_length=200)
    parameters: DiscoveryInput
    enabled: bool = False
    due_at: datetime


class DiscoveryScheduleResponse(Record):
    name: str
    parameters: dict
    enabled: bool
    due_at: datetime
    last_run_id: UUID | None
    last_checked_at: datetime | None
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

    @computed_field
    @property
    def retryable(self) -> bool:
        from app.services.inspection_quality import retry_advice

        attempts = self.evidence.get("inspection", {}).get("attempts", 0)
        return self.status == "inspection_failed" and attempts < 3 and retry_advice(self.reason)[0]

    @computed_field
    @property
    def next_action(self) -> str:
        from app.services.inspection_quality import retry_advice

        if self.status != "inspection_failed":
            return ""
        if self.evidence.get("inspection", {}).get("attempts", 0) >= 3:
            return "Retry limit reached. Review the website and contact evidence manually."
        return retry_advice(self.reason)[1]


class ProspectOutreachInput(Input):
    campaign_id: UUID
    reviewed_contact: Literal[True]

"""Validated requests and typed API responses for the complete sales workspace."""

from datetime import UTC, datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

T = TypeVar("T")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Record(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    updated_at: datetime

    @field_serializer("*", check_fields=False)
    def utc_dates(self, value):
        if isinstance(value, datetime):
            return value.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
        return value


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class CampaignInput(Input):
    name: str = Field(min_length=1, max_length=200)
    audience: str = Field(min_length=1, max_length=500)
    offer: str = Field(min_length=1, max_length=10000)
    tone: Literal["friendly", "professional", "casual"] = "friendly"
    lead_ids: list[UUID] = Field(default_factory=list, max_length=1000)


class CampaignResponse(Record):
    name: str
    audience: str
    offer: str
    tone: str
    status: str
    lead_ids: list[UUID] = []
    sent: int = 0
    replies: int = 0


class CampaignStatus(Input):
    status: Literal["active", "paused", "draft"]


class WorkflowInput(Input):
    lead_id: UUID
    campaign_id: UUID


class WorkflowResponse(Record):
    lead_id: UUID
    campaign_id: UUID
    status: str
    stage: str
    output: dict
    error: str | None


class DraftInput(Input):
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=20000)
    expected_revision: int = Field(ge=1)

    @field_validator("subject")
    @classmethod
    def subject_header(cls, value: str) -> str:
        if "\r" in value or "\n" in value:
            raise ValueError("Subject must be a single line")
        return value


class Approval(Input):
    expected_revision: int = Field(ge=1)
    acknowledge_low_confidence: bool = False


class DraftResponse(Record):
    lead_id: UUID
    campaign_id: UUID
    workflow_id: UUID | None
    subject: str
    body: str
    status: str
    revision: int
    approved_revision: int | None
    confidence: float
    requires_review: bool
    sent_at: datetime | None
    provider_message_id: str | None
    failure: str | None
    delivered_at: datetime | None
    opened_at: datetime | None


class ReplyInput(Input):
    body: str = Field(min_length=1, max_length=20000)
    subject: str = Field(default="Re: Your conversation", max_length=300)

    @field_validator("subject")
    @classmethod
    def safe_subject(cls, value: str) -> str:
        return DraftInput.subject_header(value)


class MessageResponse(Record):
    lead_id: UUID
    draft_id: UUID | None
    direction: str
    intent: str
    subject: str
    body: str
    status: str


class TimeInput(Input):
    @field_validator("start_at", "due_at", check_fields=False)
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Supply an ISO timestamp with an explicit timezone offset")
        return value.astimezone(UTC).replace(tzinfo=None)


class MeetingInput(TimeInput):
    lead_id: UUID
    title: str = Field(default="Discovery call", min_length=1, max_length=300)
    start_at: datetime
    duration_minutes: int = Field(default=30, ge=15, le=120)
    timezone: str = "Asia/Karachi"

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA timezone") from exc
        return value


class MeetingResponse(Record):
    lead_id: UUID
    title: str
    start_at: datetime
    end_at: datetime
    timezone: str
    status: str
    sync_status: str
    revision: int
    provider_event_id: str | None
    join_url: str | None
    error: str | None


class FollowupInput(TimeInput):
    lead_id: UUID
    campaign_id: UUID
    due_at: datetime


class FollowupResponse(Record):
    lead_id: UUID
    campaign_id: UUID
    due_at: datetime
    status: str
    draft_id: UUID | None


class Preferences(Input):
    company: str = Field(min_length=1, max_length=200)
    sender: str = Field(min_length=1, max_length=200)
    offer: str = Field(min_length=1, max_length=10000)
    timezone: str = "Asia/Karachi"
    daily_limit: int = Field(default=50, ge=1, le=500)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        return MeetingInput.valid_timezone(value)


class WebhookInput(Input):
    event_id: str = Field(min_length=1, max_length=200)
    draft_id: UUID
    kind: Literal["delivered", "opened", "replied", "bounced", "unsubscribed"]
    body: str | None = Field(default=None, max_length=20000)
    intent: Literal["interested", "question", "not_interested", "unsubscribe"] = "question"


class JobResponse(Record):
    kind: str
    resource_id: str
    status: str
    attempts: int
    available_at: datetime
    locked_at: datetime | None
    error: str | None


class ActivityResponse(Record):
    action: str
    resource_id: str | None
    description: str


class Reconciliation(Input):
    action: Literal["confirmed_sent", "retry_with_duplicate_risk"]
    acknowledge_duplicate_risk: bool = False

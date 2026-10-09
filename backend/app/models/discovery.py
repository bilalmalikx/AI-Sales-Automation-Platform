"""Discovery records preserve businesses without inventing contact emails."""

from uuid import UUID

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DiscoveryRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "discovery_runs"
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    parameters: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(60), default="discovery")
    provider_run_id: Mapped[str | None] = mapped_column(String(100))
    dataset_id: Mapped[str | None] = mapped_column(String(100))
    provider_cost: Mapped[float] = mapped_column(default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    ai_calls: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class Prospect(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "prospects"
    __table_args__ = (UniqueConstraint("run_id", "source_key", name="uq_prospect_run_source"),)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="CASCADE"), index=True
    )
    source_key: Mapped[str] = mapped_column(String(500))
    company: Mapped[str] = mapped_column(String(300))
    website: Mapped[str | None] = mapped_column(String(2000))
    country: Mapped[str] = mapped_column(String(20), default="")
    city: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(60), default="website_inspection")
    contact_available: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", index=True
    )
    emails: Mapped[list] = mapped_column(JSON, default=list)
    app_status: Mapped[str] = mapped_column(String(40), default="not_checked")
    score: Mapped[int] = mapped_column(Integer, default=0)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str | None] = mapped_column(Text)
    lead_id: Mapped[UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"))
    campaign_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL")
    )

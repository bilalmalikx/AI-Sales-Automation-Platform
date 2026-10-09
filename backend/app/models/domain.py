"""
Core domain models: Company, Lead, Contact, LeadSource.

These models represent the foundational entities for the sales automation
pipeline. Additional models (Campaign, EmailMessage, etc.) will be added
in subsequent phases.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, repr_helper

if TYPE_CHECKING:
    pass  # Forward references for future models


class LeadSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Lead source — where a lead came from.
    Examples: CSV Import, Web Form, API, Manual Entry
    """

    __tablename__ = "lead_sources"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="source", lazy="selectin")

    def __repr__(self) -> str:
        return repr_helper(self, "id", "name")


class Company(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Company / Organization.

    A company may have multiple leads and contacts.
    Enrichment data is stored here (website, industry, etc.).
    """

    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Contact info
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Address
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Enrichment metadata — will be populated by enrichment agent
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="company", lazy="selectin")
    contacts: Mapped[list["Contact"]] = relationship(
        "Contact", back_populates="company", lazy="selectin"
    )

    def __repr__(self) -> str:
        return repr_helper(self, "id", "name", "domain")


class Lead(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Lead — a potential sales opportunity.

    Leads progress through the CRM lifecycle (enriched → audited → email sent
    → replied → booked → won/lost). Lifecycle tracking will be added in Phase 8.
    """

    __tablename__ = "leads"

    # Foreign keys
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lead_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Lead metadata
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="new", index=True)

    # Contact details (may be duplicated in Contact model if decision maker found)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0, server_default="0")
    research: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    __table_args__ = (Index("uq_leads_email_lower", func.lower(email), unique=True),)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="leads", lazy="selectin")
    source: Mapped["LeadSource | None"] = relationship(
        "LeadSource", back_populates="leads", lazy="selectin"
    )

    def __repr__(self) -> str:
        return repr_helper(self, "id", "email", "status")


class Contact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Contact — a decision maker or individual at a company.

    Contacts are discovered by the Decision Maker Research Agent.
    Each contact is associated with a company.
    """

    __tablename__ = "contacts"

    # Foreign keys
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Contact details
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Role
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Social
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Research metadata
    confidence_score: Mapped[float | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="contacts")

    def __repr__(self) -> str:
        return repr_helper(self, "id", "first_name", "last_name", "email")

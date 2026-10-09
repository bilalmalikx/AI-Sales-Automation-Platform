"""
Pydantic schemas for Lead domain model.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class LeadBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

    """Base schema with common Lead fields."""

    email: EmailStr = Field(..., description="Lead email address")
    first_name: str | None = Field(None, max_length=100, description="Lead first name")
    last_name: str | None = Field(None, max_length=100, description="Lead last name")
    title: str | None = Field(None, max_length=200, description="Job title")
    phone: str | None = Field(None, max_length=50, description="Phone number")
    linkedin_url: str | None = Field(None, max_length=500, description="LinkedIn profile URL")
    company_name: str | None = Field(None, max_length=200, description="Company name")
    company_domain: str | None = Field(None, max_length=200, description="Company website domain")
    source_name: str | None = Field(None, max_length=100, description="Lead source name")
    notes: str | None = Field(None, max_length=20000, description="Additional notes")
    industry: str | None = Field(None, max_length=100)


class LeadCreate(LeadBase):
    """Schema for creating a new Lead."""

    status: str | None = Field(default="new", description="Lead status")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str:
        """Validate lead status is allowed."""
        allowed_statuses = [
            "new",
            "contacted",
            "replied",
            "meeting_booked",
            "unsubscribed",
            "qualified",
            "proposal_sent",
            "negotiating",
            "won",
            "lost",
            "unresponsive",
        ]
        if v and v not in allowed_statuses:
            raise ValueError(f"Status must be one of: {', '.join(allowed_statuses)}")
        return v or "new"


class LeadUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value):
        if value is None:
            raise ValueError("Email cannot be null")
        return str(value).lower()

    """Schema for updating an existing Lead."""

    email: EmailStr | None = Field(None, description="Lead email address")
    first_name: str | None = Field(None, max_length=100, description="Lead first name")
    last_name: str | None = Field(None, max_length=100, description="Lead last name")
    title: str | None = Field(None, max_length=200, description="Job title")
    phone: str | None = Field(None, max_length=50, description="Phone number")
    linkedin_url: str | None = Field(None, max_length=500, description="LinkedIn profile URL")
    company_name: str | None = Field(None, max_length=200, description="Company name")
    company_domain: str | None = Field(None, max_length=200, description="Company website domain")
    status: str | None = Field(None, description="Lead status")
    notes: str | None = Field(None, max_length=20000, description="Additional notes")
    industry: str | None = Field(None, max_length=100)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        """Validate lead status is allowed."""
        if v is None:
            raise ValueError("Status cannot be null")
        allowed_statuses = [
            "new",
            "contacted",
            "replied",
            "meeting_booked",
            "unsubscribed",
            "qualified",
            "proposal_sent",
            "negotiating",
            "won",
            "lost",
            "unresponsive",
        ]
        if v not in allowed_statuses:
            raise ValueError(f"Status must be one of: {', '.join(allowed_statuses)}")
        return v


class LeadResponse(LeadBase):
    """Schema for Lead API responses."""

    id: UUID = Field(..., description="Lead UUID")
    status: str = Field(..., description="Lead status")
    company_id: UUID | None = Field(None, description="Associated company UUID")
    source_id: UUID | None = Field(None, description="Lead source UUID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)
    confidence: float = 0
    research: dict | None = None


class LeadFilter(BaseModel):
    """Schema for filtering leads."""

    status: str | None = Field(None, description="Filter by status")
    company_name: str | None = Field(None, description="Filter by company name (partial match)")
    source_name: str | None = Field(None, description="Filter by source name")
    email: str | None = Field(None, description="Filter by email (partial match)")
    created_after: datetime | None = Field(None, description="Filter by creation date (after)")
    created_before: datetime | None = Field(None, description="Filter by creation date (before)")


class LeadListResponse(BaseModel):
    """Schema for paginated lead list responses."""

    items: list[LeadResponse] = Field(..., description="List of leads")
    total: int = Field(..., description="Total number of leads matching filter")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


class CSVLeadImport(BaseModel):
    """Schema for CSV lead import row."""

    email: EmailStr = Field(..., description="Lead email address (required)")
    first_name: str | None = Field(None, description="Lead first name")
    last_name: str | None = Field(None, description="Lead last name")
    title: str | None = Field(None, description="Job title")
    phone: str | None = Field(None, description="Phone number")
    linkedin_url: str | None = Field(None, description="LinkedIn profile URL")
    company_name: str | None = Field(None, description="Company name")
    company_domain: str | None = Field(None, description="Company website domain")
    source_name: str | None = Field(default="csv_import", description="Lead source")
    notes: str | None = Field(None, max_length=20000, description="Additional notes")
    industry: str | None = Field(None, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Basic email validation for CSV import."""
        if not v or "@" not in v:
            raise ValueError("Invalid email format")
        return v.strip().lower()

"""
Pydantic schemas for Lead domain model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class LeadBase(BaseModel):
    """Base schema with common Lead fields."""

    email: EmailStr = Field(..., description="Lead email address")
    first_name: Optional[str] = Field(None, max_length=100, description="Lead first name")
    last_name: Optional[str] = Field(None, max_length=100, description="Lead last name")
    title: Optional[str] = Field(None, max_length=200, description="Job title")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    linkedin_url: Optional[str] = Field(None, max_length=500, description="LinkedIn profile URL")
    company_name: Optional[str] = Field(None, max_length=200, description="Company name")
    company_domain: Optional[str] = Field(None, max_length=200, description="Company website domain")
    source_name: Optional[str] = Field(None, max_length=100, description="Lead source name")
    notes: Optional[str] = Field(None, description="Additional notes")


class LeadCreate(LeadBase):
    """Schema for creating a new Lead."""

    status: Optional[str] = Field(default="new", description="Lead status")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> str:
        """Validate lead status is allowed."""
        allowed_statuses = [
            "new",
            "contacted",
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
    """Schema for updating an existing Lead."""

    email: Optional[EmailStr] = Field(None, description="Lead email address")
    first_name: Optional[str] = Field(None, max_length=100, description="Lead first name")
    last_name: Optional[str] = Field(None, max_length=100, description="Lead last name")
    title: Optional[str] = Field(None, max_length=200, description="Job title")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    linkedin_url: Optional[str] = Field(None, max_length=500, description="LinkedIn profile URL")
    company_name: Optional[str] = Field(None, max_length=200, description="Company name")
    company_domain: Optional[str] = Field(None, max_length=200, description="Company website domain")
    status: Optional[str] = Field(None, description="Lead status")
    notes: Optional[str] = Field(None, description="Additional notes")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate lead status is allowed."""
        if v is None:
            return None
        allowed_statuses = [
            "new",
            "contacted",
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
    company_id: Optional[UUID] = Field(None, description="Associated company UUID")
    source_id: Optional[UUID] = Field(None, description="Lead source UUID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class LeadFilter(BaseModel):
    """Schema for filtering leads."""

    status: Optional[str] = Field(None, description="Filter by status")
    company_name: Optional[str] = Field(None, description="Filter by company name (partial match)")
    source_name: Optional[str] = Field(None, description="Filter by source name")
    email: Optional[str] = Field(None, description="Filter by email (partial match)")
    created_after: Optional[datetime] = Field(None, description="Filter by creation date (after)")
    created_before: Optional[datetime] = Field(None, description="Filter by creation date (before)")


class LeadListResponse(BaseModel):
    """Schema for paginated lead list responses."""

    items: list[LeadResponse] = Field(..., description="List of leads")
    total: int = Field(..., description="Total number of leads matching filter")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


class CSVLeadImport(BaseModel):
    """Schema for CSV lead import row."""

    email: str = Field(..., description="Lead email address (required)")
    first_name: Optional[str] = Field(None, description="Lead first name")
    last_name: Optional[str] = Field(None, description="Lead last name")
    title: Optional[str] = Field(None, description="Job title")
    phone: Optional[str] = Field(None, description="Phone number")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    company_name: Optional[str] = Field(None, description="Company name")
    company_domain: Optional[str] = Field(None, description="Company website domain")
    source_name: Optional[str] = Field(default="csv_import", description="Lead source")
    notes: Optional[str] = Field(None, description="Additional notes")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Basic email validation for CSV import."""
        if not v or "@" not in v:
            raise ValueError("Invalid email format")
        return v.strip().lower()

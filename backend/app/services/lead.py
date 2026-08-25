"""
Business logic service for Lead operations.
"""

from __future__ import annotations

import csv
import io
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.lead import LeadRepository
from app.schemas.lead import (
    LeadCreate,
    LeadUpdate,
    LeadResponse,
    LeadFilter,
    LeadListResponse,
    CSVLeadImport,
)
from app.core.exceptions import (
    ResourceNotFoundException,
    DuplicateResourceException,
    ValidationException,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class LeadService:
    """Service layer for Lead business logic."""

    def __init__(self, session: AsyncSession):
        """Initialize service with database session."""
        self.session = session
        self.repository = LeadRepository(session)

    async def create_lead(self, lead_data: LeadCreate) -> LeadResponse:
        """
        Create a new lead with duplicate detection.

        Args:
            lead_data: Lead creation data

        Returns:
            Created lead response

        Raises:
            DuplicateResourceException: If lead with email already exists
        """
        # Check for duplicate email
        existing_lead = await self.repository.get_by_email(lead_data.email)
        if existing_lead:
            logger.warning(
                "duplicate_lead_detected",
                email=lead_data.email,
                existing_id=str(existing_lead.id),
            )
            raise DuplicateResourceException(
                message=f"Lead with email {lead_data.email} already exists",
                resource_id=str(existing_lead.id),
            )

        # Create lead
        lead = await self.repository.create(lead_data)
        await self.session.commit()

        return LeadResponse.model_validate(lead)

    async def get_lead(self, lead_id: UUID) -> LeadResponse:
        """
        Get lead by ID.

        Args:
            lead_id: Lead UUID

        Returns:
            Lead response

        Raises:
            ResourceNotFoundException: If lead not found
        """
        lead = await self.repository.get_by_id(lead_id)
        if not lead:
            raise ResourceNotFoundException(
                message=f"Lead {lead_id} not found",
                resource_type="Lead",
                resource_id=str(lead_id),
            )

        return LeadResponse.model_validate(lead)

    async def list_leads(
        self,
        filters: Optional[LeadFilter] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> LeadListResponse:
        """
        List leads with filtering and pagination.

        Args:
            filters: Optional filter criteria
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Paginated lead list response
        """
        # Validate pagination
        if page < 1:
            raise ValidationException(message="Page must be >= 1")
        if page_size < 1 or page_size > 100:
            raise ValidationException(message="Page size must be between 1 and 100")

        skip = (page - 1) * page_size
        leads, total = await self.repository.list(
            filters=filters,
            skip=skip,
            limit=page_size,
        )

        # Calculate total pages
        pages = (total + page_size - 1) // page_size if total > 0 else 0

        return LeadListResponse(
            items=[LeadResponse.model_validate(lead) for lead in leads],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    async def update_lead(
        self,
        lead_id: UUID,
        lead_data: LeadUpdate,
    ) -> LeadResponse:
        """
        Update an existing lead.

        Args:
            lead_id: Lead UUID
            lead_data: Update data

        Returns:
            Updated lead response

        Raises:
            ResourceNotFoundException: If lead not found
            DuplicateResourceException: If email conflicts with another lead
        """
        # Check if lead exists
        existing_lead = await self.repository.get_by_id(lead_id)
        if not existing_lead:
            raise ResourceNotFoundException(
                message=f"Lead {lead_id} not found",
                resource_type="Lead",
                resource_id=str(lead_id),
            )

        # Check for email conflicts if email is being updated
        if lead_data.email and lead_data.email != existing_lead.email:
            conflict_lead = await self.repository.get_by_email(lead_data.email)
            if conflict_lead:
                raise DuplicateResourceException(
                    message=f"Lead with email {lead_data.email} already exists",
                    resource_id=str(conflict_lead.id),
                )

        # Update lead
        lead = await self.repository.update(lead_id, lead_data)
        await self.session.commit()

        return LeadResponse.model_validate(lead)

    async def delete_lead(self, lead_id: UUID) -> None:
        """
        Delete a lead.

        Args:
            lead_id: Lead UUID

        Raises:
            ResourceNotFoundException: If lead not found
        """
        deleted = await self.repository.delete(lead_id)
        if not deleted:
            raise ResourceNotFoundException(
                message=f"Lead {lead_id} not found",
                resource_type="Lead",
                resource_id=str(lead_id),
            )

        await self.session.commit()
        logger.info("lead_deleted_via_service", lead_id=str(lead_id))

    async def import_leads_from_csv(
        self,
        csv_content: str,
        skip_duplicates: bool = True,
    ) -> dict[str, int]:
        """
        Import leads from CSV content.

        Args:
            csv_content: CSV file content as string
            skip_duplicates: If True, skip duplicate emails; if False, raise error

        Returns:
            Dict with import statistics (created, skipped, failed)

        Raises:
            ValidationException: If CSV is invalid or duplicates found (when skip_duplicates=False)
        """
        stats = {
            "total": 0,
            "created": 0,
            "skipped": 0,
            "failed": 0,
        }
        errors = []

        try:
            # Parse CSV
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)

            if not reader.fieldnames:
                raise ValidationException(message="CSV file is empty or invalid")

            # Validate required columns
            if "email" not in reader.fieldnames:
                raise ValidationException(
                    message="CSV must contain 'email' column"
                )

            leads_to_create = []
            seen_emails = set()

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header = 1)
                stats["total"] += 1

                try:
                    # Validate row data
                    lead_import = CSVLeadImport(**row)

                    # Check for duplicate in current batch
                    email_lower = lead_import.email.lower()
                    if email_lower in seen_emails:
                        logger.warning(
                            "duplicate_in_csv",
                            row=row_num,
                            email=email_lower,
                        )
                        stats["skipped"] += 1
                        continue

                    # Check for duplicate in database
                    existing_lead = await self.repository.get_by_email(email_lower)
                    if existing_lead:
                        if skip_duplicates:
                            logger.info(
                                "skipping_duplicate",
                                row=row_num,
                                email=email_lower,
                            )
                            stats["skipped"] += 1
                            continue
                        else:
                            errors.append(
                                f"Row {row_num}: Email {email_lower} already exists"
                            )
                            stats["failed"] += 1
                            continue

                    # Add to batch
                    seen_emails.add(email_lower)
                    leads_to_create.append(
                        LeadCreate(
                            email=lead_import.email,
                            first_name=lead_import.first_name,
                            last_name=lead_import.last_name,
                            title=lead_import.title,
                            phone=lead_import.phone,
                            linkedin_url=lead_import.linkedin_url,
                            company_name=lead_import.company_name,
                            company_domain=lead_import.company_domain,
                            source_name=lead_import.source_name,
                            notes=lead_import.notes,
                            status="new",
                        )
                    )

                except Exception as e:
                    logger.error(
                        "csv_row_validation_failed",
                        row=row_num,
                        error=str(e),
                    )
                    errors.append(f"Row {row_num}: {str(e)}")
                    stats["failed"] += 1

            # Bulk create valid leads
            if leads_to_create:
                created_leads = await self.repository.bulk_create(leads_to_create)
                stats["created"] = len(created_leads)
                await self.session.commit()

            logger.info("csv_import_completed", **stats)

            # If there were errors and we're not skipping duplicates, raise exception
            if errors and not skip_duplicates:
                raise ValidationException(
                    message=f"CSV import failed with {len(errors)} errors",
                    details={"errors": errors[:10]},  # Limit to first 10 errors
                )

            return stats

        except csv.Error as e:
            logger.error("csv_parsing_failed", error=str(e))
            raise ValidationException(
                message=f"Invalid CSV format: {str(e)}"
            )
        except Exception as e:
            # Rollback on any error
            await self.session.rollback()
            logger.error("csv_import_failed", error=str(e))
            raise

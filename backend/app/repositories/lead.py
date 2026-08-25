"""
Repository for Lead model data access operations.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.domain import Lead, Company, LeadSource
from app.schemas.lead import LeadCreate, LeadUpdate, LeadFilter
from app.core.logging import get_logger

logger = get_logger(__name__)


class LeadRepository:
    """Repository for Lead CRUD operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    async def create(self, lead_data: LeadCreate) -> Lead:
        """
        Create a new lead.

        Args:
            lead_data: Lead creation data

        Returns:
            Created Lead instance
        """
        lead = Lead(
            email=lead_data.email,
            first_name=lead_data.first_name,
            last_name=lead_data.last_name,
            title=lead_data.title,
            phone=lead_data.phone,
            linkedin_url=lead_data.linkedin_url,
            status=lead_data.status or "new",
            notes=lead_data.notes,
        )

        # Associate with company if company data provided
        if lead_data.company_name or lead_data.company_domain:
            company = await self._get_or_create_company(
                name=lead_data.company_name,
                domain=lead_data.company_domain,
            )
            lead.company_id = company.id

        # Associate with source if provided
        if lead_data.source_name:
            source = await self._get_or_create_source(lead_data.source_name)
            lead.source_id = source.id

        self.session.add(lead)
        await self.session.flush()
        await self.session.refresh(lead)

        logger.info("lead_created", lead_id=str(lead.id), email=lead.email)
        return lead

    async def get_by_id(self, lead_id: UUID) -> Optional[Lead]:
        """
        Get lead by ID.

        Args:
            lead_id: Lead UUID

        Returns:
            Lead instance or None if not found
        """
        stmt = (
            select(Lead)
            .where(Lead.id == lead_id)
            .options(
                selectinload(Lead.company),
                selectinload(Lead.source),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[Lead]:
        """
        Get lead by email address.

        Args:
            email: Lead email

        Returns:
            Lead instance or None if not found
        """
        stmt = select(Lead).where(Lead.email == email.lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        filters: Optional[LeadFilter] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Lead], int]:
        """
        List leads with optional filtering and pagination.

        Args:
            filters: Optional filter criteria
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (leads list, total count)
        """
        # Build base query
        stmt = select(Lead).options(
            selectinload(Lead.company),
            selectinload(Lead.source),
        )

        # Apply filters
        if filters:
            conditions = []

            if filters.status:
                conditions.append(Lead.status == filters.status)

            if filters.email:
                conditions.append(Lead.email.ilike(f"%{filters.email}%"))

            if filters.company_name:
                # Join with company for filtering
                stmt = stmt.join(Lead.company)
                conditions.append(Company.name.ilike(f"%{filters.company_name}%"))

            if filters.source_name:
                # Join with source for filtering
                stmt = stmt.join(Lead.source)
                conditions.append(LeadSource.name.ilike(f"%{filters.source_name}%"))

            if filters.created_after:
                conditions.append(Lead.created_at >= filters.created_after)

            if filters.created_before:
                conditions.append(Lead.created_at <= filters.created_before)

            if conditions:
                stmt = stmt.where(and_(*conditions))

        # Get total count
        count_stmt = select(func.count()).select_from(stmt.alias())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        # Apply pagination and execute
        stmt = stmt.offset(skip).limit(limit).order_by(Lead.created_at.desc())
        result = await self.session.execute(stmt)
        leads = list(result.scalars().all())

        logger.info(
            "leads_listed",
            total=total,
            returned=len(leads),
            skip=skip,
            limit=limit,
        )
        return leads, total

    async def update(self, lead_id: UUID, lead_data: LeadUpdate) -> Optional[Lead]:
        """
        Update an existing lead.

        Args:
            lead_id: Lead UUID
            lead_data: Update data (only non-None fields are updated)

        Returns:
            Updated Lead instance or None if not found
        """
        lead = await self.get_by_id(lead_id)
        if not lead:
            return None

        # Update only provided fields
        update_data = lead_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if field in ["company_name", "company_domain"]:
                # Handle company association
                if value:
                    company = await self._get_or_create_company(
                        name=update_data.get("company_name"),
                        domain=update_data.get("company_domain"),
                    )
                    lead.company_id = company.id
            else:
                setattr(lead, field, value)

        await self.session.flush()
        await self.session.refresh(lead)

        logger.info(
            "lead_updated",
            lead_id=str(lead.id),
            updated_fields=list(update_data.keys()),
        )
        return lead

    async def delete(self, lead_id: UUID) -> bool:
        """
        Delete a lead.

        Args:
            lead_id: Lead UUID

        Returns:
            True if deleted, False if not found
        """
        lead = await self.get_by_id(lead_id)
        if not lead:
            return False

        await self.session.delete(lead)
        await self.session.flush()

        logger.info("lead_deleted", lead_id=str(lead_id))
        return True

    async def bulk_create(self, leads_data: list[LeadCreate]) -> list[Lead]:
        """
        Create multiple leads in bulk.

        Args:
            leads_data: List of lead creation data

        Returns:
            List of created Lead instances
        """
        leads = []

        for lead_data in leads_data:
            lead = Lead(
                email=lead_data.email,
                first_name=lead_data.first_name,
                last_name=lead_data.last_name,
                title=lead_data.title,
                phone=lead_data.phone,
                linkedin_url=lead_data.linkedin_url,
                status=lead_data.status or "new",
                notes=lead_data.notes,
            )

            # Associate with company
            if lead_data.company_name or lead_data.company_domain:
                company = await self._get_or_create_company(
                    name=lead_data.company_name,
                    domain=lead_data.company_domain,
                )
                lead.company_id = company.id

            # Associate with source
            if lead_data.source_name:
                source = await self._get_or_create_source(lead_data.source_name)
                lead.source_id = source.id

            leads.append(lead)

        self.session.add_all(leads)
        await self.session.flush()

        # Refresh all leads to get IDs and timestamps
        for lead in leads:
            await self.session.refresh(lead)

        logger.info("leads_bulk_created", count=len(leads))
        return leads

    async def _get_or_create_company(
        self,
        name: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> Company:
        """
        Get existing company or create new one.

        Args:
            name: Company name
            domain: Company domain

        Returns:
            Company instance
        """
        if not name and not domain:
            raise ValueError("Either name or domain must be provided")

        # Try to find existing company
        conditions = []
        if domain:
            conditions.append(Company.domain == domain.lower())
        if name and not domain:
            conditions.append(Company.name.ilike(name))

        if conditions:
            stmt = select(Company).where(or_(*conditions))
            result = await self.session.execute(stmt)
            company = result.scalar_one_or_none()

            if company:
                return company

        # Create new company
        company = Company(
            name=name or domain,
            domain=domain.lower() if domain else None,
        )
        self.session.add(company)
        await self.session.flush()
        await self.session.refresh(company)

        logger.info("company_created", company_id=str(company.id), name=company.name)
        return company

    async def _get_or_create_source(self, source_name: str) -> LeadSource:
        """
        Get existing lead source or create new one.

        Args:
            source_name: Source name

        Returns:
            LeadSource instance
        """
        # Try to find existing source
        stmt = select(LeadSource).where(LeadSource.name == source_name.lower())
        result = await self.session.execute(stmt)
        source = result.scalar_one_or_none()

        if source:
            return source

        # Create new source
        source = LeadSource(name=source_name.lower())
        self.session.add(source)
        await self.session.flush()
        await self.session.refresh(source)

        logger.info("lead_source_created", source_id=str(source.id), name=source.name)
        return source

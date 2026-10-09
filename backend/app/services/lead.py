"""Transactional lead ingestion and CRM lifecycle management."""

import csv
import io
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.sales import Activity, EmailDraft, Followup, SuppressedEmail
from app.repositories.lead import LeadRepository
from app.repositories.sales import SalesRepository
from app.schemas.lead import LeadCreate, LeadFilter, LeadListResponse, LeadResponse, LeadUpdate


class LeadService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = LeadRepository(session)

    async def retain_suppression(self, lead) -> None:
        if lead.status == "unsubscribed":
            if not await self.session.get(SuppressedEmail, lead.email.lower()):
                self.session.add(SuppressedEmail(email=lead.email.lower(), reason="unsubscribed"))
            for draft in (
                await self.session.scalars(
                    select(EmailDraft).where(
                        EmailDraft.lead_id == lead.id, EmailDraft.status == "queued"
                    )
                )
            ).all():
                draft.status = "cancelled"

    def response(self, lead) -> LeadResponse:
        data = {
            key: getattr(lead, key)
            for key in LeadResponse.model_fields
            if hasattr(lead, key)
            and key not in ("company_name", "company_domain", "source_name", "industry")
        }
        data.update(
            company_name=lead.company.name,
            company_domain=lead.company.domain,
            industry=lead.company.industry,
            source_name=lead.source.name if lead.source else None,
        )
        return LeadResponse(**data)

    async def create_lead(self, value: LeadCreate) -> LeadResponse:
        await SalesRepository(self.session).settings(lock=True)
        if await self.repository.get_by_email(value.email):
            raise ConflictException("A lead with this email already exists")
        if await self.session.get(SuppressedEmail, str(value.email).lower()):
            value = value.model_copy(update={"status": "unsubscribed"})
        lead = await self.repository.create(value)
        await self.retain_suppression(lead)
        self.session.add(
            Activity(action="lead_created", resource_id=str(lead.id), description="Lead created")
        )
        await self.session.commit()
        return self.response(await self.repository.get_by_id(lead.id))

    async def get_lead(self, lead_id: UUID) -> LeadResponse:
        lead = await self.repository.get_by_id(lead_id)
        if not lead:
            raise NotFoundException("Lead not found")
        return self.response(lead)

    async def list_leads(
        self, filters: LeadFilter | None = None, page: int = 1, page_size: int = 50
    ) -> LeadListResponse:
        leads, total = await self.repository.list(filters, (page - 1) * page_size, page_size)
        return LeadListResponse(
            items=[self.response(lead_record) for lead_record in leads],
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    async def update_lead(self, lead_id: UUID, value: LeadUpdate) -> LeadResponse:
        await SalesRepository(self.session).settings(lock=True)
        lead = await self.repository.get_by_id(lead_id)
        if not lead:
            raise NotFoundException("Lead not found")
        if value.status and lead.status == "unsubscribed" and value.status != "unsubscribed":
            raise ConflictException("Opted-out leads cannot be reactivated through CRM edits")
        if value.email and value.email != lead.email:
            if await self.repository.get_by_email(value.email):
                raise ConflictException("A lead with this email already exists")
        if value.email and await self.session.get(SuppressedEmail, str(value.email).lower()):
            value = value.model_copy(update={"status": "unsubscribed"})
        lead = await self.repository.update(lead_id, value)
        await self.retain_suppression(lead)
        if lead.status in ("unsubscribed", "won", "lost", "meeting_booked"):
            for f in (
                await self.session.scalars(
                    select(Followup).where(
                        Followup.lead_id == lead_id, Followup.status == "scheduled"
                    )
                )
            ).all():
                f.status = "cancelled"
        self.session.add(
            Activity(
                action="lead_updated",
                resource_id=str(lead.id),
                description="Contact or CRM stage updated",
            )
        )
        await self.session.commit()
        return self.response(await self.repository.get_by_id(lead_id))

    async def delete_lead(self, lead_id: UUID) -> None:
        await SalesRepository(self.session).settings(lock=True)
        if not await self.repository.delete(lead_id):
            raise NotFoundException("Lead not found")
        self.session.add(
            Activity(
                action="lead_deleted",
                resource_id=str(lead_id),
                description="Lead and associated records removed",
            )
        )
        await self.session.commit()

    async def import_leads_from_csv(self, csv_content: str, skip_duplicates: bool = True) -> dict:
        await SalesRepository(self.session).settings(lock=True)
        stats = {"total": 0, "created": 0, "skipped": 0, "failed": 0}
        errors = []
        try:
            reader = csv.DictReader(io.StringIO(csv_content.lstrip("\ufeff")), strict=True)
            headers = [h.strip().lower() for h in (reader.fieldnames or [])]
            if "email" not in headers or len(headers) != len(set(headers)):
                raise ValidationException("CSV requires an email column and unique headers")
            reader.fieldnames = headers
            seen = set()
            batch = []
            for n, row in enumerate(reader, start=2):
                stats["total"] += 1
                if stats["total"] > settings.MAX_CSV_ROWS:
                    raise ValidationException("CSV row limit exceeded")
                row = {k: (v or "").strip() or None for k, v in row.items() if k}
                if row.get("name") and not row.get("first_name"):
                    parts = row.pop("name").split(" ", 1)
                    row["first_name"] = parts[0]
                    row["last_name"] = parts[1] if len(parts) > 1 else None
                if row.get("company"):
                    row["company_name"] = row.pop("company")
                allowed = {k: v for k, v in row.items() if k in LeadCreate.model_fields}
                try:
                    value = (
                        LeadCreate(**allowed, source_name=row.get("source_name") or "csv_import")
                        if "source_name" not in allowed
                        else LeadCreate(**allowed)
                    )
                except ValidationError:
                    stats["failed"] += 1
                    errors.append({"row": n, "message": "Invalid lead fields"})
                    continue
                if value.email in seen or await self.repository.get_by_email(value.email):
                    stats["skipped"] += 1
                    errors.append({"row": n, "message": "Duplicate email"})
                    continue
                seen.add(value.email)
                batch.append(value)
            if errors and not skip_duplicates:
                raise ValidationException(
                    "CSV rejected; no rows imported", details={"errors": errors[:50]}
                )
            for value in batch:
                if await self.session.get(SuppressedEmail, str(value.email).lower()):
                    value = value.model_copy(update={"status": "unsubscribed"})
                created = await self.repository.create(value)
                await self.retain_suppression(created)
                stats["created"] += 1
            self.session.add(
                Activity(action="csv_imported", description=f"Imported {stats['created']} leads")
            )
            await self.session.commit()
            return {**stats, "errors": errors[:50]}
        except csv.Error as exc:
            await self.session.rollback()
            raise ValidationException("Malformed CSV") from exc
        except Exception:
            await self.session.rollback()
            raise

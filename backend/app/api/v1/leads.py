"""
API router for Lead endpoints.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ValidationException
from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.lead import (
    LeadCreate,
    LeadFilter,
    LeadListResponse,
    LeadResponse,
    LeadUpdate,
)
from app.services.lead import LeadService

logger = get_logger(__name__)

router = APIRouter(prefix="/leads", tags=["leads"])


def get_lead_service(session: AsyncSession = Depends(get_db)) -> LeadService:
    """Dependency to get LeadService instance."""
    return LeadService(session)


@router.post(
    "",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new lead",
)
async def create_lead(
    lead_data: LeadCreate,
    service: LeadService = Depends(get_lead_service),
) -> LeadResponse:
    """
    Create a new lead.

    - **email**: Lead email (required, must be unique)
    - **first_name**: Lead first name (optional)
    - **last_name**: Lead last name (optional)
    - **title**: Job title (optional)
    - **company_name**: Company name (optional, auto-creates company)
    - **status**: Lead status (default: "new")
    """
    logger.info("create_lead_request", email=lead_data.email)
    return await service.create_lead(lead_data)


@router.get(
    "",
    response_model=LeadListResponse,
    summary="List leads with filtering and pagination",
)
async def list_leads(
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    company_name: str | None = Query(None, description="Filter by company name (partial match)"),
    source_name: str | None = Query(None, description="Filter by source name"),
    email: str | None = Query(None, description="Filter by email (partial match)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page (max 100)"),
    service: LeadService = Depends(get_lead_service),
) -> LeadListResponse:
    """
    List leads with optional filtering and pagination.

    **Query Parameters:**
    - **status**: Filter by lead status
    - **company_name**: Filter by company name (case-insensitive partial match)
    - **source_name**: Filter by lead source
    - **email**: Filter by email (case-insensitive partial match)
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)

    **Returns:**
    - Paginated list with metadata (total, pages, current page)
    """
    filters = LeadFilter(
        status=status_filter,
        company_name=company_name,
        source_name=source_name,
        email=email,
    )

    logger.info(
        "list_leads_request",
        page=page,
        page_size=page_size,
        filters=filters.model_dump(exclude_none=True),
    )
    return await service.list_leads(filters=filters, page=page, page_size=page_size)


@router.get(
    "/{lead_id}",
    response_model=LeadResponse,
    summary="Get lead by ID",
)
async def get_lead(
    lead_id: UUID,
    service: LeadService = Depends(get_lead_service),
) -> LeadResponse:
    """
    Get a specific lead by UUID.

    **Path Parameters:**
    - **lead_id**: Lead UUID

    **Returns:**
    - Lead details with associated company and source
    """
    logger.info("get_lead_request", lead_id=str(lead_id))
    return await service.get_lead(lead_id)


@router.put(
    "/{lead_id}",
    response_model=LeadResponse,
    summary="Update a lead",
)
async def update_lead(
    lead_id: UUID,
    lead_data: LeadUpdate,
    service: LeadService = Depends(get_lead_service),
) -> LeadResponse:
    """
    Update an existing lead.

    **Path Parameters:**
    - **lead_id**: Lead UUID

    **Body:**
    - Only include fields you want to update
    - Email must be unique if changed

    **Returns:**
    - Updated lead details
    """
    logger.info(
        "update_lead_request",
        lead_id=str(lead_id),
        update_fields=lead_data.model_dump(exclude_unset=True),
    )
    return await service.update_lead(lead_id, lead_data)


@router.delete(
    "/{lead_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a lead",
)
async def delete_lead(
    lead_id: UUID,
    service: LeadService = Depends(get_lead_service),
) -> None:
    """
    Delete a lead permanently.

    **Path Parameters:**
    - **lead_id**: Lead UUID

    **Returns:**
    - 204 No Content on success
    """
    logger.info("delete_lead_request", lead_id=str(lead_id))
    await service.delete_lead(lead_id)


@router.post(
    "/import/csv",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Import leads from CSV file",
)
async def import_leads_csv(
    file: UploadFile = File(..., description="CSV file with lead data"),
    skip_duplicates: bool = Query(
        True,
        description="Skip duplicate emails instead of failing",
    ),
    service: LeadService = Depends(get_lead_service),
) -> dict:
    """
    Import leads from a CSV file.

    **Required CSV Columns:**
    - **email**: Lead email address (required)

    **Optional CSV Columns:**
    - first_name, last_name, title, phone, linkedin_url
    - company_name, company_domain
    - source_name (default: "csv_import")
    - notes

    **Query Parameters:**
    - **skip_duplicates**: If true, skip existing emails; if false, fail on duplicates

    **Returns:**
    - Import statistics: total, created, skipped, failed

    **Example CSV:**
    ```csv
    email,first_name,last_name,company_name,title
    john@example.com,John,Doe,Example Inc,CEO
    jane@acme.com,Jane,Smith,Acme Corp,CTO
    ```
    """
    logger.info("import_csv_request", filename=file.filename, skip_duplicates=skip_duplicates)

    # Validate file type
    if not file.filename or not file.filename.endswith(".csv"):
        raise ValidationException(message="File must be a CSV (.csv extension)")

    # Read file content
    try:
        content = await file.read(settings.MAX_CSV_BYTES + 1)
        if len(content) > settings.MAX_CSV_BYTES:
            raise ValidationException("CSV file size limit exceeded")
        csv_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise ValidationException(message="File must be UTF-8 encoded") from None

    # Import leads
    stats = await service.import_leads_from_csv(
        csv_content=csv_content,
        skip_duplicates=skip_duplicates,
    )

    logger.info("import_csv_completed", **stats)
    return {
        "message": "CSV import completed",
        "statistics": stats,
    }

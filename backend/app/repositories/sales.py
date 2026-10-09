"""Common database access with explicit row locking and bounded pagination."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.sales import WorkspaceSettings
from app.schemas.sales import Page


class SalesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, model, identifier: UUID, lock: bool = False):
        statement = select(model).where(model.id == identifier)
        if lock:
            statement = statement.with_for_update()
        obj = (await self.session.scalars(statement)).first()
        if obj is None:
            raise NotFoundException(f"{model.__name__} not found")
        return obj

    async def settings(self, lock: bool = False) -> WorkspaceSettings:
        statement = select(WorkspaceSettings).where(WorkspaceSettings.id == 1)
        if lock:
            statement = statement.with_for_update()
        obj = (await self.session.scalars(statement)).first()
        if obj is None:
            raise NotFoundException("Workspace settings missing; apply database migrations")
        return obj

    async def page(self, model, schema, page: int, page_size: int, conditions=()):
        query = select(model).where(*conditions)
        total = await self.session.scalar(select(func.count()).select_from(query.subquery()))
        items = (
            await self.session.scalars(
                query.order_by(model.created_at.desc(), model.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return Page(
            items=[schema.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

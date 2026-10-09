"""
SQLAlchemy async session management.

Usage in route handlers:
    @router.get("/leads")
    async def get_leads(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(Lead))
        return result.scalars().all()
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.engine import get_engine

# Session factory — created once at module import
SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=None,  # bind is set dynamically in get_db() to allow testing overrides
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI routes. Yields an async session, ensures it closes.

    Usage:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...
    """
    engine = get_engine()
    SessionLocal.configure(bind=engine)
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

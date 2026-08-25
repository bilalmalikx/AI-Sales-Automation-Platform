"""
SQLAlchemy async engine.

The engine is a module-level singleton. It is created at application startup
and disposed at shutdown (see app/main.py lifespan).
"""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """
    Return the global async engine instance.
    Raises RuntimeError if called before init_db() or after dispose_db().
    """
    if engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    return engine


async def init_db() -> None:
    """Initialize the async database engine. Called at app startup."""
    global engine
    logger.info(
        "initializing_database_engine",
        url=settings.DATABASE_URL.split("@")[-1],  # hide credentials in logs
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
    )
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_pre_ping=True,  # verify connections before use
    )
    logger.info("database_engine_initialized")


async def dispose_db() -> None:
    """Dispose the database engine. Called at app shutdown."""
    global engine
    if engine is not None:
        logger.info("disposing_database_engine")
        await engine.dispose()
        engine = None
        logger.info("database_engine_disposed")

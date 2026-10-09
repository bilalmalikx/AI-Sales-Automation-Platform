"""
Application entry point.

create_app() is the application factory — it builds a configured FastAPI
instance. The module-level `app` variable is what uvicorn targets.

Usage:
    uvicorn app.main:app --reload
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.discovery import router as discovery_router
from app.api.v1.health import router as health_router
from app.api.v1.leads import router as leads_router
from app.api.v1.sales import public as public_router
from app.api.v1.sales import router as sales_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestContextMiddleware
from app.core.security import require_auth

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle: startup → yield → shutdown."""
    logger.info(
        "application_startup",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        env=settings.APP_ENV,
    )
    # Initialize database engine
    from app.db.engine import init_db

    await init_db()

    from sqlalchemy import select

    from app.db.engine import get_engine
    from app.models.sales import WorkspaceSettings

    async with get_engine().connect() as conn:
        await conn.execute(select(WorkspaceSettings.id).limit(1))
    worker = None
    if settings.WORKER_MODE == "inline":
        from app.tasks.worker import poll

        worker = asyncio.create_task(poll())
    try:
        yield
    finally:
        if worker:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
    logger.info("application_shutdown")

    # Dispose database engine
    from app.db.engine import dispose_db

    await dispose_db()


def create_app() -> FastAPI:
    """
    Application factory.

    Returns a fully configured FastAPI instance with:
    - Structured logging
    - CORS middleware
    - Request-context middleware (request ID, timing)
    - Centralised exception handlers
    - All API routers registered under /api/v1
    """
    setup_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        description=(
            "Production-grade AI-Powered Lead Generation, Outreach, "
            "Sales Automation, CRM & Analytics Platform."
        ),
        version=settings.APP_VERSION,
        # Disable interactive docs in production
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    # Note: middleware is executed in reverse registration order
    # (last registered = outermost wrapper).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    # ── Exception Handlers ────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health_router)
    app.include_router(discovery_router, prefix=settings.API_V1_PREFIX)
    app.include_router(sales_router, prefix=settings.API_V1_PREFIX)
    app.include_router(
        leads_router, prefix=settings.API_V1_PREFIX, dependencies=[Depends(require_auth)]
    )
    app.include_router(public_router, prefix=settings.API_V1_PREFIX)

    return app


app: FastAPI = create_app()

"""
Application entry point.

create_app() is the application factory — it builds a configured FastAPI
instance. The module-level `app` variable is what uvicorn targets.

Usage:
    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.api.v1.leads import router as leads_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestContextMiddleware

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
    
    # Phase 6: initialise Redis connection pool here
    yield
    logger.info("application_shutdown")
    
    # Dispose database engine
    from app.db.engine import dispose_db
    await dispose_db()
    
    # Phase 6: close Redis connection pool here


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
    app.include_router(leads_router, prefix=settings.API_V1_PREFIX)

    return app


app: FastAPI = create_app()

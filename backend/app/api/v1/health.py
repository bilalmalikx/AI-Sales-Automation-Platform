"""
Health & readiness endpoints.

GET /health         — basic liveness (process is alive)
GET /health/live    — explicit liveness probe (K8s / ALB)
GET /health/ready   — readiness probe; checks critical dependencies
                      (DB and Redis checks are wired in Phase 2 / Phase 6)
"""

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter

from app.core.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Basic liveness")
async def health() -> dict[str, Any]:
    return {
        "status": "alive",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/health/live", summary="Liveness probe")
async def health_live() -> dict[str, str]:
    """Lightweight liveness probe — no dependency checks."""
    return {"status": "alive"}


@router.get("/health/ready", summary="Readiness probe")
async def health_ready() -> dict[str, Any]:
    """
    Readiness probe.  Each dependency reports its status.
    Returns HTTP 200 when the service is ready to accept traffic.
    """
    checks: dict[str, str] = {}
    
    # Database check
    try:
        from app.db.engine import get_engine
        from sqlalchemy import text
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
        checks["database"] = "failed"
    
    # Redis check (Phase 6)
    checks["redis"] = "not_configured"

    # Determine overall status — degrade gracefully
    all_ok = all(v in ("ok", "not_configured") for v in checks.values())
    overall = "ready" if all_ok else "degraded"

    logger.debug("health_ready_check", checks=checks, overall=overall)

    return {
        "status": overall,
        "checks": checks,
        "timestamp": datetime.now(UTC).isoformat(),
    }

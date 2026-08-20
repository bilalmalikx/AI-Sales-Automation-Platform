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
    Dependency checks (DB, Redis) will be fully wired in Phase 2/6.
    """
    checks: dict[str, str] = {
        "database": "not_configured",  # wired in Phase 2
        "redis": "not_configured",     # wired in Phase 6
    }

    # Determine overall status — degrade gracefully
    all_ok = all(v in ("ok", "not_configured") for v in checks.values())
    overall = "ready" if all_ok else "degraded"

    logger.debug("health_ready_check", checks=checks, overall=overall)

    return {
        "status": overall,
        "checks": checks,
        "timestamp": datetime.now(UTC).isoformat(),
    }

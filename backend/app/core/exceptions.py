"""
Centralised exception hierarchy and FastAPI exception handlers.

All custom exceptions inherit from AppBaseException so a single handler
can catch any application-level error and return a safe, structured response.

Internal stack traces are never exposed to API clients.
"""

import uuid
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


# ── Exception Hierarchy ───────────────────────────────────────────────────────


class AppBaseException(Exception):
    """Root application exception. All custom exceptions inherit from this."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: str | None = None,
        details: Any = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.details = details
        super().__init__(self.message)


class NotFoundException(AppBaseException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"
    message = "Resource not found"


class ValidationException(AppBaseException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "VALIDATION_ERROR"
    message = "Validation failed"


class ConflictException(AppBaseException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"
    message = "Resource already exists"


class UnauthorizedException(AppBaseException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "UNAUTHORIZED"
    message = "Authentication required"


class ForbiddenException(AppBaseException):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "FORBIDDEN"
    message = "Insufficient permissions"


class RateLimitException(AppBaseException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Too many requests"


class ExternalServiceException(AppBaseException):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "EXTERNAL_SERVICE_ERROR"
    message = "External service error"


class AgentException(AppBaseException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "AGENT_ERROR"
    message = "Agent execution failed"


class LowConfidenceException(AgentException):
    error_code = "LOW_CONFIDENCE"
    message = "Agent confidence below threshold — human escalation required"


class LLMException(AppBaseException):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "LLM_ERROR"
    message = "LLM provider error"


class DatabaseException(AppBaseException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "DATABASE_ERROR"
    message = "Database operation failed"


class DuplicateEventException(ConflictException):
    error_code = "DUPLICATE_EVENT"
    message = "Event already processed (idempotency check)"


# ── Response Builder ──────────────────────────────────────────────────────────


def _build_error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    trace_id = str(uuid.uuid4())
    body: dict[str, Any] = {
        "error": {
            "code": error_code,
            "message": message,
            "trace_id": trace_id,
            "path": str(request.url.path),
        }
    }
    if details is not None:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


# ── Handler Registration ──────────────────────────────────────────────────────


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers onto the FastAPI app instance."""

    @app.exception_handler(AppBaseException)
    async def app_exception_handler(
        request: Request, exc: AppBaseException
    ) -> JSONResponse:
        logger.warning(
            "app_exception",
            error_code=exc.error_code,
            message=exc.message,
            path=request.url.path,
            method=request.method,
        )
        return _build_error_response(
            request,
            exc.status_code,
            exc.error_code,
            exc.message,
            exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "request_validation_error",
            errors=exc.errors(),
            path=request.url.path,
        )
        return _build_error_response(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            "Request validation failed",
            exc.errors(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            path=request.url.path,
        )
        return _build_error_response(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "An unexpected error occurred",
        )

"""Single-workspace bearer authentication and scoped public tokens."""

import hashlib
import hmac
import time
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UnauthorizedException
from app.db.session import get_db

bearer = HTTPBearer(auto_error=False)


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> None:
    if (
        settings.API_TOKEN
        and credentials
        and hmac.compare_digest(credentials.credentials, settings.API_TOKEN)
    ):
        return
    if settings.AUTH_ENABLED:
        from app.services.auth import current_user

        await current_user(request, db)
        return
    if not settings.API_TOKEN and settings.is_development:
        return
    raise UnauthorizedException()


def scoped_token(resource: UUID, purpose: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(), f"{purpose}:{resource}".encode(), hashlib.sha256
    ).hexdigest()


def verify_token(resource: UUID, purpose: str, token: str) -> None:
    if not hmac.compare_digest(token, scoped_token(resource, purpose)):
        raise UnauthorizedException("Invalid link token")


def verify_webhook(body: bytes, timestamp: str, signature: str) -> None:
    try:
        valid_time = abs(time.time() - int(timestamp)) <= 300
    except ValueError:
        valid_time = False
    expected = hmac.new(
        settings.WEBHOOK_SECRET.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    if (
        not settings.WEBHOOK_SECRET
        or not valid_time
        or not hmac.compare_digest(expected, signature)
    ):
        raise UnauthorizedException("Invalid webhook signature or timestamp")

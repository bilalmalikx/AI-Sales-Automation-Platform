"""Passwords never leave salted scrypt; stored bearer/link tokens are SHA-256 digests."""

import asyncio
import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from html import escape
from pathlib import Path

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UnauthorizedException
from app.db.session import get_db
from app.models.auth import Session, User
from app.providers.email import _smtp_send
from app.providers.email_template import render_email

COOKIE = "skilledhat_session"


def now():
    return datetime.now(UTC).replace(tzinfo=None)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + ":" + key.hex()


def password_matches(password: str, stored: str) -> bool:
    try:
        salt, key = stored.split(":")
        value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(value.hex(), key)
    except (ValueError, TypeError):
        return False


def check_origin(request: Request):
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get(
        "origin"
    ) != settings.AUTH_FRONTEND_URL.rstrip("/"):
        raise UnauthorizedException("Request origin is not allowed")


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE, "")
    session = await db.get(Session, digest(token)) if token else None
    user = (
        await db.get(User, session.user_email) if session and session.expires_at > now() else None
    )
    if not user or not user.verified:
        raise UnauthorizedException("Please log in to your workspace")
    check_origin(request)
    return user


async def send_verification(email: str, token: str):
    url = settings.AUTH_FRONTEND_URL.rstrip("/") + "/#/verify-email?token=" + token
    message = EmailMessage()
    message["From"] = formataddr(
        ("Skilledhat", settings.DEFAULT_FROM_EMAIL or "skilledhat@localhost.test")
    )
    message["To"] = email
    message["Subject"] = "Verify your Skilledhat email address"
    message["Message-ID"] = make_msgid()
    body = (
        "Welcome to Skilledhat. Confirm your email address to activate your workspace account.\n\n"
        + url
        + "\n\nThis link expires in 30 minutes and can be used once. If you did not request this account, ignore this email."
    )
    message.set_content(body)
    message.add_alternative(
        render_email(
            "Verify your email address", body, "Skilledhat team", label="ACCOUNT VERIFICATION"
        ),
        subtype="html",
    )
    html_part = message.get_body(preferencelist=("html",))
    html_body = html_part.get_content().replace(
        escape(url),
        '<a href="'
        + escape(url, quote=True)
        + '" style="display:inline-block;padding:14px 22px;background:#5b57c9;color:white;border-radius:10px;text-decoration:none;font-weight:bold;">Verify email address</a>',
    )
    html_part.set_content(html_body, subtype="html")
    if settings.EMAIL_PROVIDER == "local":
        root = Path(settings.LOCAL_MAIL_DIR)
        root.mkdir(parents=True, exist_ok=True)
        fd = os.open(
            root / ("verification-" + secrets.token_hex(12) + ".eml"),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(fd, "wb") as out:
            out.write(message.as_bytes())
    else:
        await asyncio.to_thread(_smtp_send, message, transactional=True)


async def issue_verification(db, user):
    token = secrets.token_urlsafe(32)
    user.verification_hash = digest(token)
    user.verification_expires = now() + timedelta(minutes=30)
    user.email_sent_at = now()
    await db.commit()
    await send_verification(user.email, token)

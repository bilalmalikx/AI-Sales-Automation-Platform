"""Email-verified accounts for the private Skilledhat workspace."""

import asyncio
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictException, UnauthorizedException
from app.db.session import get_db
from app.models.auth import Session, User
from app.repositories.sales import SalesRepository
from app.services.auth import (
    COOKIE,
    check_origin,
    current_user,
    digest,
    issue_verification,
    now,
    password_hash,
    password_matches,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
DB = Annotated[AsyncSession, Depends(get_db)]
GENERIC = {
    "message": "If this email is eligible, a verification link has been sent. Check your inbox."
}


class EmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class Credentials(EmailInput):
    password: str = Field(min_length=12, max_length=128)


class Signup(Credentials):
    name: str = Field(min_length=1, max_length=100)


class Verification(BaseModel):
    token: str = Field(min_length=32, max_length=100)


def profile(user):
    return {"email": user.email, "name": user.name, "role": user.role}


@router.post("/signup", status_code=202)
async def signup(value: Signup, request: Request, db: DB):
    check_origin(request)
    await SalesRepository(db).settings(lock=True)
    email = str(value.email).lower()
    user = await db.get(User, email)
    owner = (settings.AUTH_OWNER_EMAIL or settings.DEFAULT_FROM_EMAIL).lower()
    if not user and email != owner:
        return GENERIC
    if user and (user.password_hash or not user.invited):
        return GENERIC
    if not user:
        user = User(email=email, role="owner", invited=True)
        db.add(user)
    user.name = value.name
    user.password_hash = await asyncio.to_thread(password_hash, value.password)
    user.verified = False
    await issue_verification(db, user)
    return GENERIC


@router.post("/resend-verification", status_code=202)
async def resend(value: EmailInput, request: Request, db: DB):
    check_origin(request)
    await SalesRepository(db).settings(lock=True)
    user = await db.get(User, str(value.email).lower())
    if (
        user
        and user.password_hash
        and not user.verified
        and (not user.email_sent_at or user.email_sent_at < now() - timedelta(seconds=60))
    ):
        await issue_verification(db, user)
    return GENERIC


@router.post("/verify-email")
async def verify(value: Verification, request: Request, db: DB):
    check_origin(request)
    await SalesRepository(db).settings(lock=True)
    user = await db.scalar(
        select(User).where(User.verification_hash == digest(value.token)).with_for_update()
    )
    if not user or not user.verification_expires or user.verification_expires <= now():
        raise ConflictException("Verification link is invalid or expired. Request a new link.")
    user.verified = True
    user.verification_hash = None
    user.verification_expires = None
    await db.commit()
    return {"message": "Email verified. You can now log in."}


@router.post("/login")
async def login(value: Credentials, request: Request, response: Response, db: DB):
    check_origin(request)
    await SalesRepository(db).settings(lock=True)
    user = await db.get(User, str(value.email).lower())
    # Spend the same password work on unknown accounts to reduce account enumeration.
    stored = user.password_hash if user and user.password_hash else "00" * 16 + ":" + "00" * 64
    matched = await asyncio.to_thread(password_matches, value.password, stored)
    if not user or (user.locked_until and user.locked_until > now()):
        raise UnauthorizedException("Invalid credentials or temporarily locked account")
    if not matched:
        user.failed_logins += 1
        if user.failed_logins >= 5:
            user.locked_until = now() + timedelta(minutes=15)
            user.failed_logins = 0
        await db.commit()
        raise UnauthorizedException("Invalid credentials or temporarily locked account")
    if not user.verified:
        raise UnauthorizedException("Verify your email before logging in")
    user.failed_logins = 0
    user.locked_until = None
    token = secrets.token_urlsafe(32)
    await db.execute(delete(Session).where(Session.expires_at <= now()))
    db.add(
        Session(
            token_hash=digest(token), user_email=user.email, expires_at=now() + timedelta(hours=12)
        )
    )
    await db.commit()
    response.set_cookie(
        COOKIE,
        token,
        max_age=43200,
        httponly=True,
        secure=not settings.is_development,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return profile(user)


@router.get("/me")
async def me(response: Response, user: Annotated[User, Depends(current_user)]):
    response.headers["Cache-Control"] = "no-store"
    return profile(user)


@router.post("/logout")
async def logout(request: Request, response: Response, db: DB):
    check_origin(request)
    token = request.cookies.get(COOKIE, "")
    await db.execute(delete(Session).where(Session.token_hash == digest(token)))
    await db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"message": "Logged out"}


@router.post("/invitations", status_code=201)
async def invite(value: EmailInput, db: DB, user: Annotated[User, Depends(current_user)]):
    if user.role != "owner":
        raise UnauthorizedException("Only the workspace owner can invite members")
    await SalesRepository(db).settings(lock=True)
    email = str(value.email).lower()
    existing = await db.get(User, email)
    if not existing:
        db.add(User(email=email, invited=True))
        await db.commit()
    return {"message": "Member may now sign up using this email address."}

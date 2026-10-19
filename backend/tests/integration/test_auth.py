"""Verified private-workspace access, expiring links and revocable cookie sessions."""

import re
from datetime import timedelta
from email import policy
from email.parser import BytesParser

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.db.engine import get_engine
from app.models.auth import Session, User
from app.services.auth import digest, now

BASE = "/api/v1/auth"
ORIGIN = {"Origin": "http://localhost:4202"}
PASSWORD = "a long test passphrase"


@pytest.fixture
def auth_env(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(settings, "AUTH_FRONTEND_URL", "http://localhost:4202")
    monkeypatch.setattr(settings, "LOCAL_MAIL_DIR", str(tmp_path))
    client.cookies.clear()
    yield tmp_path
    client.cookies.clear()


def signup(client, email="owner@example.com"):
    return client.post(
        BASE + "/signup",
        json={"name": "Owner", "email": email, "password": PASSWORD},
        headers=ORIGIN,
    )


def link_token(root):
    message = BytesParser(policy=policy.default).parsebytes(
        max(root.glob("verification-*.eml"), key=lambda p: p.stat().st_mtime_ns).read_bytes()
    )
    return re.search(
        r"token=([\w-]+)", message.get_body(preferencelist=("plain",)).get_content()
    ).group(1)


def verified_login(client, root):
    assert signup(client).status_code == 202
    token = link_token(root)
    assert (
        client.post(BASE + "/verify-email", json={"token": token}, headers=ORIGIN).status_code
        == 200
    )
    r = client.post(
        BASE + "/login", json={"email": "owner@example.com", "password": PASSWORD}, headers=ORIGIN
    )
    assert r.status_code == 200
    return token, r


def test_signup_verify_login_private_access_csrf_and_logout(client, auth_env):
    assert client.get("/api/v1/leads").status_code == 401
    assert signup(client).status_code == 202
    assert (
        client.post(
            BASE + "/login",
            json={"email": "owner@example.com", "password": PASSWORD},
            headers=ORIGIN,
        ).status_code
        == 401
    )
    token = link_token(auth_env)
    assert (
        client.post(BASE + "/verify-email", json={"token": token}, headers=ORIGIN).status_code
        == 200
    )
    assert (
        client.post(BASE + "/verify-email", json={"token": token}, headers=ORIGIN).status_code
        == 409
    )
    response = client.post(
        BASE + "/login", json={"email": "owner@example.com", "password": PASSWORD}, headers=ORIGIN
    )
    assert response.status_code == 200 and "HttpOnly" in response.headers["set-cookie"]
    assert "password" not in response.text
    assert client.get("/api/v1/leads").status_code == 200
    assert (
        client.post(
            "/api/v1/campaigns",
            json={"name": "Bad origin", "audience": "Team", "offer": "Service"},
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 401
    )
    cookie = client.cookies.get("skilledhat_session")
    assert client.post(BASE + "/logout", headers=ORIGIN).status_code == 200
    client.cookies.set("skilledhat_session", cookie)
    assert client.get(BASE + "/me").status_code == 401


def test_unknown_signup_cannot_join_private_workspace(client, auth_env):
    assert signup(client, "outsider@example.com").status_code == 202
    assert not list(auth_env.glob("*.eml"))
    assert (
        client.post(
            BASE + "/login",
            json={"email": "outsider@example.com", "password": PASSWORD},
            headers=ORIGIN,
        ).status_code
        == 401
    )


def test_passwords_and_tokens_are_hashed(client, auth_env):
    token, _ = verified_login(client, auth_env)
    cookie = client.cookies.get("skilledhat_session")

    async def check():
        async with async_sessionmaker(get_engine())() as db:
            user = await db.get(User, "owner@example.com")
            session = await db.scalar(select(Session))
            assert user.password_hash != PASSWORD and len(user.password_hash) > 100
            assert user.verification_hash is None
            assert session.token_hash == digest(cookie) and session.token_hash != cookie
            assert token not in user.password_hash

    client.portal.call(check)


def test_expired_link_and_resend_rotate_token(client, auth_env):
    signup(client)
    token = link_token(auth_env)

    async def expire():
        async with async_sessionmaker(get_engine())() as db:
            user = await db.get(User, "owner@example.com")
            user.verification_expires = now() - timedelta(seconds=1)
            user.email_sent_at = now() - timedelta(seconds=61)
            await db.commit()

    client.portal.call(expire)
    assert (
        client.post(BASE + "/verify-email", json={"token": token}, headers=ORIGIN).status_code
        == 409
    )
    assert (
        client.post(
            BASE + "/resend-verification", json={"email": "owner@example.com"}, headers=ORIGIN
        ).status_code
        == 202
    )
    replacement = link_token(auth_env)
    assert replacement != token
    assert (
        client.post(BASE + "/verify-email", json={"token": token}, headers=ORIGIN).status_code
        == 409
    )
    assert (
        client.post(BASE + "/verify-email", json={"token": replacement}, headers=ORIGIN).status_code
        == 200
    )
    count = len(list(auth_env.glob("*.eml")))
    client.post(BASE + "/resend-verification", json={"email": "owner@example.com"}, headers=ORIGIN)
    assert len(list(auth_env.glob("*.eml"))) == count


def test_only_owner_can_invite_and_invited_member_must_verify(client, auth_env):
    verified_login(client, auth_env)
    assert (
        client.post(
            BASE + "/invitations", json={"email": "member@example.com"}, headers=ORIGIN
        ).status_code
        == 201
    )
    assert signup(client, "member@example.com").status_code == 202
    token = link_token(auth_env)
    assert (
        client.post(BASE + "/verify-email", json={"token": token}, headers=ORIGIN).status_code
        == 200
    )
    client.post(BASE + "/logout", headers=ORIGIN)
    assert (
        client.post(
            BASE + "/login",
            json={"email": "member@example.com", "password": PASSWORD},
            headers=ORIGIN,
        ).status_code
        == 200
    )
    assert (
        client.post(
            BASE + "/invitations", json={"email": "outsider@example.com"}, headers=ORIGIN
        ).status_code
        == 401
    )


def test_login_lockout_and_bad_origin(client, auth_env):
    verified_login(client, auth_env)
    client.post(BASE + "/logout", headers=ORIGIN)
    for _ in range(5):
        assert (
            client.post(
                BASE + "/login",
                json={"email": "owner@example.com", "password": "wrong password long"},
                headers=ORIGIN,
            ).status_code
            == 401
        )
    assert (
        client.post(
            BASE + "/login",
            json={"email": "owner@example.com", "password": PASSWORD},
            headers=ORIGIN,
        ).status_code
        == 401
    )
    assert signup(client, "new@example.com").status_code == 202
    assert (
        client.post(
            BASE + "/signup",
            json={"name": "Test", "email": "owner@example.com", "password": PASSWORD},
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 401
    )


def test_verification_uses_branded_multipart_smtp_without_enabling_outreach(
    client, auth_env, monkeypatch
):
    from tests.integration.test_providers import smtp_server

    with smtp_server() as (port, deliveries):
        for key, value in {
            "EMAIL_PROVIDER": "smtp",
            "SMTP_HOST": "127.0.0.1",
            "SMTP_PORT": port,
            "SMTP_TLS": "none",
            "SMTP_USERNAME": "",
            "LIVE_DELIVERY_ENABLED": False,
            "AUTH_EMAIL_ENABLED": True,
        }.items():
            monkeypatch.setattr(settings, key, value)
        assert signup(client).status_code == 202
        assert len(deliveries) == 1 and not settings.LIVE_DELIVERY_ENABLED
        message = BytesParser(policy=policy.default).parsebytes(deliveries[0])
        assert message["To"] == "owner@example.com"
        assert message.get_content_type() == "multipart/alternative"
        assert "Skilledhat" in message.get_body(preferencelist=("plain",)).get_content()
        html = message.get_body(preferencelist=("html",)).get_content()
        assert '<a href="http://localhost:4202/#/verify-email?token=' in html
        assert "Verify email address</a>" in html

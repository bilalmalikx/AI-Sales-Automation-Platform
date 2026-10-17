"""SMTP delivery; local mode writes MIME messages without contacting recipients."""

import asyncio
import smtplib
import ssl
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.core.exceptions import ExternalServiceException
from app.core.security import scoped_token
from app.providers.email_template import render_email


class DeliveryUncertainError(Exception):
    """SMTP may have accepted DATA; automatic retry could duplicate the message."""


def compose(draft, lead, sender: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = draft.subject
    message["From"] = formataddr(
        (
            settings.DEFAULT_FROM_NAME or sender,
            settings.DEFAULT_FROM_EMAIL or "salesway@localhost.test",
        )
    )
    message["To"] = lead.email
    domain = (settings.DEFAULT_FROM_EMAIL or "salesway@localhost.test").split("@")[1]
    message["Message-ID"] = f"<{draft.id}.{draft.revision}@{domain}>"
    unsubscribe = f"{settings.PUBLIC_BASE_URL}/api/v1/public/unsubscribe/{lead.id}?token={scoped_token(lead.id,'unsubscribe')}"
    message["List-Unsubscribe"] = f"<{unsubscribe}>"
    message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    message.set_content(draft.body + f"\n\n{sender}\nStop outreach: {unsubscribe}\n")
    message.add_alternative(
        render_email(draft.subject, draft.body, sender, unsubscribe=unsubscribe), subtype="html"
    )
    return message


def compose_verification(recipient: str) -> EmailMessage:
    sender = settings.DEFAULT_FROM_NAME or "Codelps team"
    message = EmailMessage()
    message["From"] = formataddr((sender, settings.DEFAULT_FROM_EMAIL or "salesway@localhost.test"))
    message["To"] = recipient
    message["Subject"] = "Your Codelps email delivery check"
    message["Message-ID"] = make_msgid()
    body = "Your test email is here.\n\nThis message checks the email connection for your Codelps Salesway workspace.\n\nThis is a verification message only. No customer outreach was sent."
    stamp = datetime.now(UTC).strftime("%d %B %Y, %H:%M UTC")
    reference = uuid4().hex[:12].upper()
    message.set_content(body + f"\n\nSent at: {stamp}\nReference: {reference}\n")
    message.add_alternative(
        render_email(
            "Your test email is here.",
            body.split("\n\n", 1)[1],
            sender,
            label="EMAIL CONNECTION CHECK",
            details=[
                ("Purpose", "Delivery verification"),
                ("Sent at", stamp),
                ("Reference", reference),
            ],
        ),
        subtype="html",
    )
    return message


def _smtp_connect():
    if not settings.SMTP_HOST:
        raise ExternalServiceException("SMTP host is not configured")
    if settings.SMTP_TLS == "ssl":
        smtp = smtplib.SMTP_SSL(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=settings.SMTP_TIMEOUT_SECONDS,
            context=ssl.create_default_context(),
        )
    else:
        smtp = smtplib.SMTP(
            settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SECONDS
        )
    try:
        smtp.ehlo()
        if settings.SMTP_TLS == "starttls":
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        return smtp
    except Exception:
        smtp.close()
        raise


async def check_connection() -> dict:
    """Verify TLS/authentication without submitting any message or enabling delivery."""

    def check():
        smtp = None
        try:
            smtp = _smtp_connect()
            code, _ = smtp.noop()
            if code != 250:
                raise ExternalServiceException("SMTP readiness check was rejected")
            return {
                "status": "connected",
                "message": "SMTP connection and authentication verified. No email sent.",
            }
        except smtplib.SMTPAuthenticationError:
            return {
                "status": "failed",
                "message": "SMTP authentication failed. Check username and app password.",
            }
        except Exception:
            return {
                "status": "failed",
                "message": "SMTP connection failed. Check host, port, TLS and network access.",
            }
        finally:
            if smtp:
                try:
                    smtp.quit()
                except Exception:
                    smtp.close()

    return await asyncio.to_thread(check)


def _smtp_send(message: EmailMessage) -> str:
    if not settings.LIVE_DELIVERY_ENABLED:
        raise ExternalServiceException("Live email delivery is disabled")
    smtp = None
    data_started = False
    try:
        smtp = _smtp_connect()
        data_started = True
        refused = smtp.send_message(message)
        if refused:
            raise ExternalServiceException("SMTP rejected the recipient")
        return str(message["Message-ID"])
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPDataError) as exc:
        raise ExternalServiceException("SMTP rejected delivery") from exc
    except Exception as exc:
        if data_started:
            raise DeliveryUncertainError(
                "SMTP acceptance could not be confirmed; reconcile before retrying"
            ) from exc
        raise ExternalServiceException("SMTP connection or authentication failed") from exc
    finally:
        if smtp:
            try:
                smtp.quit()
            except Exception:
                smtp.close()


async def deliver(draft, lead, sender: str) -> str:
    message = compose(draft, lead, sender)
    if settings.EMAIL_PROVIDER == "local":
        directory = Path(settings.LOCAL_MAIL_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{draft.id}.{draft.revision}.eml"
        # Stable file names make crash recovery idempotent for the local provider.
        await asyncio.to_thread(path.write_bytes, message.as_bytes())
        return str(message["Message-ID"])
    return await asyncio.to_thread(_smtp_send, message)

"""SMTP delivery; local mode writes MIME messages without contacting recipients."""

import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import ExternalServiceException
from app.core.security import scoped_token


class DeliveryUncertainError(Exception):
    """SMTP may have accepted DATA; automatic retry could duplicate the message."""


def compose(draft, lead, sender: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = draft.subject
    message["From"] = settings.DEFAULT_FROM_EMAIL or "salesway@localhost.test"
    message["To"] = lead.email
    domain = (settings.DEFAULT_FROM_EMAIL or "salesway@localhost.test").split("@")[1]
    message["Message-ID"] = f"<{draft.id}.{draft.revision}@{domain}>"
    unsubscribe = f"{settings.PUBLIC_BASE_URL}/api/v1/public/unsubscribe/{lead.id}?token={scoped_token(lead.id,'unsubscribe')}"
    message["List-Unsubscribe"] = f"<{unsubscribe}>"
    message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    message.set_content(draft.body + f"\n\n{sender}\nStop outreach: {unsubscribe}\n")
    return message


def _smtp_send(message: EmailMessage) -> str:
    if not settings.LIVE_DELIVERY_ENABLED:
        raise ExternalServiceException("Live email delivery is disabled")
    smtp = None
    data_started = False
    try:
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
            if settings.SMTP_TLS == "starttls":
                smtp.starttls(context=ssl.create_default_context())
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
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

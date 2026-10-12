"""Check configured SMTP and optionally send one fixed verification email to the sender itself."""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.providers.email import _smtp_send, check_connection


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send-to-self", action="store_true")
    args = parser.parse_args()
    result = await check_connection()
    if result["status"] == "connected" and args.send_to_self:
        if not settings.DEFAULT_FROM_EMAIL:
            result = {"status": "failed", "message": "Sender address is required."}
        else:
            settings.EMAIL_PROVIDER = "smtp"
            settings.LIVE_DELIVERY_ENABLED = (
                True  # This process only; no pending jobs are executed.
            )
            message = EmailMessage()
            message["From"] = formataddr(
                (settings.DEFAULT_FROM_NAME or "Codelps Team", settings.DEFAULT_FROM_EMAIL)
            )
            message["To"] = settings.DEFAULT_FROM_EMAIL
            message["Subject"] = "Codelps Salesway — SMTP verification"
            message["Message-ID"] = make_msgid()
            message.set_content(
                f"This is your requested Salesway SMTP test.\nUTC time: {datetime.now(UTC).isoformat()}\nNo customer outreach was sent."
            )
            try:
                await asyncio.to_thread(_smtp_send, message)
                result = {
                    "status": "accepted",
                    "message": "SMTP server accepted one test message addressed to the configured sender. Inbox receipt is not yet confirmed.",
                }
            except Exception as exc:
                result = {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "message": "SMTP test delivery was not confirmed.",
                }
    print(json.dumps(result))  # noqa: T201
    return 0 if result["status"] in {"connected", "accepted"} else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

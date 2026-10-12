"""Read-only TLS IMAP batches and MIME parsing. No mailbox writes or automatic replies."""

import hashlib
import imaplib
import re
import ssl
from contextlib import suppress
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
from html.parser import HTMLParser

from app.core.config import settings
from app.core.exceptions import ExternalServiceException

MAX_BYTES = 1_000_000


class ReplyText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"p", "div", "br", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def mailbox_key() -> str:
    value = (
        f"{settings.IMAP_HOST}:{settings.IMAP_PORT}/{settings.IMAP_USERNAME}/{settings.IMAP_FOLDER}"
    )
    return hashlib.sha256(value.encode()).hexdigest()


def fetch_batch(validity: str, last_uid: int) -> tuple[str, list[tuple[int, bytes | None]]]:
    connection = imaplib.IMAP4_SSL(
        settings.IMAP_HOST,
        settings.IMAP_PORT,
        ssl_context=ssl.create_default_context(),
        timeout=settings.IMAP_TIMEOUT_SECONDS,
    )
    try:
        connection.login(settings.IMAP_USERNAME, settings.IMAP_PASSWORD)
        status, _ = connection.select(settings.IMAP_FOLDER, readonly=True)
        if status != "OK":
            raise ExternalServiceException("IMAP folder unavailable")
        _, data = connection.response("UIDVALIDITY")
        current = data[0].decode() if data and data[0] else ""
        if not current:
            raise ExternalServiceException("IMAP UIDVALIDITY unavailable")
        first = last_uid + 1 if current == validity else 1
        status, data = connection.uid("search", None, f"UID {first}:*")
        if status != "OK":
            raise ExternalServiceException("IMAP search failed")
        # Some servers return the last message for n:* when n exceeds the final UID.
        uids = sorted(int(uid) for uid in (data[0] or b"").split() if int(uid) >= first)[:50]
        result = []
        for uid in uids:
            status, data = connection.uid("fetch", str(uid), "(RFC822.SIZE)")
            metadata = b" ".join(part for part in (data or []) if isinstance(part, bytes))
            size = re.search(rb"RFC822.SIZE\s+(\d+)", metadata)
            if status != "OK" or not size:
                raise ExternalServiceException("IMAP message size unavailable")
            if int(size.group(1)) > MAX_BYTES:
                result.append((uid, None))
                continue
            status, data = connection.uid("fetch", str(uid), "(BODY.PEEK[])")
            if status != "OK":
                raise ExternalServiceException("IMAP message fetch failed")
            raw = next((part[1] for part in data if isinstance(part, tuple)), None)
            if raw is None:
                raise ExternalServiceException("IMAP message disappeared; retry batch")
            result.append((uid, raw if len(raw) <= MAX_BYTES else None))
        return current, result
    finally:
        with suppress(Exception):
            connection.logout()


def parse_reply(raw: bytes) -> dict | None:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    # Automatic responses and delivery reports are not customer replies.
    if str(message.get("Auto-Submitted", "no")).lower() != "no":
        return None
    if str(message.get("Precedence", "")).lower() in {"bulk", "list", "junk"}:
        return None
    if message.get_content_type() == "multipart/report":
        return None
    references = re.findall(r"<[^<>\s]+>", str(message.get("In-Reply-To", "")))
    references += list(reversed(re.findall(r"<[^<>\s]+>", str(message.get("References", "")))))
    body = message.get_body(preferencelist=("plain", "html"))
    if not references or body is None:
        return None
    try:
        content = body.get_content()
    except (LookupError, ValueError):
        return None
    if not isinstance(content, str) or not content.strip():
        return None
    if body.get_content_type() == "text/html":
        parser = ReplyText()
        parser.feed(content)
        content = "".join(parser.parts)
    text = content.strip()[:20000]
    if not text:
        return None
    # Only explicit first-line opt-out commands are classified automatically.
    first_line = text.splitlines()[0].strip().lower().rstrip(".! ")
    intent = (
        "unsubscribe"
        if first_line in {"unsubscribe", "remove me", "stop emailing me"}
        else "question"
    )
    return {
        "sender": parseaddr(str(message.get("From", "")))[1].lower(),
        "references": references[:100],
        "body": text,
        "intent": intent,
    }

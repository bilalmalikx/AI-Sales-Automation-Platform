"""Import replies matched to sent Message-IDs, with durable per-mailbox deduplication."""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.db.engine import get_engine
from app.models.domain import Lead
from app.models.sales import EmailDraft, MailboxSync
from app.providers import inbox
from app.repositories.sales import SalesRepository
from app.schemas.sales import WebhookInput
from app.services.sales import SalesService, now


async def sync_inbox() -> dict:
    if not settings.IMAP_ENABLED:
        return {"status": "disabled", "processed": 0}
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    key = inbox.mailbox_key()
    async with factory() as db:
        # Serialize sync sessions, including simultaneous beat and manual requests.
        await SalesRepository(db).settings(lock=True)
        cursor = await db.get(MailboxSync, key)
        if cursor is None:
            cursor = MailboxSync(id=key, uid_validity="", last_uid=0, status="idle")
            db.add(cursor)
            await db.flush()
        try:
            validity, batch = await asyncio.to_thread(
                inbox.fetch_batch, cursor.uid_validity, cursor.last_uid
            )
        except Exception:
            cursor.status = "failed"
            cursor.checked_at = now()
            cursor.error = "Inbox sync failed. Check IMAP host, credentials and folder."
            await db.commit()
            return {"status": "failed", "processed": 0, "message": cursor.error}
        if validity != cursor.uid_validity:
            cursor.last_uid = 0
            cursor.uid_validity = validity
        # Network retrieval is complete before committing any checkpoints.
        await db.commit()
    processed = 0
    for uid, raw in batch:
        async with factory() as db:
            await SalesRepository(db).settings(lock=True)
            cursor = await db.get(MailboxSync, key, with_for_update=True)
            if cursor.uid_validity != validity or uid <= cursor.last_uid:
                continue
            reply = inbox.parse_reply(raw) if raw else None
            draft = None
            if reply:
                for reference in reply["references"]:
                    draft = await db.scalar(
                        select(EmailDraft)
                        .join(Lead, Lead.id == EmailDraft.lead_id)
                        .where(
                            EmailDraft.provider_message_id == reference,
                            EmailDraft.status == "sent",
                            Lead.email == reply["sender"],
                        )
                    )
                    if draft:
                        break
            if draft:
                await SalesService(db).webhook(
                    WebhookInput(
                        event_id=f"imap:{key}:{validity}:{uid}",
                        draft_id=draft.id,
                        kind="replied",
                        body=reply["body"],
                        intent=reply["intent"],
                    )
                )
                processed += 1
                # Webhook commits its event first; if checkpoint commit crashes it dedupes on retry.
                await SalesRepository(db).settings(lock=True)
                cursor = await db.get(MailboxSync, key, with_for_update=True)
            cursor.last_uid = max(cursor.last_uid, uid)
            cursor.checked_at = now()
            cursor.status = "synced"
            cursor.error = None
            await db.commit()
    async with factory() as db:
        await SalesRepository(db).settings(lock=True)
        cursor = await db.get(MailboxSync, key, with_for_update=True)
        cursor.checked_at = now()
        cursor.status = "synced"
        cursor.error = None
        await db.commit()
    return {"status": "synced", "processed": processed, "scanned": len(batch)}

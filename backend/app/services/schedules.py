"""Daily UTC discovery slots: durable, bounded, no catch-up burst or automatic email sends."""

from datetime import timedelta

from sqlalchemy import select

from app.core.exceptions import RateLimitException, ValidationException
from app.models.discovery import DiscoverySchedule
from app.repositories.sales import SalesRepository
from app.schemas.discovery import DiscoveryInput
from app.services.discovery import start
from app.services.sales import now


async def dispatch_due() -> int:
    from app.tasks.worker import sessions

    async with sessions()() as db:
        identifiers = (
            await db.scalars(
                select(DiscoverySchedule.id)
                .where(DiscoverySchedule.enabled.is_(True), DiscoverySchedule.due_at <= now())
                .order_by(DiscoverySchedule.due_at)
                .limit(20)
            )
        ).all()
    count = 0
    for identifier in identifiers:
        async with sessions()() as db:
            await SalesRepository(db).settings(lock=True)
            schedule = await db.get(DiscoverySchedule, identifier, with_for_update=True)
            if not schedule or not schedule.enabled or schedule.due_at > now():
                continue
            slot = schedule.due_at
            try:
                run = await start(
                    db,
                    DiscoveryInput.model_validate(schedule.parameters),
                    f"schedule:{schedule.id}:{slot.isoformat()}",
                    commit=False,
                )
                schedule.last_run_id = run.id
                schedule.error = None
                count += 1
            except (RateLimitException, ValidationException) as exc:
                schedule.error = exc.message[:300]
            schedule.last_checked_at = now()
            # Advance to the next future 24-hour slot, including after a server outage.
            days = max(1, int((now() - slot).total_seconds() // 86400) + 1)
            schedule.due_at = slot + timedelta(days=days)
            await db.commit()
    return count

"""Celery wakes the durable queue; broker loss cannot lose committed work."""

import asyncio

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "salesway", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    beat_schedule={"drain-sales-jobs": {"task": "salesway.drain", "schedule": 5.0}},
)


@celery_app.task(name="salesway.drain", acks_late=True)
def drain_jobs() -> int:
    async def execute():
        from app.db.engine import dispose_db, init_db
        from app.tasks.worker import drain

        await init_db()
        try:
            return await drain(20)
        finally:
            await dispose_db()

    return asyncio.run(execute())

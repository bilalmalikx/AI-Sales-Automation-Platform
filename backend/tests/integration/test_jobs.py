"""Crash recovery, checkpoints, retries and operator reconciliation."""

from datetime import timedelta
from uuid import UUID

from app.core.config import settings
from app.models.sales import EmailDraft, Job
from app.services.sales import now
from app.tasks import worker
from tests.api.test_sales import BASE, approve, campaign, future, lead, workflow


def test_workflow_failure_checkpoint_and_explicit_retry(client, drain, monkeypatch):
    lead_record = lead(client)
    c = campaign(client, [lead_record["id"]])
    original = worker.generate

    async def fail(lead, campaign, prefs, checkpoint, persist):
        await persist("enrichment", {"confidence_score": 0.8, "sources": ["test checkpoint"]})
        raise ConnectionError("provider unavailable")

    monkeypatch.setattr(settings, "WORKER_MAX_ATTEMPTS", 1)
    monkeypatch.setattr(worker, "generate", fail)
    response = client.post(
        BASE + "/workflows",
        json={"lead_id": lead_record["id"], "campaign_id": c["id"]},
        headers={"Idempotency-Key": "recovery-test"},
    )
    identifier = response.json()["id"]
    drain()
    run = client.get(BASE + f"/workflows/{identifier}").json()
    assert run["status"] == "failed" and "enrichment" in run["output"]
    job = client.get(BASE + "/jobs").json()["items"][0]
    assert job["status"] == "failed"
    monkeypatch.setattr(worker, "generate", original)
    assert client.post(BASE + f"/jobs/{job['id']}/retry").status_code == 200
    drain()
    run = client.get(BASE + f"/workflows/{identifier}").json()
    assert run["status"] == "needs_review"
    assert run["output"]["enrichment"]["sources"] == ["test checkpoint"]
    assert client.get(BASE + "/emails").json()["total"] == 1


def test_stale_smtp_job_recovers_without_duplicate_send(client, drain, monkeypatch):
    lead_record = lead(client)
    c = campaign(client, [lead_record["id"]])
    d = approve(client, workflow(client, drain, lead_record, c))
    client.post(BASE + f"/emails/{d['id']}/send")

    async def simulate_crash():
        from sqlalchemy import select

        async with worker.sessions()() as db:
            draft = await db.get(EmailDraft, UUID(d["id"]))
            draft.status = "sending"
            job = await db.scalar(select(Job).where(Job.kind == "email"))
            job.status = "processing"
            job.locked_at = now() - timedelta(seconds=settings.JOB_LEASE_SECONDS + 1)
            await db.commit()

    client.portal.call(simulate_crash)
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "smtp")
    drain()
    assert client.get(BASE + f"/emails/{d['id']}").json()["status"] == "delivery_unknown"
    assert (
        client.post(
            BASE + f"/emails/{d['id']}/reconcile", json={"action": "retry_with_duplicate_risk"}
        ).status_code
        == 422
    )
    result = client.post(BASE + f"/emails/{d['id']}/reconcile", json={"action": "confirmed_sent"})
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "sent"
    assert client.get(BASE + "/inbox").json()["total"] == 1


def test_calendar_failure_is_visible_and_retryable(client, drain, monkeypatch):
    from app.providers import calendar

    lead_record = lead(client)
    original = calendar.sync

    async def fail(*args):
        raise ConnectionError("provider unavailable")

    monkeypatch.setattr(calendar, "sync", fail)
    monkeypatch.setattr(settings, "WORKER_MAX_ATTEMPTS", 1)
    client.post(BASE + "/meetings", json={"lead_id": lead_record["id"], "start_at": future()})
    drain()
    assert client.get(BASE + "/meetings").json()["items"][0]["sync_status"] == "failed"
    job = client.get(BASE + "/jobs").json()["items"][0]
    assert job["status"] == "failed"
    monkeypatch.setattr(calendar, "sync", original)
    client.post(BASE + f"/jobs/{job['id']}/retry")
    drain()
    assert client.get(BASE + "/meetings").json()["items"][0]["sync_status"] == "synced"

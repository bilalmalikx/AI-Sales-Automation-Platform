"""Daily dispatch and budget reservations never repeat paid starts or send emails."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.core.config import settings
from app.models.discovery import DiscoveryRun
from app.services.schedules import dispatch_due
from app.tasks.worker import sessions

BASE = "/api/v1/discovery"
PARAMS = {
    "industry": "restaurants",
    "location": "London",
    "country": "GB",
    "limit": 5,
    "mode": "fresh",
    "generate_drafts": True,
}


def schedule(client, enabled=False, days_ago=0):
    return client.post(
        BASE + "/schedules",
        json={
            "name": "Codelps daily",
            "parameters": PARAMS,
            "enabled": enabled,
            "due_at": (datetime.now(UTC) - timedelta(days=days_ago, minutes=1)).isoformat(),
        },
    )


def test_paused_schedule_never_dispatches(client):
    response = schedule(client)
    assert response.status_code == 201
    assert client.portal.call(dispatch_due) == 0
    assert client.get(BASE + "/runs").json()["total"] == 0


def test_enabled_schedule_dispatches_once_and_skips_missed_days(client):
    response = schedule(client, enabled=True, days_ago=5)
    assert response.status_code == 201
    assert client.portal.call(dispatch_due) == 1
    assert client.portal.call(dispatch_due) == 0
    item = client.get(BASE + "/schedules").json()["items"][0]
    assert item["last_run_id"]
    assert datetime.fromisoformat(item["due_at"].replace("Z", "+00:00")) > datetime.now(UTC)
    assert client.get(BASE + "/runs").json()["total"] == 1
    assert client.get("/api/v1/emails").json()["total"] == 0


def test_daily_limit_holds_scheduled_search_with_visible_error(client, monkeypatch):
    monkeypatch.setattr(settings, "DISCOVERY_DAILY_LIMIT", 1)
    schedule(client, enabled=True)
    assert client.portal.call(dispatch_due) == 0
    item = client.get(BASE + "/schedules").json()["items"][0]
    assert "Daily discovery limit" in item["error"]
    assert item["last_run_id"] is None
    assert client.portal.call(dispatch_due) == 0


def test_monthly_budget_reserves_before_paid_start_and_keeps_unknown_spend(client, monkeypatch):
    monkeypatch.setattr(settings, "DISCOVERY_MONTHLY_BUDGET_USD", 0.5)
    a = client.post(BASE + "/runs", json=PARAMS, headers={"Idempotency-Key": "budget-a"})
    assert a.status_code == 202
    assert (
        client.post(BASE + "/runs", json=PARAMS, headers={"Idempotency-Key": "budget-a"}).json()[
            "id"
        ]
        == a.json()["id"]
    )
    assert (
        client.post(
            BASE + "/runs", json=PARAMS, headers={"Idempotency-Key": "budget-b"}
        ).status_code
        == 429
    )

    async def ambiguous_start():
        async with sessions()() as db:
            row = await db.get(DiscoveryRun, UUID(a.json()["id"]))
            row.status = "starting"
            await db.commit()

    client.portal.call(ambiguous_start)
    assert client.post(BASE + f"/runs/{a.json()['id']}/cancel").status_code == 200
    assert (
        client.post(
            BASE + "/runs", json=PARAMS, headers={"Idempotency-Key": "budget-c"}
        ).status_code
        == 429
    )
    assert client.get(BASE + "/configuration").json()["monthly_budget"]["committed_usd"] == 0.5


def test_completed_run_replaces_reservation_with_reported_charge(client, monkeypatch):
    monkeypatch.setattr(settings, "DISCOVERY_MONTHLY_BUDGET_USD", 0.6)
    run = client.post(BASE + "/runs", json=PARAMS, headers={"Idempotency-Key": "settled-a"}).json()

    async def complete():
        async with sessions()() as db:
            row = await db.get(DiscoveryRun, UUID(run["id"]))
            row.status = "completed"
            row.provider_cost = 0.02
            await db.commit()

    client.portal.call(complete)
    assert client.post(BASE + f"/runs/{run['id']}/cancel").json()["status"] == "completed"
    assert (
        client.post(
            BASE + "/runs", json=PARAMS, headers={"Idempotency-Key": "settled-b"}
        ).status_code
        == 202
    )
    budget = client.get(BASE + "/configuration").json()["monthly_budget"]
    assert budget["committed_usd"] == 0.52 and budget["reported_usd"] == 0.02


def test_cancelling_before_paid_start_releases_reservation(client, monkeypatch):
    monkeypatch.setattr(settings, "DISCOVERY_MONTHLY_BUDGET_USD", 0.5)
    run = client.post(BASE + "/runs", json=PARAMS, headers={"Idempotency-Key": "unused-a"}).json()
    assert client.post(BASE + f"/runs/{run['id']}/cancel").status_code == 200
    assert client.get(BASE + "/configuration").json()["monthly_budget"]["committed_usd"] == 0
    assert (
        client.post(
            BASE + "/runs", json=PARAMS, headers={"Idempotency-Key": "unused-b"}
        ).status_code
        == 202
    )


def test_schedule_budget_failure_and_pause_are_persisted(client, monkeypatch):
    monkeypatch.setattr(settings, "DISCOVERY_MONTHLY_BUDGET_USD", 0)
    item = schedule(client, enabled=True).json()
    assert client.portal.call(dispatch_due) == 0
    current = client.get(BASE + "/schedules").json()["items"][0]
    assert "Monthly Apify budget" in current["error"]
    response = client.put(
        BASE + f"/schedules/{item['id']}",
        json={
            "name": item["name"],
            "parameters": item["parameters"],
            "enabled": False,
            "due_at": current["due_at"],
        },
    )
    assert response.status_code == 200 and not response.json()["enabled"]
    assert client.portal.call(dispatch_due) == 0


def test_schedule_requires_explicit_timezone_and_auth(client, monkeypatch):
    assert (
        client.post(
            BASE + "/schedules",
            json={"name": "test", "parameters": PARAMS, "due_at": "2026-10-20T10:00:00"},
        ).status_code
        == 422
    )
    monkeypatch.setattr(settings, "API_TOKEN", "test-token")
    assert client.get(BASE + "/schedules").status_code == 401

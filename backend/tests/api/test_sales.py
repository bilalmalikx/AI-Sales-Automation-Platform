"""API and durable worker integration tests over real persisted records."""

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.config import settings

BASE = "/api/v1"


def lead(client, email="alex@example.com", **extra):
    response = client.post(
        BASE + "/leads",
        json={
            "email": email,
            "first_name": "Alex",
            "last_name": "Morgan",
            "company_name": "Example Studio",
            "title": "Founder",
            "industry": "Design",
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def campaign(client, ids, status="active"):
    response = client.post(
        BASE + "/campaigns",
        json={
            "name": "Studio growth",
            "audience": "Founders",
            "offer": "Help teams reduce repetitive reporting.",
            "lead_ids": ids,
        },
    )
    assert response.status_code == 201, response.text
    result = response.json()
    if status != "draft":
        response = client.patch(BASE + f"/campaigns/{result['id']}/status", json={"status": status})
        assert response.status_code == 200, response.text
        result = response.json()
    return result


def workflow(client, drain, lead_record, c, key=None):
    response = client.post(
        BASE + "/workflows",
        json={"lead_id": lead_record["id"], "campaign_id": c["id"]},
        headers={"Idempotency-Key": key or str(uuid4())},
    )
    assert response.status_code == 202, response.text
    identifier = response.json()["id"]
    drain()
    result = client.get(BASE + f"/workflows/{identifier}").json()
    assert result["status"] == "needs_review", result
    return client.get(BASE + f"/emails/{result['output']['draft_id']}").json()


def approve(client, d):
    response = client.post(
        BASE + f"/emails/{d['id']}/approve",
        json={"expected_revision": d["revision"], "acknowledge_low_confidence": True},
    )
    assert response.status_code == 200, response.text
    return response.json()


def webhook(client, draft, kind="replied", event=None, body="Sounds interesting"):
    payload = json.dumps(
        {
            "event_id": event or str(uuid4()),
            "draft_id": draft["id"],
            "kind": kind,
            "body": body,
            "intent": "interested",
        }
    ).encode()
    stamp = str(int(time.time()))
    signature = hmac.new(
        settings.WEBHOOK_SECRET.encode(), stamp.encode() + b"." + payload, hashlib.sha256
    ).hexdigest()
    return client.post(
        BASE + "/webhooks/email",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Timestamp": stamp,
            "X-Webhook-Signature": signature,
        },
    )


def future(days=3, hour=10):
    return (
        (datetime.now(UTC) + timedelta(days=days))
        .replace(hour=hour, minute=0, second=0, microsecond=0)
        .isoformat()
    )


class TestLeads:
    def test_crud_and_normalized_duplicates(self, client):
        lead_record = lead(client, email="Alex@Example.com")
        assert lead_record["email"] == "alex@example.com"
        assert lead_record["company_name"] == "Example Studio"
        assert lead_record["industry"] == "Design"
        assert client.post(BASE + "/leads", json={"email": "ALEX@example.com"}).status_code == 409
        assert (
            client.put(BASE + f"/leads/{lead_record['id']}", json={"status": "replied"}).json()[
                "status"
            ]
            == "replied"
        )
        assert (
            client.get(BASE + "/leads", params={"email": "alex", "page_size": 1}).json()["total"]
            == 1
        )
        assert client.delete(BASE + f"/leads/{lead_record['id']}").status_code == 204
        assert client.get(BASE + f"/leads/{lead_record['id']}").status_code == 404

    def test_email_only_and_validation_errors(self, client):
        assert client.post(BASE + "/leads", json={"email": "only@example.com"}).status_code == 201
        for payload in [{"email": "invalid"}, {"email": "ok@example.com", "status": "random"}]:
            response = client.post(BASE + "/leads", json=payload)
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert client.get(BASE + "/leads", params={"page_size": 101}).status_code == 422

    def test_csv_quotes_statistics_and_atomic_strict_import(self, client):
        lead(client)
        content = 'name,email,company\n"Taylor, Jr",taylor@example.com,"Studio, Inc"\nAlex,alex@example.com,X\nBad,noemail,X\n'
        result = client.post(
            BASE + "/leads/import/csv", files={"file": ("leads.csv", content, "text/csv")}
        )
        assert result.status_code == 201, result.text
        assert result.json()["statistics"]["created"] == 1
        assert result.json()["statistics"]["skipped"] == 1
        assert result.json()["statistics"]["failed"] == 1
        strict = "email,company_name\nnew@example.com,New\nalex@example.com,Old\n"
        response = client.post(
            BASE + "/leads/import/csv?skip_duplicates=false", files={"file": ("leads.csv", strict)}
        )
        assert response.status_code == 422, response.text
        assert client.get(BASE + "/leads", params={"email": "new@example.com"}).json()["total"] == 0

    def test_csv_limits_and_safe_export(self, client, monkeypatch):
        monkeypatch.setattr(settings, "MAX_CSV_BYTES", 20)
        assert (
            client.post(
                BASE + "/leads/import/csv", files={"file": ("x.csv", "email\n" + "x" * 30)}
            ).status_code
            == 422
        )
        lead_record = lead(client, first_name="=FORMULA()")
        response = client.get(BASE + "/leads/export/csv")
        assert response.status_code == 200, response.text
        assert "'=FORMULA()" in response.text
        assert lead_record["id"] in response.text

    def test_optout_cannot_be_overridden_by_crm(self, client):
        lead_record = lead(client)
        assert client.post(BASE + f"/leads/{lead_record['id']}/unsubscribe").status_code == 200
        assert (
            client.put(BASE + f"/leads/{lead_record['id']}", json={"status": "new"}).status_code
            == 409
        )


class TestSalesWorkflow:
    def test_complete_lead_to_meeting(self, client, drain):
        lead_record = lead(client)
        c = campaign(client, [lead_record["id"]])
        d = workflow(client, drain, lead_record, c)
        assert client.post(BASE + f"/emails/{d['id']}/send").status_code == 409
        d = approve(client, d)
        assert client.post(BASE + f"/emails/{d['id']}/send").status_code == 202
        drain()
        sent = client.get(BASE + f"/emails/{d['id']}").json()
        assert sent["status"] == "sent", sent
        assert sent["provider_message_id"]
        assert webhook(client, d).status_code == 200
        assert client.get(BASE + f"/leads/{lead_record['id']}").json()["status"] == "replied"
        meeting = client.post(
            BASE + "/meetings",
            json={"lead_id": lead_record["id"], "start_at": future(), "timezone": "Asia/Karachi"},
        )
        assert meeting.status_code == 201, meeting.text
        drain()
        assert client.get(BASE + "/meetings").json()["items"][0]["sync_status"] == "synced"
        analytics = client.get(BASE + "/analytics").json()
        assert (
            analytics["emails_sent"] == 1
            and analytics["replies"] == 1
            and analytics["meetings"] == 1
        )
        assert client.get(BASE + f"/campaigns/{c['id']}").json()["sent"] == 1
        assert client.get(BASE + "/analytics/export").status_code == 200

    def test_workflow_idempotency_and_membership(self, client, drain):
        lead_record = lead(client)
        other = lead(client, "other@example.com")
        c = campaign(client, [lead_record["id"]])
        data = {"lead_id": lead_record["id"], "campaign_id": c["id"]}
        headers = {"Idempotency-Key": "stable-key"}
        first = client.post(BASE + "/workflows", json=data, headers=headers)
        second = client.post(BASE + "/workflows", json=data, headers=headers)
        assert first.json()["id"] == second.json()["id"]
        assert (
            client.post(
                BASE + "/workflows", json={**data, "lead_id": other["id"]}, headers=headers
            ).status_code
            == 409
        )
        assert (
            client.post(
                BASE + "/workflows",
                json={**data, "lead_id": other["id"]},
                headers={"Idempotency-Key": "other"},
            ).status_code
            == 422
        )
        drain()
        assert client.get(BASE + "/emails").json()["total"] == 1

    def test_edit_invalidates_approval_and_stale_revision(self, client, drain):
        lead_record = lead(client)
        c = campaign(client, [lead_record["id"]])
        d = workflow(client, drain, lead_record, c)
        approve(client, d)
        assert (
            client.post(
                BASE + f"/emails/{d['id']}/approve", json={"expected_revision": 1}
            ).status_code
            == 422
        )
        edited = client.put(
            BASE + f"/emails/{d['id']}",
            json={"subject": "Better subject", "body": "Better message", "expected_revision": 1},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["revision"] == 2 and edited.json()["status"] == "needs_review"
        assert (
            client.post(
                BASE + f"/emails/{d['id']}/approve",
                json={"expected_revision": 1, "acknowledge_low_confidence": True},
            ).status_code
            == 409
        )
        assert client.post(BASE + f"/emails/{d['id']}/send").status_code == 409

    def test_daily_limit_and_idempotent_send(self, client, drain):
        prefs = client.get(BASE + "/settings").json()
        prefs["daily_limit"] = 1
        assert client.put(BASE + "/settings", json=prefs).status_code == 200
        lead_record = lead(client)
        c = campaign(client, [lead_record["id"]])
        d = approve(client, workflow(client, drain, lead_record, c))
        assert client.post(BASE + f"/emails/{d['id']}/send").status_code == 202
        assert client.post(BASE + f"/emails/{d['id']}/send").status_code == 202
        second = approve(client, workflow(client, drain, lead_record, c))
        assert client.post(BASE + f"/emails/{second['id']}/send").status_code == 429
        drain()
        assert client.get(BASE + "/inbox").json()["total"] == 1

    def test_pause_and_unsubscribe_stop_queued_email(self, client, drain):
        lead_record = lead(client)
        c = campaign(client, [lead_record["id"]])
        d = approve(client, workflow(client, drain, lead_record, c))
        client.patch(BASE + f"/campaigns/{c['id']}/status", json={"status": "paused"})
        assert client.post(BASE + f"/emails/{d['id']}/send").status_code == 409
        client.patch(BASE + f"/campaigns/{c['id']}/status", json={"status": "active"})
        client.post(BASE + f"/emails/{d['id']}/send")
        client.post(BASE + f"/leads/{lead_record['id']}/unsubscribe")
        drain()
        assert client.get(BASE + f"/emails/{d['id']}").json()["status"] == "cancelled"
        assert client.get(BASE + "/analytics").json()["emails_sent"] == 0

    def test_lead_delete_cascades(self, client, drain):
        lead_record = lead(client)
        c = campaign(client, [lead_record["id"]])
        workflow(client, drain, lead_record, c)
        client.delete(BASE + f"/leads/{lead_record['id']}")
        assert client.get(BASE + "/emails").json()["total"] == 0
        assert client.get(BASE + "/workflows").json()["total"] == 0
        assert client.get(BASE + f"/campaigns/{c['id']}").json()["lead_ids"] == []


class TestMeetingsAndFollowups:
    def test_overlap_reschedule_cancel_and_timezone(self, client, drain):
        lead_record = lead(client)
        start = future()
        data = {"lead_id": lead_record["id"], "start_at": start, "duration_minutes": 30}
        first = client.post(BASE + "/meetings", json=data)
        assert first.status_code == 201, first.text
        assert client.post(BASE + "/meetings", json=data).status_code == 409
        adjacent = {
            **data,
            "start_at": (datetime.fromisoformat(start) + timedelta(minutes=30)).isoformat(),
        }
        assert client.post(BASE + "/meetings", json=adjacent).status_code == 201
        identifier = first.json()["id"]
        assert (
            client.put(
                BASE + f"/meetings/{identifier}", json={**data, "start_at": future(4)}
            ).status_code
            == 200
        )
        assert client.post(BASE + f"/meetings/{identifier}/cancel").status_code == 200
        drain()
        assert client.get(BASE + "/meetings").json()["total"] == 2
        assert (
            client.post(
                BASE + "/meetings", json={**data, "start_at": "2099-01-01T10:00:00"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                BASE + "/meetings", json={**data, "timezone": "Invalid/Timezone"}
            ).status_code
            == 422
        )

    def test_due_followup_generates_review_draft_once(self, client, drain):
        lead_record = lead(client, status="contacted")
        c = campaign(client, [lead_record["id"]])
        result = client.post(
            BASE + "/followups",
            json={"lead_id": lead_record["id"], "campaign_id": c["id"], "due_at": future()},
        )
        assert result.status_code == 201, result.text

        async def make_due():
            from uuid import UUID

            from app.models.sales import Followup
            from app.tasks.worker import sessions

            async with sessions()() as db:
                f = await db.get(Followup, UUID(result.json()["id"]))
                f.due_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
                await db.commit()

        client.portal.call(make_due)
        drain()
        drain()
        assert client.get(BASE + "/emails").json()["total"] == 1
        assert client.get(BASE + "/emails").json()["items"][0]["status"] == "needs_review"
        assert client.get(BASE + "/followups").json()["items"][0]["status"] == "ready_for_review"

    def test_unsubscribe_cancels_followup_and_prevents_booking(self, client):
        lead_record = lead(client, status="contacted")
        c = campaign(client, [lead_record["id"]])
        assert (
            client.post(
                BASE + "/followups",
                json={"lead_id": lead_record["id"], "campaign_id": c["id"], "due_at": future()},
            ).status_code
            == 201
        )
        client.post(BASE + f"/leads/{lead_record['id']}/unsubscribe")
        assert client.get(BASE + "/followups").json()["items"][0]["status"] == "cancelled"
        assert (
            client.post(
                BASE + "/meetings", json={"lead_id": lead_record["id"], "start_at": future()}
            ).status_code
            == 409
        )


class TestSecurityAndInbox:
    def test_auth_required_when_configured(self, client, monkeypatch):
        monkeypatch.setattr(settings, "API_TOKEN", "test-api-token")
        assert client.get(BASE + "/leads").status_code == 401
        assert (
            client.get(BASE + "/leads", headers={"Authorization": "Bearer wrong"}).status_code
            == 401
        )
        assert (
            client.get(
                BASE + "/leads", headers={"Authorization": "Bearer test-api-token"}
            ).status_code
            == 200
        )
        assert client.get("/health/live").status_code == 200

    def test_signed_webhook_and_deduplication(self, client, drain):
        lead_record = lead(client)
        c = campaign(client, [lead_record["id"]])
        d = workflow(client, drain, lead_record, c)
        response = webhook(client, d, event="event-1")
        assert response.status_code == 200, response.text
        assert webhook(client, d, event="event-1").json()["status"] == "duplicate"
        assert client.get(BASE + "/inbox").json()["total"] == 1
        assert (
            client.post(
                BASE + "/webhooks/email",
                json={},
                headers={
                    "X-Webhook-Timestamp": str(int(time.time())),
                    "X-Webhook-Signature": "bad",
                },
            ).status_code
            == 401
        )
        assert webhook(client, d, kind="opened").status_code == 200
        assert client.get(BASE + f"/emails/{d['id']}").json()["opened_at"]

    def test_manual_reply_saved_then_explicit_send(self, client, drain):
        lead_record = lead(client, status="replied")
        campaign(client, [lead_record["id"]])
        response = client.post(
            BASE + f"/inbox/{lead_record['id']}/reply", json={"body": "Thanks, let's talk."}
        )
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "approved"
        assert client.post(BASE + f"/emails/{response.json()['id']}/send").status_code == 202
        drain()
        assert client.get(BASE + "/analytics").json()["emails_sent"] == 1
        assert client.post(BASE + f"/inbox/{lead_record['id']}/suggest").status_code == 200

    def test_settings_search_notifications_and_integrations(self, client):
        lead(client)
        assert client.get(BASE + "/search?q=Alex").json()["leads"]
        assert client.get(BASE + "/notifications").status_code == 200
        assert client.get(BASE + "/activity").json()["total"] > 0
        assert client.get(BASE + "/pipeline").json()["new"] == 1
        assert client.get(BASE + "/integrations").json()["live_delivery_enabled"] is False
        prefs = client.get(BASE + "/settings").json()
        prefs["timezone"] = "Wrong/Zone"
        assert client.put(BASE + "/settings", json=prefs).status_code == 422


def test_unsubscribe_suppression_survives_delete_and_import(client):
    original = lead(client)
    client.post(BASE + f"/leads/{original['id']}/unsubscribe")
    client.delete(BASE + f"/leads/{original['id']}")
    recreated = lead(client)
    assert recreated["status"] == "unsubscribed"
    client.delete(BASE + f"/leads/{recreated['id']}")
    response = client.post(
        BASE + "/leads/import/csv", files={"file": ("x.csv", "email\nalex@example.com\n")}
    )
    assert response.status_code == 201, response.text
    assert client.get(BASE + "/leads").json()["items"][0]["status"] == "unsubscribed"


def test_public_unsubscribe_token_and_no_get_side_effect(client):
    from uuid import UUID

    from app.core.security import scoped_token

    lead_record = lead(client)
    url = BASE + f"/public/unsubscribe/{lead_record['id']}"
    assert client.post(url + "?token=wrong").status_code == 401
    token = scoped_token(UUID(lead_record["id"]), "unsubscribe")
    confirmation = client.get(url, params={"token": token})
    assert confirmation.status_code == 200
    assert 'method="post"' in confirmation.text
    assert client.get(BASE + f"/leads/{lead_record['id']}").json()["status"] == "new"
    assert client.post(url, params={"token": token}).status_code == 200
    assert client.get(BASE + f"/leads/{lead_record['id']}").json()["status"] == "unsubscribed"


def test_paused_worker_cancellation_can_be_reapproved(client, drain):
    contact = lead(client)
    c = campaign(client, [contact["id"]])
    d = approve(client, workflow(client, drain, contact, c))
    client.post(BASE + f"/emails/{d['id']}/send")
    client.patch(BASE + f"/campaigns/{c['id']}/status", json={"status": "paused"})
    drain()
    cancelled = client.get(BASE + f"/emails/{d['id']}").json()
    assert cancelled["status"] == "cancelled"
    client.patch(BASE + f"/campaigns/{c['id']}/status", json={"status": "active"})
    renewed = approve(client, cancelled)
    assert renewed["revision"] == cancelled["revision"] + 1
    assert client.post(BASE + f"/emails/{d['id']}/send").status_code == 202
    drain()
    assert client.get(BASE + f"/emails/{d['id']}").json()["status"] == "sent"
    assert client.get(BASE + "/inbox").json()["total"] == 1


def test_crm_optout_persists_suppression_and_cancels_queue(client, drain):
    contact = lead(client)
    c = campaign(client, [contact["id"]])
    d = approve(client, workflow(client, drain, contact, c))
    client.post(BASE + f"/emails/{d['id']}/send")
    assert (
        client.put(BASE + f"/leads/{contact['id']}", json={"status": "unsubscribed"}).status_code
        == 200
    )
    assert client.get(BASE + f"/emails/{d['id']}").json()["status"] == "cancelled"
    client.delete(BASE + f"/leads/{contact['id']}")
    assert lead(client)["status"] == "unsubscribed"

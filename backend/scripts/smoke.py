"""Exercise a running local-provider API and its real asynchronous workers."""

import argparse
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://localhost:8000")
parser.add_argument("--token", default="")
parser.add_argument("--webhook-secret", default="local-development-webhook-secret")
args = parser.parse_args()
client = httpx.Client(
    base_url=args.url,
    timeout=15,
    headers={"Authorization": f"Bearer {args.token}"} if args.token else {},
)


def call(method, path, **kwargs):
    response = client.request(method, "/api/v1" + path, **kwargs)
    response.raise_for_status()
    return response.json()


def wait(path, predicate):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        data = call("GET", path)
        if predicate(data):
            return data
        time.sleep(1)
    raise RuntimeError(f"Worker did not complete {path}: {data}")


assert client.get("/health/ready").status_code == 200
assert (
    call("GET", "/integrations")["email"]["provider"] == "local"
), "Smoke test requires local delivery"
tag = uuid4().hex[:10]
lead = call(
    "POST",
    "/leads",
    json={
        "email": f"smoke-{tag}@example.com",
        "first_name": "Smoke",
        "company_name": "Test Studio",
    },
)
campaign = call(
    "POST",
    "/campaigns",
    json={
        "name": f"Smoke {tag}",
        "audience": "Studio founders",
        "offer": "Reduce repetitive reporting",
        "lead_ids": [lead["id"]],
    },
)
call("PATCH", f"/campaigns/{campaign['id']}/status", json={"status": "active"})
run = call(
    "POST",
    "/workflows",
    json={"lead_id": lead["id"], "campaign_id": campaign["id"]},
    headers={"Idempotency-Key": f"smoke-{tag}"},
)
run = wait(f"/workflows/{run['id']}", lambda x: x["status"] == "needs_review")
draft = call("GET", f"/emails/{run['output']['draft_id']}")
call(
    "POST",
    f"/emails/{draft['id']}/approve",
    json={"expected_revision": draft["revision"], "acknowledge_low_confidence": True},
)
call("POST", f"/emails/{draft['id']}/send")
draft = wait(f"/emails/{draft['id']}", lambda x: x["status"] == "sent")
followup = call(
    "POST",
    "/followups",
    json={
        "lead_id": lead["id"],
        "campaign_id": campaign["id"],
        "due_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
    },
)
body = json.dumps(
    {
        "event_id": f"smoke-reply-{tag}",
        "draft_id": draft["id"],
        "kind": "replied",
        "body": "Interested in a discovery call",
        "intent": "interested",
    }
).encode()
stamp = str(int(time.time()))
signature = hmac.new(
    args.webhook_secret.encode(), stamp.encode() + b"." + body, hashlib.sha256
).hexdigest()
call(
    "POST",
    "/webhooks/email",
    content=body,
    headers={
        "Content-Type": "application/json",
        "X-Webhook-Timestamp": stamp,
        "X-Webhook-Signature": signature,
    },
)
assert call("GET", f"/leads/{lead['id']}")["status"] == "replied"
assert (
    next(x for x in call("GET", "/followups")["items"] if x["id"] == followup["id"])["status"]
    == "cancelled"
)
# Unique smoke time avoids existing meetings; all dates are explicitly UTC.
start = datetime.now(UTC) + timedelta(days=10, seconds=int(tag[:5], 16))
meeting = call(
    "POST",
    "/meetings",
    json={"lead_id": lead["id"], "start_at": start.isoformat(), "timezone": "Asia/Karachi"},
)
wait(
    "/meetings",
    lambda x: any(m["id"] == meeting["id"] and m["sync_status"] == "synced" for m in x["items"]),
)
call(
    "PUT",
    f"/meetings/{meeting['id']}",
    json={
        "lead_id": lead["id"],
        "start_at": (start + timedelta(hours=1)).isoformat(),
        "timezone": "Asia/Karachi",
    },
)
wait(
    "/meetings",
    lambda x: any(
        m["id"] == meeting["id"] and m["sync_status"] == "synced" and m["revision"] == 2
        for m in x["items"]
    ),
)
call("POST", f"/meetings/{meeting['id']}/cancel")
wait(
    "/meetings",
    lambda x: any(
        m["id"] == meeting["id"] and m["sync_status"] == "synced" and m["status"] == "cancelled"
        for m in x["items"]
    ),
)
assert call("GET", "/analytics")["emails_sent"] >= 1
call("POST", f"/leads/{lead['id']}/unsubscribe")
assert call("GET", f"/leads/{lead['id']}")["status"] == "unsubscribed"
print(  # noqa: T201 -- CLI verification output
    json.dumps(
        {
            "status": "passed",
            "workflow_id": run["id"],
            "draft_id": draft["id"],
            "meeting_id": meeting["id"],
            "checks": [
                "readiness",
                "lead",
                "campaign",
                "durable AI workflow",
                "review approval",
                "worker email",
                "signed reply",
                "followup cancellation",
                "meeting create/reschedule/cancel",
                "analytics",
                "unsubscribe",
            ],
        },
        indent=2,
    )
)
client.close()

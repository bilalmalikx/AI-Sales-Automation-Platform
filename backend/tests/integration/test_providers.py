"""Live adapter contracts: real local SMTP protocol and mocked Google HTTP endpoints."""

import socketserver
import threading
from contextlib import contextmanager

import httpx

from app.core.config import settings
from app.providers import calendar, email
from tests.api.test_sales import BASE, approve, campaign, future, lead, workflow


@contextmanager
def smtp_server():
    deliveries = []

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.wfile.write(b"220 localhost test SMTP\r\n")
            self.wfile.flush()
            data = []
            receiving = False
            while True:
                line = self.rfile.readline()
                if not line:
                    return
                if receiving:
                    if line == b".\r\n":
                        deliveries.append(b"".join(data))
                        receiving = False
                        self.wfile.write(b"250 accepted\r\n")
                    else:
                        data.append(line)
                        continue
                elif line.upper().startswith((b"EHLO", b"HELO")):
                    self.wfile.write(b"250 localhost\r\n")
                elif line.upper().startswith(b"DATA"):
                    receiving = True
                    self.wfile.write(b"354 send data\r\n")
                elif line.upper().startswith(b"QUIT"):
                    self.wfile.write(b"221 bye\r\n")
                    self.wfile.flush()
                    return
                else:
                    self.wfile.write(b"250 ok\r\n")
                self.wfile.flush()

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1], deliveries
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_smtp_adapter_delivers_once_over_real_protocol(client, drain, monkeypatch):
    lead_record = lead(client)
    c = campaign(client, [lead_record["id"]])
    d = approve(client, workflow(client, drain, lead_record, c))
    with smtp_server() as (port, deliveries):
        for key, value in {
            "EMAIL_PROVIDER": "smtp",
            "LIVE_DELIVERY_ENABLED": True,
            "SMTP_HOST": "127.0.0.1",
            "SMTP_PORT": port,
            "SMTP_TLS": "none",
            "SMTP_USERNAME": "",
            "DEFAULT_FROM_EMAIL": "sender@example.com",
        }.items():
            monkeypatch.setattr(settings, key, value)
        client.post(BASE + f"/emails/{d['id']}/send")
        drain()
        drain()
        assert len(deliveries) == 1
        assert b"To: alex@example.com" in deliveries[0]
        assert b"List-Unsubscribe" in deliveries[0]
        assert client.get(BASE + f"/emails/{d['id']}").json()["status"] == "sent"


def test_google_calendar_create_reschedule_cancel(client, drain, monkeypatch):
    events = {}
    operations = []

    def transport(request):
        operations.append((request.method, request.url.path))
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "test-token"})
        assert request.headers["authorization"] == "Bearer test-token"
        path = request.url.path
        if request.method == "GET" and path.endswith("/events"):
            return httpx.Response(200, json={"items": []})
        key = path.split("/")[-1]
        if request.method == "GET":
            return httpx.Response(200 if key in events else 404, json=events.get(key, {}))
        if request.method == "POST":
            import json

            payload = json.loads(request.content)
            key = payload["id"]
            events[key] = {"id": key, "hangoutLink": "https://meet.google.com/test-room"}
            return httpx.Response(201, json=events[key])
        if request.method == "PATCH":
            return httpx.Response(200, json=events[key])
        if request.method == "DELETE":
            events.pop(key, None)
            return httpx.Response(204)
        raise AssertionError("Unexpected Google request")

    original = httpx.AsyncClient
    monkeypatch.setattr(
        calendar.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(transport), **kwargs),
    )
    monkeypatch.setattr(settings, "CALENDAR_PROVIDER", "google")
    monkeypatch.setattr(settings, "LIVE_DELIVERY_ENABLED", True)
    lead_record = lead(client)
    data = {"lead_id": lead_record["id"], "start_at": future()}
    meeting = client.post(BASE + "/meetings", json=data).json()
    identifier = meeting["id"]
    drain()
    result = client.get(BASE + "/meetings").json()["items"][0]
    assert (
        result["sync_status"] == "synced"
        and result["join_url"] == "https://meet.google.com/test-room"
    )
    assert len(events) == 1
    client.put(BASE + f"/meetings/{identifier}", json={**data, "start_at": future(4)})
    drain()
    assert len(events) == 1
    client.post(BASE + f"/meetings/{identifier}/cancel")
    drain()
    assert len(events) == 0
    assert any(method == "PATCH" for method, _ in operations)


def test_delivery_ambiguity_never_retries_automatically(client, drain, monkeypatch):
    lead_record = lead(client)
    c = campaign(client, [lead_record["id"]])
    d = approve(client, workflow(client, drain, lead_record, c))
    calls = []

    async def uncertain(*args):
        calls.append(True)
        raise email.DeliveryUncertainError("Acceptance is uncertain")

    monkeypatch.setattr(email, "deliver", uncertain)
    client.post(BASE + f"/emails/{d['id']}/send")
    drain()
    drain()
    assert len(calls) == 1
    assert client.get(BASE + f"/emails/{d['id']}").json()["status"] == "delivery_unknown"
    assert client.post(BASE + f"/emails/{d['id']}/send").status_code == 409


def test_known_delivery_failure_needs_new_approval(client, drain, monkeypatch):
    lead_record = lead(client)
    c = campaign(client, [lead_record["id"]])
    d = approve(client, workflow(client, drain, lead_record, c))

    async def fail(*args):
        raise ConnectionError("test failure")

    monkeypatch.setattr(email, "deliver", fail)
    client.post(BASE + f"/emails/{d['id']}/send")
    drain()
    result = client.get(BASE + f"/emails/{d['id']}").json()
    assert result["status"] == "failed" and result["approved_revision"] is None
    assert result["revision"] == 2
    assert client.post(BASE + f"/emails/{d['id']}/send").status_code == 409

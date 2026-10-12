"""Mailbox correlation, duplicate protection, and opt-out use real persisted sales data."""

from email.message import EmailMessage

from app.core.config import settings
from app.providers import inbox
from app.services.inbox import sync_inbox
from tests.api.test_sales import BASE, approve, campaign, future, lead, workflow


def reply(reference, sender="alex@example.com", body="Can you share details?", automatic=False):
    message = EmailMessage()
    message["From"] = sender
    message["To"] = "sender@example.com"
    message["In-Reply-To"] = reference
    if automatic:
        message["Auto-Submitted"] = "auto-replied"
    message.set_content(body)
    return message.as_bytes()


def prepare(client, drain, monkeypatch):
    monkeypatch.setattr(settings, "IMAP_ENABLED", True)
    monkeypatch.setattr(settings, "IMAP_HOST", "imap.example.com")
    monkeypatch.setattr(settings, "IMAP_USERNAME", "sender@example.com")
    record = lead(client)
    c = campaign(client, [record["id"]])
    d = approve(client, workflow(client, drain, record, c))
    client.post(BASE + f"/emails/{d['id']}/send")
    drain()
    sent = client.get(BASE + f"/emails/{d['id']}").json()
    f = client.post(
        BASE + "/followups",
        json={"lead_id": record["id"], "campaign_id": c["id"], "due_at": future()},
    ).json()
    return record, sent, f


def test_inbox_reply_import_deduplication_and_followup_stop(client, drain, monkeypatch):
    record, sent, f = prepare(client, drain, monkeypatch)
    raw = reply(sent["provider_message_id"])
    monkeypatch.setattr(inbox, "fetch_batch", lambda *args: ("1", [(1, raw)]))
    result = client.post(BASE + "/integrations/inbox/sync").json()
    assert result["processed"] == 1
    assert client.post(BASE + "/integrations/inbox/sync").json()["processed"] == 0
    assert client.get(BASE + f"/leads/{record['id']}").json()["status"] == "replied"
    assert client.get(BASE + f"/followups/{f['id']}").json()["status"] == "cancelled"
    assert (
        len(
            [m for m in client.get(BASE + "/inbox").json()["items"] if m["direction"] == "incoming"]
        )
        == 1
    )
    assert client.get(BASE + "/integrations").json()["inbox"]["status"] == "synced"


def test_inbox_requires_matching_sender_and_sent_message(client, drain, monkeypatch):
    record, sent, _ = prepare(client, drain, monkeypatch)
    batch = [
        (1, reply(sent["provider_message_id"], "other@example.com")),
        (2, reply("<unrelated@example.com>")),
        (3, reply(sent["provider_message_id"], automatic=True)),
    ]
    monkeypatch.setattr(inbox, "fetch_batch", lambda *args: ("2", batch))
    assert client.portal.call(sync_inbox)["processed"] == 0
    assert client.get(BASE + f"/leads/{record['id']}").json()["status"] == "contacted"


def test_inbox_opt_out_and_uid_validity_change(client, drain, monkeypatch):
    record, sent, _ = prepare(client, drain, monkeypatch)
    monkeypatch.setattr(inbox, "fetch_batch", lambda *args: ("3", [(5, None)]))
    assert client.portal.call(sync_inbox)["processed"] == 0
    raw = reply(sent["provider_message_id"], body="Unsubscribe")
    monkeypatch.setattr(inbox, "fetch_batch", lambda *args: ("4", [(1, raw)]))
    assert client.portal.call(sync_inbox)["processed"] == 1
    assert client.get(BASE + f"/leads/{record['id']}").json()["status"] == "unsubscribed"


def test_inbox_failure_is_visible_and_does_not_leak_credentials(client, monkeypatch):
    monkeypatch.setattr(settings, "IMAP_ENABLED", True)

    def fail(*args):
        raise ConnectionError("password=secret")

    monkeypatch.setattr(inbox, "fetch_batch", fail)
    result = client.portal.call(sync_inbox)
    assert result["status"] == "failed" and "secret" not in str(result)
    assert client.get(BASE + "/integrations").json()["inbox"]["status"] == "failed"


def test_imap_fetch_read_only_bounded_and_skips_old_uid(monkeypatch):
    calls = []

    class Mailbox:
        def __init__(self, *args, **kwargs):
            pass

        def login(self, *args):
            pass

        def select(self, folder, readonly):
            assert readonly
            return "OK", []

        def response(self, value):
            return "UIDVALIDITY", [b"11"]

        def uid(self, command, *args):
            calls.append((command, args))
            if command == "search":
                return "OK", [b"4 5 6"]
            if args[1] == "(RFC822.SIZE)":
                return "OK", [
                    b"1 (RFC822.SIZE 1000001)" if args[0] == "6" else b"1 (RFC822.SIZE 20)"
                ]
            assert args[1] == "(BODY.PEEK[])"
            return "OK", [(b"BODY", b"sample")]

        def logout(self):
            pass

    monkeypatch.setattr(inbox.imaplib, "IMAP4_SSL", Mailbox)
    assert inbox.fetch_batch("11", 4) == ("11", [(5, b"sample"), (6, None)])
    assert not any(call[1][0] == "4" for call in calls if call[0] == "fetch")


def test_html_only_reply_is_converted_to_plain_text():
    message = EmailMessage()
    message["From"] = "alex@example.com"
    message["In-Reply-To"] = "<sent@example.com>"
    message.set_content(
        "<p>Can you share details?</p><script>secret-script</script>", subtype="html"
    )
    result = inbox.parse_reply(message.as_bytes())
    assert result["body"] == "Can you share details?"

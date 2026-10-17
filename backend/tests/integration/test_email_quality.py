"""Regression: old approvals and AI output cannot bypass unfinished-content checks."""

import json
from uuid import UUID

import pytest

from app.agents.base import AgentConfig
from app.agents.email_generator import EmailGeneratorAgent
from app.agents.schemas import EmailGeneratorInput
from app.models.sales import EmailDraft
from app.services.email_quality import content_issues
from app.tasks.worker import sessions
from tests.api.test_sales import BASE, approve, campaign, lead, workflow


@pytest.mark.parametrize(
    "body",
    [
        "Hi [Name]",
        "Hi [Your Name]",
        "Our clients see a 30% lift",
        "I can share case studies.",
        "I\u2019ve been enjoying your dishes.",
        "We have been using your services.",
    ],
)
def test_unfinished_or_unprovided_proof_is_flagged(body):
    assert content_issues("Hello", body)


def test_operator_supplied_numeric_context_is_allowed():
    assert not content_issues(
        "Pilot", "The documented pilot recorded 10%.", "Documented pilot result: 10%."
    )


@pytest.mark.parametrize(
    "generated_body",
    [
        "Hi [Name], our clients see a 30% lift. Best, [Your Name]",
        "I noticed Verification Studio focuses on reliable verification solutions. Could we talk?",
    ],
)
async def test_ai_invented_proof_is_replaced_with_operator_context(monkeypatch, generated_body):
    class LLM:
        def __init__(self, **kwargs):
            pass

        async def generate(self, **kwargs):
            return json.dumps(
                {
                    "subject_line": "Grow bookings",
                    "email_body": generated_body,
                    "call_to_action": "Can we talk?",
                    "personalization_elements": ["Bristol"],
                }
            ), {"model": "test", "latency_ms": 1}

    monkeypatch.setattr("app.agents.email_generator.LLMService", LLM)
    agent = EmailGeneratorAgent(AgentConfig(confidence_threshold=0))
    result = await agent.run(
        EmailGeneratorInput(
            recipient_name="COR team",
            recipient_company="COR Restaurant",
            sender_name="Codelps team",
            sender_company="Codelps",
            product_value_prop="We develop mobile applications.",
        )
    )
    assert result.success, result.error
    assert "30%" not in result.data.email_body and "[Name]" not in result.data.email_body
    assert "Codelps team" in result.data.email_body
    assert "We develop mobile applications." in result.data.email_body


def test_approval_requires_content_correction_and_preserves_text(client, drain):
    record = lead(client)
    c = campaign(client, [record["id"]])
    d = workflow(client, drain, record, c)
    edited = client.put(
        BASE + f"/emails/{d['id']}",
        json={
            "subject": "Hello",
            "body": "Hi [Name], our clients see a 30% lift.",
            "expected_revision": d["revision"],
        },
    ).json()
    result = client.post(
        BASE + f"/emails/{d['id']}/approve",
        json={"expected_revision": edited["revision"], "acknowledge_low_confidence": True},
    )
    assert result.status_code == 409 and "Draft needs editing" in result.text
    saved = client.get(BASE + f"/emails/{d['id']}").json()
    assert saved["body"] == edited["body"] and saved["review_issues"]
    assert saved["has_unresolved_placeholders"] is True
    clean = client.put(
        BASE + f"/emails/{d['id']}",
        json={
            "subject": "Hello",
            "body": "Hi Alex, would a short conversation be useful?",
            "expected_revision": saved["revision"],
        },
    ).json()
    assert approve(client, clean)["status"] == "approved"


def test_legacy_approved_content_is_checked_before_send(client, drain):
    record = lead(client)
    c = campaign(client, [record["id"]])
    d = approve(client, workflow(client, drain, record, c))

    async def legacy():
        async with sessions()() as db:
            row = await db.get(EmailDraft, UUID(d["id"]))
            row.body = "Hi [Name], a recent client saw a 22% lift."
            await db.commit()

    client.portal.call(legacy)
    assert client.post(BASE + f"/emails/{d['id']}/send").status_code == 409
    assert client.get(BASE + f"/emails/{d['id']}").json()["status"] == "approved"


def test_worker_rechecks_legacy_queued_content_before_smtp(client, drain):
    record = lead(client)
    c = campaign(client, [record["id"]])
    d = approve(client, workflow(client, drain, record, c))
    assert client.post(BASE + f"/emails/{d['id']}/send").status_code == 202

    async def legacy():
        async with sessions()() as db:
            row = await db.get(EmailDraft, UUID(d["id"]))
            row.body = "Hi [Name]"
            await db.commit()

    client.portal.call(legacy)
    drain()
    result = client.get(BASE + f"/emails/{d['id']}").json()
    assert result["status"] == "needs_review" and result["approved_revision"] is None
    assert result["sent_at"] is None

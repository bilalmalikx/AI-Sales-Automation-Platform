"""Recipients receive readable text and safe branded HTML alternatives."""

from types import SimpleNamespace

from app.providers.email import compose, compose_verification


def test_verification_email_has_text_and_branded_html():
    message = compose_verification("owner@example.test")
    assert message["To"] == "owner@example.test"
    assert message["Message-ID"]
    assert message.get_content_type() == "multipart/alternative"
    plain = message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()
    for content in (plain, html):
        assert "Your test email is here." in content
        assert "No customer outreach was sent." in content
        assert "Reference" in content
    assert "EMAIL CONNECTION CHECK" in html
    assert "<script" not in html
    assert "<img" not in html


def test_outreach_html_escapes_content_and_keeps_unsubscribe_and_thread_identity():
    draft = SimpleNamespace(
        id="template-check",
        revision=2,
        subject="<script>alert(1)</script>",
        body="Hello <b>team</b>\n\nA & B",
    )
    lead = SimpleNamespace(id="test-lead", email="owner@example.test")
    message = compose(draft, lead, "Codelps <team>")
    html = message.get_body(preferencelist=("html",)).get_content()
    plain = message.get_body(preferencelist=("plain",)).get_content()
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;team&lt;/b&gt;" in html
    assert "A &amp; B" in html
    assert "Codelps &lt;team&gt;" in html
    assert draft.body in plain
    assert "Stop outreach:" in plain
    assert "Stop outreach from this workspace" in html
    assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert message["Message-ID"] == compose(draft, lead, "Codelps")["Message-ID"]

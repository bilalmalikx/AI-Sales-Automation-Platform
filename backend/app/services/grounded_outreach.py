"""Website-discovered outreach uses bounded observations, never invented experience."""

import re


def grounded_draft(lead: dict, campaign: dict, prefs: dict) -> dict:
    company = " ".join(lead["company"].split())[:180]
    evidence = (lead.get("website_research") or {}).get("evidence", {})
    text = evidence.get("website", {}).get("text", "")
    features = []
    if re.search(r"\b(?:order online|online ordering)\b", text, re.I):
        features.append("online ordering")
    if re.search(r"\b(?:book a table|table reservations|reserve a table)\b", text, re.I):
        features.append("table booking")
    observation = ("Your website includes " + " and ".join(features) + ".\n\n") if features else ""
    body = (
        f"Hi {company} team,\n\n{observation}"
        f"I'm reaching out from {prefs['company']}. {campaign['offer']}\n\n"
        f"Would you be open to a short conversation about whether this is relevant for {company}?\n\n"
        f"Best,\n{prefs['sender']}"
    )
    return {
        "subject_line": f"A mobile app conversation for {company}",
        "email_body": body,
        "confidence_score": 0.6,
        "source": "Bounded website observations and operator-provided offer",
        "app_absence_verified": False,
    }

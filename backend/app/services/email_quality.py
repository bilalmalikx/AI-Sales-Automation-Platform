"""Deterministic checks for unfinished templates and unsupported sales proof."""

import re

PLACEHOLDER = re.compile(
    r"\[(?:your|first|last|recipient|sender|name|company)[^\]]*\]|\{\{[^}]+\}\}", re.I
)
QUANTIFIED = re.compile(r"\d+(?:[.,]\d+)?\s*(?:%|percent\b|per cent\b)|[£$€]\s*\d[\d,.]*", re.I)
PORTFOLIO = re.compile(
    r"case stud(?:y|ies)|clients? like|(?:our|a recent) (?:clients?|customers?) (?:often |typically )?(?:saw|see|achieved|reported)",
    re.I,
)


def content_issues(subject: str, body: str, verified_offer: str = "") -> list[str]:
    text = subject + "\n" + body
    issues = []
    if PLACEHOLDER.search(text):
        issues.append("Replace unresolved name/sender placeholders before approval or sending.")
    normalized = re.sub(r"\s+", "", verified_offer).casefold()
    if any(
        re.sub(r"\s+", "", m.group()).casefold() not in normalized
        for m in QUANTIFIED.finditer(text)
    ):
        issues.append(
            "Remove numeric result/price claims or document their verified basis in the campaign offer."
        )
    if PORTFOLIO.search(text) and not PORTFOLIO.search(verified_offer):
        issues.append(
            "Remove unprovided client examples or case-study promises, or supply verified details in the campaign offer."
        )
    return issues


def personalization_issues(body: str, supplied_company_context: bool) -> list[str]:
    if re.search(r"(?:I|we)(?:['\u2019]ve| have) been following", body, re.I):
        return ["Do not invent a prior relationship or history of following the recipient."]
    if not supplied_company_context and re.search(
        r"I (?:noticed|saw|read|understand)|focus(?:es|ed)? on|you (?:offer|provide|speciali[sz]e)|your (?:recent|growth|reputation)",
        body,
        re.I,
    ):
        return ["Company observations require supplied website/company context."]
    return []

"""Actionable retry decisions without bypassing crawler restrictions or AI budgets."""


def retry_advice(reason: str | None) -> tuple[bool, str]:
    reason = (reason or "").lower()
    if any(word in reason for word in ("blocks crawler", "robots", "http 401", "http 403")):
        return False, "Website restricts automated access. Review its public contact page manually."
    if any(word in reason for word in ("only public", "invalid public", "size limit")):
        return False, "Source URL cannot be crawled safely; review or correct the source website."
    if any(word in reason for word in ("openai", "ai request", "qualification")):
        return (
            True,
            "Retry saved website evidence when AI quota is available; run limits still apply.",
        )
    return (
        True,
        "Retry temporary network failures; inaccessible websites may still require manual review.",
    )

# End-to-end email retest — 15 October 2026

## Results

- Final PostgreSQL suite: **94 passed**, coverage **84.83%**.
- SQLite suite during the email fix: **93 passed**, coverage **84.92%**. The final additional personalization case/flag is covered by the successful PostgreSQL run.
- Angular: **12 passed**; production build passed. Ruff checks and Git whitespace checks passed.
- Complete isolated HTTP/Celery flow passed: lead/campaign → workflow → draft approval → local delivery → signed reply → followup cancellation → local meeting create/reschedule/cancel → analytics → unsubscribe. [Result](email-retest-smoke-2026-10-15.json).
- Actual configured SMTP TLS/authentication passed. A single fixed test email to the configured sender was then accepted through HTTP approval/send and the real Celery worker. No customer email was sent. Inbox receipt is not independently verified. [Result](email-retest-smtp-2026-10-15.json).
- One real configured AI email-generation call passed after the correction; the resulting draft contained no detected placeholder, unsupported numeric proof or unprovided company observation. [Result](email-retest-ai-2026-10-15.json).
- Real Angular email review showed content warnings and disabled Approve/Send for unresolved placeholders, including the previously approved draft. No browser console errors were captured in this check.
- Existing workspace text and historical sent records were preserved. A private pre-update database backup was created by the local lifecycle script.

## Issue found and fixed during testing

Several existing AI drafts contained unresolved `[Name]` / `[Your Name]`, unsupported percentages, invented client results or unprovided case-study promises. One such draft was already approved.

Generation now uses stricter factual instructions, the configured sender, lower temperature and supplied website context. Detected unsupported proof, placeholders or unsupported company observations cause replacement with a conservative draft based on the operator's offer. Such replacement remains low confidence and requires human review. This is a heuristic check, not a comprehensive fact checker.

Approval and Send now independently reject unfinished placeholders and numeric/result/portfolio claims that lack context in the campaign offer. The worker repeats the check before delivery, including legacy queued jobs. A typed placeholder flag disables the relevant Angular buttons. Original operator drafts and approval status are not silently rewritten.

Six existing unsent drafts showed content-review warnings in the real workspace. Edit them and verify their claims before approval/send. A supplied campaign offer is operator context, not independent third-party proof; manual factual review remains necessary. Drafts with verified numerical claims may be approved when their supporting context is supplied in the campaign offer.

## Still not live verified

IMAP credentials remain absent/disabled; Google OAuth credentials remain absent and the Calendar provider remains local. Signed-reply handling and mailbox parsing passed isolated tests; Google adapter tests use mocks. An actual prospect reply → inbox → live Google meeting round trip cannot be certified yet. Production deployment remains deferred by the user.

Fresh paid Maps discovery was not rerun in this pass. Existing real discovery records and review drafts remained visible. Test databases/workers were separate from the real workspace and stopped after verification. The real frontend/API remain running.

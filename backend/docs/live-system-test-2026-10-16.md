# Live system verification — 16 October 2026

The approved Birmingham campaign sent four reviewed outreach messages through the application API, Celery worker and live SMTP. All four are recorded as sent with provider Message-IDs. This verifies SMTP acceptance, not delivery to each customer inbox. No customer reply has arrived yet. Four follow-up tasks are scheduled for 19 October; follow-up emails require review.

## Actual live self-test

An independently labeled owner-inbox test passed workflow, draft editing/approval, SMTP send, actual self-reply ingestion over TLS IMAP, lead status update, follow-up cancellation and duplicate-sync protection. Application meeting booking created a Google Calendar event and Meet link; rescheduling and cancellation synchronized successfully. The temporary meeting was cancelled, the self-test campaign paused, and the self-test lead suppressed. No reply or meeting was fabricated for a customer. Automatic IMAP polling is now enabled and reports synced.

## Checks and limits

98 backend regression tests passed. Ten workspace API endpoints returned HTTP 200 after the live run. Earlier Angular verification passed 12 tests and a production build.

Discovery processed all 50 businesses: 24 had contact details, 11 had public email, and four entered this campaign. Two app-found businesses were excluded, so the UI contact counts excluding them are 22 and nine respectively. The run completed with errors: 12 blocked websites, seven inaccessible websites, one network error and one AI request failure. Qualification used the configured 20-call budget. An initial synthetic-lead enrichment test failed without research context; a new run with an explicitly labeled test fixture passed.

Real customer meeting bookings remain dependent on a reply and agreed availability. Customer replies are not simulated.

Detailed evidence: [live-campaign-2026-10-16.json](live-campaign-2026-10-16.json).

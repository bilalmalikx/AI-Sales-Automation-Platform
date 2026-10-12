# Verification — 11 October 2026

The local Codelps application runs on http://localhost:4202 with its API on http://localhost:8002. PostgreSQL, Redis, API, worker and beat are running. Existing credentials and workspace records were preserved.

## Verified

- Final PostgreSQL regression suite: **75 passed**, coverage **83.99%**, isolated database on port 15433 with background workers paused during tests.
- SQLite regression suite before the final send-guard/HTML additions: **73 passed**, coverage **84.05%**.
- Angular production build passed; Angular tests: **10 passed** across three files.
- Ruff lint and format checks passed.
- Independent local-provider API smoke passed with actual PostgreSQL/Celery/Redis: lead/campaign, durable workflow, approval, queued email, signed reply, followup cancellation, meeting create/reschedule/cancel, analytics and unsubscribe. [Persisted result](end-to-end-smoke-result.json).
- Configured live SMTP connection/authentication passed. One test email addressed only to the configured sender was accepted by SMTP. Inbox receipt is not independently confirmed.
- Configured live AI endpoint returned the requested `OK` response using the configured model. This confirms connectivity, not guaranteed rate-limit capacity for large batches.
- Angular Settings → Check SMTP connection returned success through the real backend endpoint.
- Both existing pending-delivery and pending-email-job counts were zero before enabling the explicit manual SMTP delivery override. Approval, active campaign and Send are still required; discovery does not send mail.

## Added or corrected

- TLS IMAP polling, persistent UIDVALIDITY/UID checkpoints, bounded read-only batches, plain-text/HTML MIME replies, matching sent Message-ID and sender, deduplication, explicit opt-out and cancellation of scheduled followups.
- IMAP sync status/error API, scheduled Celery polling when enabled, and manual Settings sync.
- Secret-free SMTP readiness endpoint and Settings controls. Disabled SMTP returns a conflict before queuing or invalidating approval.
- Website-derived CRM evidence remains intact when the outreach workflow completes.
- Configured LLM retry count is now applied to the SDK adapter.
- Opt-in delivery Compose override, sender display names and dedicated self-test CLI.

## Credential-dependent work remains unverified

IMAP credentials are absent. Set `IMAP_ENABLED=true`, `IMAP_HOST`, `IMAP_PORT=993`, `IMAP_USERNAME`, `IMAP_PASSWORD` and optionally folder/poll interval in the backend environment. SMTP credentials are not assumed to be valid IMAP credentials. Recreate API/worker/beat after configuration, then verify an actual reply appears in Inbox. Parsed sender headers are not independent DKIM authentication; mailbox-provider anti-spam/authentication remains relevant.

Google OAuth credentials are absent. Supply `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `GOOGLE_CALENDAR_ID` and explicitly select `CALENDAR_PROVIDER=google` in the runtime override. Calendar adapter behavior is covered by mocked provider tests; current meetings remain local. Google event creation and attendance invitations have not been executed against a live account.

Fresh Apify discovery was verified previously and its existing results remain in the real workspace. This verification did not purchase another discovery run. Discovery remains click-triggered; automatic daily discovery scheduling and an all-provider monthly budget are not implemented.

This is a tested single-workspace local application. Public HTTPS deployment, recipient-reachable unsubscribe URLs, tenant accounts/permissions, billing and production operational monitoring are separate from this verification. Local Compose pins PUBLIC_BASE_URL to localhost; configure a public URL in a deployment override before real external outreach.

## Run

```sh
# From backend: real discovery/AI/SMTP credentials, manual reviewed delivery enabled.
docker compose -f docker-compose.yml -f docker-compose.live.yml -f docker-compose.delivery.yml up -d --build

# From frontend: Angular 21 requires a supported Node runtime.
npm start
```

Omit `docker-compose.delivery.yml` to keep SMTP delivery disabled. Neither live discovery nor inbox sync approves drafts or sends unsolicited automatic mail. Test-only containers used for this verification are stopped separately from the actual application.

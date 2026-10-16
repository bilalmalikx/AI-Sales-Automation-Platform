# Local Codelps completion — 15 October 2026

Scope confirmed by the user: complete the single-company local system first; deployment later.

## Implemented

- Existing discovery → website/app evidence → qualification → CRM → AI review draft → manual approval/send workflow retained.
- Daily discovery schedules can be saved, enabled or paused from Angular. Each schedule repeats every 24 hours in UTC; the initial timestamp is converted from the browser's local time. New UI schedules are saved paused, so a test or page visit does not start paid recurring work.
- Dispatch is durable and idempotent per schedule/time slot, serialized under a workspace database lock. Missed days do not produce a catch-up burst. Daily limits and monthly provider reservations apply to manual and scheduled searches together. Pausing stops future slots, not a paid external run already started.
- Monthly Apify cap defaults to `$5`, configurable with `DISCOVERY_MONTHLY_BUDGET_USD`. The maximum per-run charge is reserved before a queued paid run starts. Actual reported costs replace reservations after completion. Failed/ambiguous paid starts retain their cap for the rest of the month. Cancelling before any paid start releases the unused reservation. The provider start uses the reserved cap even if configuration changes while queued.
- Angular shows reported costs, spent/reserved amounts, cap and schedule state/errors. These are Apify controls, not an all-provider AI/email budget. Existing per-run AI call limits remain separate.
- `scripts/local.sh` provides start, stop, status and private database backup. Start brings up PostgreSQL/Redis, backs up the database before running migrations, then starts API/workers and the Angular frontend. Stop retains all volumes. It checks project ownership before stopping/reusing a frontend process on port 4202.
- Missing IMAP and Google OAuth placeholders were added to the real, ignored `backend/.env` without overwriting existing values. File permissions were set to 0600. Examples were updated. The live Compose override now honors the configured Calendar provider.

## Verification

- Final PostgreSQL regression suite: **84 passed**, coverage **84.59%**. An initial attempt began before the disposable database download/readiness completed and was interrupted; the final successful run happened after migration readiness, with test API/workers stopped.
- Earlier SQLite suite during implementation: **82 passed**, coverage **84.68%**. Final cancellation/reserved-cap behavior is included in the successful PostgreSQL suite.
- Angular: **12 passed** across four files; production build passed.
- Ruff lint/format, shell syntax and Git whitespace checks passed.
- Complete isolated HTTP/Celery flow passed: lead/campaign, durable workflow, current-revision review/approval, queued local email, signed reply, followup cancellation, meeting create/reschedule/cancel, analytics and unsubscribe. [Result](local-completion-smoke-2026-10-15.json). This run used local AI/email/calendar providers; prior live AI/SMTP/discovery verification is recorded in the 13 October report.
- A real workspace database backup was restored only into a separate disposable database: **7 leads, 40 prospects**, migration `006_discovery_schedules`. The actual database was not restored over or cleared. Backups remain privately under `.local/backups/`, excluded from Git.
- Angular successfully saved `Codelps · London car wash`, maximum 50, as a **paused** schedule. No paid schedule was enabled during verification.
- Local stop/start and readiness were verified. Actual records were retained; no new paid discovery or customer outreach was executed in this completion pass.

## Run from the repository root

```sh
bash scripts/local.sh start
bash scripts/local.sh status
bash scripts/local.sh backup
bash scripts/local.sh stop
```

Frontend: http://localhost:4202/#/discovery. API: http://localhost:8002. Docker Desktop must be running; frontend dependencies must be installed. The script prefers the bundled Node runtime if available, otherwise PATH Node; Angular 21 needs a supported Node version. Logs are in `.local/frontend.log`; use Docker Compose logs for backend services.

## Credential-dependent checks

Fill `IMAP_HOST`, `IMAP_USERNAME`, `IMAP_PASSWORD`; keep port 993/folder INBOX unless the mailbox provider specifies otherwise, then set `IMAP_ENABLED=true`.

Fill `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`; keep `GOOGLE_CALENDAR_ID=primary` unless using another calendar, then set `CALENDAR_PROVIDER=google`. The refresh token is an offline OAuth token using Calendar events scope, not a password or an API key.

Restart with the local script after configuration. A real incoming reply and a real Google event/Meet invitation still need verification with those credentials; do not report them as live verified. Credentials were still unfilled when checked during this pass. Local meetings and signed-reply handling are tested and available meanwhile.

Public deployment, multi-tenant SaaS accounts/billing and broader inbox deliverability/load testing are outside this confirmed local completion scope. A 50-business raw search is not a guarantee of 50 public-email leads; uncertain app absence still requires human review.

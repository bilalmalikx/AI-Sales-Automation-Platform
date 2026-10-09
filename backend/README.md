# Salesway backend

FastAPI backend for the existing Angular/prototype workspace. The Angular frontend uses the real API, including business discovery. This backend stores real records in PostgreSQL and runs durable jobs through Celery/Redis; local providers keep development self-contained.

## Run the complete local stack

From `backend/`:

```sh
docker compose up -d --build
docker compose ps
```

API: http://localhost:8000 · interactive API docs: http://localhost:8000/docs · readiness: http://localhost:8000/health/ready

Compose starts PostgreSQL 16, Redis, migrations, API, Celery worker and Celery beat. PostgreSQL is available on localhost:15432; Redis stays inside the network. Data and local email files persist in Docker volumes. `docker compose down` stops the stack while retaining its data.

The default providers are local: AI produces an explicit unverified draft, email writes `.eml` files to `/app/var/mailbox`, and calendar synchronization records a local event ID. They do not send external emails or create Google events. Beat checks committed jobs every five seconds. These defaults intentionally work without account credentials.

For Python development, install Python 3.13, create a virtual environment, install `requirements-dev.txt`, and copy `.env.example` to `.env` only if you do not already have your own configuration. Run `alembic upgrade head` before `uvicorn app.main:app --reload`. `WORKER_MODE=inline` runs development jobs inside the API; `manual` is for tests. Existing `.env` credentials were preserved. Do not start another API on port 8000 while Compose is running.

## Real business discovery

See [live discovery setup and safeguards](docs/live-discovery.md). With your existing `.env` configured, start the live-discovery stack:

```sh
docker compose -f docker-compose.yml -f docker-compose.live.yml up -d --build
```

The override loads Apify and the configured OpenAI-compatible AI endpoint into the API and workers. It deliberately keeps `LIVE_DELIVERY_ENABLED=false`. SMTP credentials are loaded, but no external email is sent. Google Calendar stays local until its OAuth credentials are configured.

Open `http://localhost:4202/#/discovery`, choose a category/city and click Discover businesses. Results and evidence persist in PostgreSQL and refresh automatically.

## Implemented flow

1. Create/edit/delete/search leads or import bounded, quoted UTF-8 CSV. Emails are normalized and unique; strict imports roll back on errors. CSV export protects spreadsheet formula cells.
2. Create campaigns, assign leads, and activate or pause outreach.
3. Start `/api/v1/workflows` with an `Idempotency-Key` header. LangGraph runs enrichment, research and email generation, persisting completed stages so retries can resume.
4. Review/edit the resulting email. Approval requires its current `expected_revision`; editing invalidates approval. Unverified AI content requires explicit acknowledgment. Inferred research is never silently promoted to verified CRM facts.
5. Explicitly request send. The durable worker enforces approval, campaign/contact eligibility and the workspace's timezone-based daily limit. Repeat requests do not create another send job.
6. Signed inbound email events update inbox, lead status and delivered/opened timestamps. Replies cancel scheduled followups. Human replies are saved as approved drafts and still require explicit send.
7. Create/reschedule/cancel meetings with explicit timezone offsets. Local overlaps are rejected; Google also checks external calendar availability. Provider sync failures remain visible and retryable.
8. Schedule followups. When due, eligible contacts receive a draft requiring review; followups do not auto-send. Analytics, pipeline, notifications, settings and activity use persisted records.
9. Unsubscribe cancels pending outreach and stores independent email suppression. Deleting and reimporting a contact cannot bypass that suppression.

All application routes live under `/api/v1`. Lists return `items`, `total`, `page`, `page_size`, `pages` and accept bounded pagination. Resource IDs are UUID strings; statuses are lowercase strings. Timestamps are UTC with `Z`; input meeting/followup timestamps must contain an offset. Validation/conflict errors use a consistent error envelope. Explore request and response schemas in `/docs` or `/openapi.json`.

## SMTP and Google Calendar

Configure the API, worker and beat with the same environment settings. The local Compose file pins local providers; changing a host `.env` alone does not override its environment. Use a private deployment environment or a Compose override with explicit values.

SMTP: `EMAIL_PROVIDER=smtp`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_TLS=starttls` (or `ssl`), `DEFAULT_FROM_EMAIL`, `DEFAULT_FROM_NAME`, then `LIVE_DELIVERY_ENABLED=true`. Authentication is optional only when your SMTP server supports it. Outbound mail includes a stable Message-ID and signed one-click unsubscribe headers.

SMTP does not provide incoming replies, delivery or open events. Your inbound mailbox/provider bridge must map the original Message-ID to its draft UUID and forward normalized events to `POST /api/v1/webhooks/email`. There is no IMAP polling or open-tracking pixel in this backend. Payload: `event_id`, `draft_id`, `kind` (`delivered`, `opened`, `replied`, `bounced`, `unsubscribed`), optional `body`, and `intent`. Sign the exact request bytes with HMAC-SHA256 over `timestamp + "." + body`, using `WEBHOOK_SECRET`; pass `X-Webhook-Timestamp` (Unix seconds) and `X-Webhook-Signature` (hex). Requests outside five minutes are rejected; repeated event IDs are deduplicated.

Google: enable Calendar API, configure an OAuth client and obtain an offline refresh token with `https://www.googleapis.com/auth/calendar.events` scope. Set `CALENDAR_PROVIDER=google`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `GOOGLE_CALENDAR_ID`, then enable live delivery. The account must own or have write access to the calendar. Event IDs are stable across retries; attendee updates use `sendUpdates=all`, and Meet links are returned when Google creates them. Refresh-token acquisition is performed by the operator; this backend does not expose an OAuth consent/login UI.

AI: set `AI_PROVIDER=openai`, `OPENAI_API_KEY`, and an account-supported `OPENAI_MODEL`. Manual-lead workflows infer from supplied data. Business-discovery workflows use crawled website evidence and app-store checks before drafting. Human review remains mandatory. Local AI is the default for repeatable tests.

Provider references: [Google events](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert), [Google offline OAuth](https://developers.google.com/identity/protocols/oauth2/web-server), [LangGraph](https://reference.langchain.com/python/langgraph/graph), [Celery tasks](https://docs.celeryq.dev/en/stable/userguide/tasks.html).

## Recovery and deployment

PostgreSQL is the source of truth for queued work. Workers claim jobs using row locks and leases; expired jobs can be recovered. Workflow checkpoints avoid repeating completed steps. Calendar retries reconcile stable event IDs. Failed workflow/calendar jobs can be explicitly retried through `/jobs/{id}/retry`.

SMTP cannot guarantee exactly-once delivery after a connection loss following DATA. Such sends become `unknown` and are never automatically resent. `/emails/{id}/reconcile` lets an operator confirm delivery or explicitly acknowledge duplicate risk before producing a new revision for approval. Definitively rejected sends require renewed approval. An unsubscribe stops queued work; it cannot retract email already accepted by the SMTP server.

This is a single-workspace API, protected by `Authorization: Bearer <API_TOKEN>` when configured. There is no user login, per-user RBAC or multi-tenant account model. Production requires a strong API token and secret, PostgreSQL, Celery mode and an HTTPS public URL. Do not embed a shared privileged token in a publicly shipped Angular bundle; use a trusted server/session boundary during real integration.

Use `.env.production.example` as a deployment template and secret-manager values for credentials. Build the runtime image from `Dockerfile`, run `alembic upgrade head` once before rollout, then run API, worker and a single beat instance on a private Redis/PostgreSQL network behind HTTPS. Keep persistent storage/backups, database migrations and external provider access configured for your deployment. The container runs as a non-root user. The supplied Compose stack is a local development deployment, not a public production deployment.

Migrations support a clean database and the original Alembic-managed `001` schema. If an existing database was created manually from old SQL scripts, reconcile its schema with migrations before upgrading; do not blindly stamp or drop your existing data.

## Verify

```sh
venv/bin/pytest -q --cov=app --cov-report=term:skip-covered
venv/bin/ruff check app tests alembic scripts
venv/bin/ruff format --check app tests alembic scripts
venv/bin/python scripts/smoke.py
```

Default pytest uses a temporary migrated SQLite database and local providers. PostgreSQL verification uses `SALESWAY_TEST_DATABASE_URL=postgresql+asyncpg://.../DEDICATED_TEST_DB`; the fixture clears application tables, so use only a dedicated test database. Tests cover workflow, approval/revisions, send limits, real temporary SMTP-server delivery, mocked Google create/reschedule/cancel, retries, SMTP uncertainty, CSV imports, auth, signed webhooks, suppression, meetings and agent outputs. Live account delivery requires separately supplied SMTP/Google credentials and is not claimed by these tests.

`smoke.py` exercises a running API and real asynchronous workers. It requires local providers and creates synthetic test records. It does not erase existing records.

## Structure

`api/v1` routes → `schemas` validation → `services` business rules → `repositories` persistence → `models` entities. `workflows` contains LangGraph orchestration, `agents` contains AI agents, `providers` contains SMTP/Google adapters, `tasks` contains durable workers and Celery, `core` contains config/security/errors, and `alembic` contains versioned migrations.

Latest verification: **49 tests passed on SQLite and PostgreSQL**, PostgreSQL coverage **86.43%**, Ruff lint/format checks passed, and migration upgrade/downgrade/upgrade passed. The running Docker PostgreSQL/Redis/API/Celery/beat stack passed the HTTP end-to-end smoke flow; its result is saved in [smoke-result.json](docs/smoke-result.json). SMTP was tested with a temporary local SMTP server; Google Calendar responses were mocked. No live account credentials were used.

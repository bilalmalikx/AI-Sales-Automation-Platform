# Codelps real business discovery

## Providers and configuration

Keep credentials in the existing backend `.env`; do not put them in Angular. Use `docker-compose.live.yml` alongside the base Compose file. The isolated Compose PostgreSQL database uses port 15432 and does not modify a different database named in the host `.env`.

- `APIFY_API_TOKEN`: account access for fresh Maps searches. `APIFY_ACTOR_ID` defaults to `compass/crawler-google-places`. Fresh mode creates a new run; it does not need the old dataset. Optional `APIFY_DATASET_ID` supports reading a saved dataset without another Actor start. A dataset API URL is normalized to its ID, discarding query credentials.
- `AI_PROVIDER=openai`: OpenAI-compatible chat adapter. `OPENAI_API_KEY` or `GROQ_API_KEY`; `LLM_BASE_URL` defaults to OpenAI, but can point to Groq. `LLM_MODEL` takes precedence over `OPENAI_MODEL`. Provider hostname and model are visible in the configuration endpoint, never keys. Current configured endpoint is Groq, rather than the OpenAI service.
- SMTP accepts `DEFAULT_FROM_EMAIL`/`SMTP_FROM`, `SMTP_TLS`/`SMTP_SECURITY` plus server/login settings. The live override keeps delivery disabled. Google Calendar requires a separate OAuth refresh token and calendar configuration; it remains local here.

## One-click process

1. Angular posts `/api/v1/discovery/runs` with an idempotency key and UK/US industry/city filters.
2. Durable Celery jobs start a bounded Apify Maps search. Search requests prefer businesses with websites and skip closed places. Database checkpoints record the provider run before polling.
3. Dataset pagination produces distinct prospects with Maps source identifiers, website, city and phone. Missing websites, closed companies and other countries are explicitly recorded/excluded.
4. Website inspection honors robots restrictions, follows only public addresses, pins validated DNS and limits page size, redirects, time and number of pages. Contact/app pages take priority. It extracts actual public addresses, filters unrelated footer domains and records the source URL. It never generates an email address.
5. App verification inspects official website links and Apple/Google search evidence. A website-linked listing or matching developer domain can identify an existing app. Brand-name candidates and incomplete searches remain uncertain. No app found never proves absence, ownership or intent to purchase.
6. Structured AI qualification evaluates booking, ordering, loyalty and membership opportunities using the evidence. Scores are inferences, not verified company facts. Existing apps and unsuitable businesses are excluded or left for review.
7. Suitable prospects with public email and score at least 50 are deduplicated into CRM. Suppression is enforced. A draft campaign and review workflow may be created. Existing contacts are linked without automatic repeat drafting. Every draft requires human review; no automatic SMTP sends occur.
8. Results and detailed evidence refresh in Angular every two seconds. The main list shows all results and separately counts contacts found, public-email records and CRM contacts. An optional contact-only view is available; the API supports `contact_only=true` with correct pagination. Only accessible websites with an extracted email, telephone link or same-domain contact-page link count as contactable. Unreachable sites and contact-less records remain visible. Email delivery still requires a public email; phone/contact-page prospects are for manual contact. A contact-page link is a website-advertised contact route, not email validation. Failed inspections can retry saved stages; incomplete website crawls retry the website stage.

## Limits, retries and costs

Default ceiling: 100 requested discoveries per UTC day, at most 100 per request. This is a discovery ceiling, not a promise of 100 qualified contacts or emails. Requested limits count toward the daily ceiling even when a run produces fewer rows.

Default Apify charge cap: $0.50 per fresh run, passed to Apify as `maxTotalChargeUsd`. The UI shows the provider-reported usage, not an estimated total invoice. AI qualification is separately limited to 20 calls per run; draft generation has separate bounded workflow calls. The Apify cap is not an all-provider monthly budget. Set lower limits for initial testing and monitor account credit usage.

An ambiguous paid Actor start is never blindly repeated. Check the account run history before starting another search. GET polling and website inspections can retry. `Stop processing` prevents later CRM promotion but does not abort an already running external Actor or retract work completed before cancellation; the provider run remains subject to its charge cap.

Incoming SMTP replies require an inbound mailbox/provider bridge to the signed webhook. Meeting sync needs Google credentials. A scheduler for automatically starting new discovery searches is not enabled: discovery is click-triggered here, with durable polling and processing of each run.

## Local verification

```sh
venv/bin/pytest -q --cov=app
# Optional isolated PostgreSQL test database only:
SALESWAY_TEST_DATABASE_URL=postgresql+asyncpg://bilalmalik@127.0.0.1:5432/salesway_backend_tests venv/bin/pytest -q
```

Tests use local providers or mocks and cannot access the configured Apify token. The live trial records are saved separately in `docs/live-discovery-result.json` after provider completion. No prospect email is sent during verification.

## Operator-selected review drafts

Campaigns → Prepare outreach opens AI workflow with that campaign selected. The lead selector includes eligible CRM contacts and public-email discovery contacts from all runs. Discovery-only candidates remain labelled review required; they are not silently marked AI-qualified. Their website, actual email, AI fit and app evidence appear before selection is confirmed.

`POST /api/v1/discovery/prospects/{id}/prepare-outreach` requires `campaign_id`, `reviewed_contact: true` and an `Idempotency-Key`. It preserves evidence/AI scores, deduplicates the contact into CRM, assigns it to the chosen campaign and queues a human-review draft. Completed website inspection and a public email are required. Existing apps, excluded/cancelled records and stopped/suppressed CRM contacts cannot use this route. It neither activates the campaign nor sends mail.

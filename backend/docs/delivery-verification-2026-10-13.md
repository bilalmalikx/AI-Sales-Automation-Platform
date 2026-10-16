# Delivery verification — 13 October 2026

**Result: the existing single-workspace application passed today's regression and end-to-end workflow verification. Live replies and Google Calendar remain credential-dependent and were not verified against real accounts.**

Frontend: http://localhost:4202/#/discovery. Backend: http://localhost:8002. API/database/Redis were ready; worker and beat were running. The frontend was restarted for verification. Actual workspace records and credentials were preserved. Synthetic workflow tests ran in the separate `salesway-e2e` Docker project on ports 8003/15433.

## Checks completed

- SQLite: **75 tests passed**, coverage **84.10%**.
- PostgreSQL: **75 tests passed**, coverage **83.99%**. Background workers were not started until the table-resetting test suite finished.
- Angular: **10 tests passed** across three test files; production build passed.
- Ruff lint/format and Git whitespace checks passed.
- HTTP/Celery smoke: campaign/lead creation, durable AI workflow, draft review/approval, asynchronous email, signed incoming reply, followup cancellation, meeting create/reschedule/cancel, analytics and unsubscribe passed. AI/email/calendar providers in this smoke were local. [Result](delivery-smoke-2026-10-13.json).
- Live configured AI endpoint responded successfully using `openai/gpt-oss-20b`; fresh website qualification and three real AI outreach drafts also completed.
- Live SMTP accepted two self-addressed verification messages: one adapter self-test and one through isolated HTTP workflow → fixed test content → current-revision approval → explicit Send → actual Celery worker → SMTP. No customer test messages were sent. SMTP acceptance/Message-ID is verified; final inbox receipt and spam placement are not. [HTTP SMTP result](delivery-smtp-2026-10-13.json).
- Angular Settings SMTP check succeeded through the real backend endpoint.
- All **12 frontend pages** rendered their expected headings without backend-unavailable notices: overview, discovery, leads, campaigns, AI workflow, email review, inbox, meetings, followups, pipeline, analytics and settings. No browser console errors were captured. This is route/data-load verification, not a claim that every browser interaction has automated coverage. [UI checks](delivery-ui-checks-2026-10-13.json).
- Workflow lead dropdown displayed real CRM/discovery contacts, including the new Bristol contacts.

## Fresh real discovery

Restaurants, Bristol, UK; requested five businesses. All five were discovered and inspected. Three businesses with public emails were added to CRM and three email drafts reached `needs_review`. Their campaign remains draft and zero customer emails were sent.

One website initially timed out. An explicit retry reused the existing discovery result, recovered the website, found official Apple/Google app links and excluded that business. Another business had website contact information but no public email, so outreach was blocked. Three businesses have uncertain app status and require human review; they are opportunities, not proof that they want to buy an app or have no app.

Final run status: **completed**, five of five inspections processed. Provider-reported Apify charge: **$0.0002**; this is the reported run field, not a verified invoice or all-provider cost. [Result](delivery-live-discovery-2026-10-13.json). Fresh results and drafts remain available in the actual application for delivery demonstration.

## Pending items to discuss after handover

1. **Incoming live replies:** IMAP host/username/password are absent and IMAP is disabled. The parser, durable sync and reply/followup handling passed tests, but a real mailbox round trip is pending. A signed webhook bridge is an alternative; it is not automatically supplied by SMTP.
2. **Live Google meetings:** OAuth client ID/secret/refresh token are absent. Meetings currently persist locally. Google adapter tests use mocked responses; live event/Meet creation and invitations are pending.
3. **Public deployment:** domain/HTTPS, production environment, trusted authentication/session boundary, recipient-reachable unsubscribe URL, backup/restore and monitoring must be configured and verified. Local Compose uses localhost unsubscribe URLs. Do not describe the localhost setup as a publicly deployed production service.
4. **Email delivery validation:** confirm both self-test messages in the actual inbox and check sender-domain SPF/DKIM/DMARC/spam placement before broad external outreach. Provider acceptance does not prove recipient inbox delivery.
5. **Discovery scale and automation:** test the intended 50/100-business workload against provider credits/rate limits; add automatic daily query scheduling if required. Current discovery is click-triggered, with scheduled processing of each run. All-provider monthly budget accounting is not implemented.
6. **Lead quality:** uncertain app matches require review. A raw search limit is not a guaranteed number of public-email leads. Website blocking, JavaScript-only contacts and unavailable pages can reduce results.
7. **Commercial SaaS features, if required:** signup/login, separate tenant workspaces, roles, billing/subscriptions and onboarding remain outside this single-workspace delivery.

## Delivery positioning

Deliver as a **working Codelps internal sales automation application / pilot** with real discovery, website evidence, AI review drafts, reviewed SMTP sends, CRM and local meeting management. Disclose the live inbox/Google/public-hosting items above. A fully live prospect-email-reply-Google-meeting round trip cannot be certified while those credentials are missing.

Test-only services were removed after verification; persisted test volumes and actual workspace volumes were retained. The real application remains running.

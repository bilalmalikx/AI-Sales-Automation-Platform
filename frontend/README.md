# Salesway Angular frontend

Angular 21 standalone implementation of the Salesway prototype. All 12 screens use native Angular components, lazy routes, typed models and signal-based services. The prototype's text, Figtree font, Porcelain/Midnight/System themes, 3D tilt, loading states, custom dropdowns and date picker are retained.

## Run and verify

Use Node.js 22.12+ LTS and npm. From `frontend`:

```sh
npm ci
npm start
npm test
npm run build:production
npm run build:local
```

Open http://localhost:4202/#/overview. The port avoids other apps already running on 4200/4201. Deploy `dist/frontend/browser` after the production build. Hash routes work on static hosts without rewrite rules.

## Structure

- `src/app/components`: app shell and reusable workspace dialog.
- `src/app/pages`: discovery, overview, leads, campaigns, workflow, emails, inbox, meetings, followups, pipeline, analytics and settings. Routes load pages independently.
- `src/app/shared`: icons, person/badge, page headers, metric cards, tables, chart, dropdown, calendar, toast and intro.
- `src/app/services`: HTTP-backed workspace state; leads, campaigns, workflow, email, inbox, meetings, followups and analytics; theme, notification, dialog and HTTP API services.
- `src/app/models`: typed domain and backend records.
- `src/app/utils`: CSV parsing/export, date and meeting conflict rules, static SVG icons, pointer tilt, top-layer overlay positioning and HTTP error handling.
- `src/environments`: local `environment.ts` and production `environment.production.ts`; `angular.json` replaces the environment for production builds.
- `public/assets`: locally served Figtree font.

Angular CLI generated the pages, shared components and services before implementation. To extend this structure, use `npm run ng -- generate component pages/example` or `npm run ng -- generate service services/example`.

## Live data and backend integration

Both environments use the real API. Local base URL: `http://localhost:8000/api/v1`; production: `/api/v1`, served through your authenticated reverse proxy. There is no fallback to demo leads or browser-stored sales records. Workspace pages refresh every five seconds; discovery refreshes every two seconds. Theme preferences remain local.

Start the backend using its documented Compose live override, then `npm start`. Open `http://localhost:4202/#/discovery`. A single click starts the server-side Maps search, public website crawl, app evidence checks, AI qualification and eligible CRM/draft creation. Maps does not need to be open. Failed inspections can resume from saved evidence.

Leads, campaign membership, workflows, email revisions/approval/send requests, inbox drafts, meetings, followups, pipeline and settings call backend endpoints. Loading and error states are visible. Backend rules enforce suppression, review, campaign eligibility, daily limits and revision checks. When SMTP delivery is disabled, the Send button explains that state and remains disabled. Google Calendar and inbound reply visibility depend on their provider configuration; SMTP alone cannot fetch incoming mail.

Discovery records without public emails remain prospects. Uncertain app matches require review; the UI never treats search absence as proof of no app. Qualification scores are inferred from collected evidence. The sidebar’s other pages show persisted records, including any earlier manually entered test records.

## Checks

`npm test` verifies API-backed UUID records, edits, backend conflict messages and CSV handling. `npm run build:production` produces `dist/frontend/browser`. Node 24 LTS is recommended; Node 25 is unsupported by this Angular toolchain. No backend credentials belong in Angular source or browser storage.

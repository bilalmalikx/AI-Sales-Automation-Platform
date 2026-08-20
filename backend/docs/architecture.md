# Architecture — Phase 1: Backend Foundation

## Overview

This document describes the backend architecture established in Phase 1.
It will be updated incrementally as each phase is implemented.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Web Framework | FastAPI 0.115 |
| Runtime | Python 3.13 / uvicorn |
| Settings | Pydantic Settings v2 |
| Logging | structlog (JSON or console) |
| Database (Phase 2) | PostgreSQL 16 + SQLAlchemy 2.x async |
| Migrations (Phase 2) | Alembic |
| Cache / Broker (Phase 6) | Redis 7 |
| Task Queue (Phase 6) | Celery 5 |
| AI Agents (Phase 5+) | LangChain + LangGraph |
| Containerisation | Docker + Docker Compose |

---

## Directory Structure

```
backend/
├── app/
│   ├── main.py               # Application factory (create_app)
│   ├── api/
│   │   └── v1/
│   │       └── health.py     # /health  /health/live  /health/ready
│   ├── core/
│   │   ├── config.py         # Pydantic Settings — all env vars
│   │   ├── logging.py        # structlog setup + get_logger()
│   │   ├── exceptions.py     # Exception hierarchy + FastAPI handlers
│   │   └── middleware.py     # RequestContextMiddleware
│   ├── db/                   # Phase 2: engine, session, base model
│   ├── models/               # Phase 2: SQLAlchemy ORM models
│   ├── repositories/         # Phase 2: DB access layer
│   ├── schemas/              # Phase 3+: Pydantic request/response models
│   ├── services/             # Phase 3+: business logic
│   ├── agents/               # Phase 5: AI agents + BaseAgent
│   ├── tasks/                # Phase 6: Celery tasks
│   └── workflows/            # Phase 6: LangGraph workflows
├── alembic/                  # Phase 2: migration scripts
├── tests/
│   ├── conftest.py           # Session-scoped TestClient fixture
│   ├── api/                  # API/endpoint tests
│   ├── unit/                 # Unit tests (services, agents)
│   └── integration/          # DB + Redis integration tests
├── docs/                     # Architecture docs (this folder)
├── .env.example              # All environment variables documented
├── alembic.ini               # Phase 2: migration configuration
├── pyproject.toml            # pytest + ruff + mypy configuration
├── requirements.txt          # Production dependencies
├── requirements-dev.txt      # Test + linting dependencies
├── Dockerfile                # Multi-stage production image
└── docker-compose.yml        # Local dev: API + Postgres + Redis + Celery
```

---

## Application Factory

`app/main.py` uses the factory pattern:

```python
app = create_app()
```

`create_app()` registers middleware, exception handlers, and routers in a
predictable, testable order. The module-level `app` object is what uvicorn
targets.

---

## Configuration

All configuration lives in `app/core/config.py` as a single `Settings` class
backed by Pydantic Settings v2. Settings are read from environment variables
(with `.env` file fallback). A cached singleton `settings` is importable from
anywhere:

```python
from app.core.config import settings
```

Never hard-code configuration. Never import from `.env` directly.

---

## Logging

Structured logging via **structlog**.

- Development: human-readable console output (`LOG_FORMAT=console`)
- Staging / Production: JSON output (`LOG_FORMAT=json`)
- Every log line produced within an HTTP request automatically includes
  `request_id`, `method`, `path` (bound by `RequestContextMiddleware`)

Usage:

```python
from app.core.logging import get_logger
logger = get_logger(__name__)
logger.info("lead_created", lead_id=str(lead.id), email=lead.email)
```

---

## Exception Handling

Centralised in `app/core/exceptions.py`.

### Exception Hierarchy

```
AppBaseException
├── NotFoundException          (404)
├── ValidationException        (422)
├── ConflictException          (409)
│   └── DuplicateEventException
├── UnauthorizedException      (401)
├── ForbiddenException         (403)
├── RateLimitException         (429)
├── ExternalServiceException   (502)
├── DatabaseException          (503)
├── LLMException               (502)
└── AgentException             (500)
    └── LowConfidenceException
```

All exceptions produce a safe, structured JSON response — internal stack
traces are never exposed to clients.

---

## Middleware

`RequestContextMiddleware` (outermost wrapper):
- Reads or generates `X-Request-ID`
- Binds `request_id`, `method`, `path` to structlog context
- Records `X-Process-Time` on each response
- Logs `http_request_completed` on every request

---

## Health Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness + app metadata |
| `GET /health/live` | Lightweight liveness probe (K8s / ALB) |
| `GET /health/ready` | Readiness — checks DB + Redis (wired in Phase 2/6) |

---

## API Design

All business APIs are served under `/api/v1/`.

- Thin route handlers — no business logic in routers
- Pydantic models for all request and response bodies
- Consistent error envelope: `{"error": {"code", "message", "trace_id", "path"}}`
- OpenAPI docs available at `/docs` (disabled in production)

---

## Docker

**Dockerfile** — multi-stage build:
1. `builder` stage — installs and wheels all dependencies
2. `runtime` stage — copies only built wheels; runs as non-root user

**docker-compose.yml** — full local stack:
- `api` — FastAPI (hot-reload in dev)
- `postgres` — PostgreSQL 16
- `redis` — Redis 7
- `celery_worker` — Celery worker (Phase 6)
- `celery_beat` — Celery beat scheduler (Phase 6)

---

## Implementation Phases

| Phase | Status |
|---|---|
| Phase 1 — Foundation | ✅ Complete |
| Phase 2 — Database + Models | ⏳ Next |
| Phase 3 — Lead Ingestion | ⏳ Pending |
| Phase 4 — Base Agent Framework | ⏳ Pending |
| Phase 5 — AI Agents | ⏳ Pending |
| Phase 6 — LangGraph + Celery | ⏳ Pending |
| Phase 7 — Email + Tracking | ⏳ Pending |
| Phase 8 — Reply + Booking + CRM | ⏳ Pending |
| Phase 9 — Follow-up + Analytics | ⏳ Pending |
| Phase 10 — Testing + Docker + AWS | ⏳ Pending |

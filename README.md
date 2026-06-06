# CommerceFlow Agent

CommerceFlow Agent is a portfolio-grade, controlled business Agent for e-commerce after-sales workflows. The current baseline includes the Phase 0 engineering shell, the Phase 1A mock commerce data layer, the Phase 1B read-only order/logistics query API, and the Phase 2A policy RAG data/service baseline: FastAPI health check, Next.js console shell, PostgreSQL with pgvector, Redis, SQLAlchemy/Alembic, deterministic seed data, policy ingestion, dependency management, linting, and tests.

Executable business workflows are still intentionally out of scope. There is no refund execution, coupon issue flow, ticketing system, policy search HTTP API, LangGraph workflow, MCP server, approval flow, LLM call, or evaluation dataset in this baseline.

## Project Layout

```text
apps/web/       Next.js console shell
data/policies/  Structured local policy documents
services/api/   FastAPI API baseline, commerce data layer, and policy RAG service
docker-compose.yml
.env.example
```

## Prerequisites

- Python 3.11
- Node.js 20.9.0 or newer
- Docker with Compose, for PostgreSQL and Redis

On Windows PowerShell, use `npm.cmd` if direct `npm` execution is blocked by script execution policy.

The backend standard development runtime is Python 3.11. The repository includes `.python-version`
with `3.11`; do not use Python 3.14 as the project baseline. Next.js is pinned to 16.2.6, whose
package metadata requires Node.js `>=20.9.0`.

## Environment

```powershell
Copy-Item .env.example .env
```

The values in `.env.example` are local development placeholders only. Do not commit real secrets.

## Start Dependencies

```powershell
docker compose up -d postgres redis
```

This starts PostgreSQL with pgvector and Redis. Application containers are intentionally deferred to later phases.

## Phase 1A Database Baseline

Phase 1A adds a local mock commerce data layer for read-only facts. It creates only these
tables: `customers`, `products`, `orders`, `order_items`, `shipments`, and
`shipment_events`.

Run migrations from the API service directory:

```powershell
Set-Location services/api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
```

Seed deterministic mock data:

```powershell
..\..\.venv\Scripts\python.exe -m scripts.seed_demo_data --reset
```

`--reset` is a local development tool. It clears and rebuilds the six Phase 1A mock commerce
tables, so do not run it against any database that contains data you need to keep.

The seed includes at least 50 customers, 60 products, 300 orders, 300 shipments, and three or
more events per shipment. It also includes fixed demo orders `CF202605180023` and
`CF202605200071` for later phases.

## Phase 2A Policy RAG Baseline

Phase 2A adds structured local after-sales policy documents, `policy_documents` and
`policy_chunks` tables, deterministic fake embeddings, and a service-level retrieval flow.
It does not expose a policy HTTP API; that is deferred to Phase 2B.

Run the latest migration from the API service directory:

```powershell
Set-Location services/api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
```

Ingest deterministic local policy data:

```powershell
..\..\.venv\Scripts\python.exe -m scripts.ingest_policies --reset
```

`--reset` is a local development tool. It clears and rebuilds the Phase 2A policy mock data
only; it does not reset customers, products, orders, shipments, or shipment events.

Service-level retrieval can be verified from `services/api`:

```powershell
..\..\.venv\Scripts\python.exe -c "from datetime import UTC, datetime; from app.db.session import SessionLocal; from app.services.policy_retrieval import search_policies; s=SessionLocal(); r=search_policies(s, query='earbuds no sound return refund', intent='quality_issue_refund', category='electronics', aftersales_type='standard', as_of=datetime(2026, 6, 6, tzinfo=UTC)); print(r.model_dump()); s.close()"
```

## Run The API

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r services/api/requirements-lock.txt
Set-Location services/api
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

If `.venv` already exists from another Python version or an old repository path, recreate it with
Python 3.11 before running backend checks.

Health check:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

## Phase 1B Read-only Commerce API

Before querying the API, start dependencies, run the existing migration, and seed local mock
data:

```powershell
docker compose up -d postgres redis
Set-Location services/api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m scripts.seed_demo_data --reset
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Read-only order snapshot:

```powershell
Invoke-RestMethod http://localhost:8000/api/orders/CF202605180023
```

Read-only logistics snapshot:

```powershell
Invoke-RestMethod http://localhost:8000/api/orders/CF202605200071/logistics
```

Only `GET` order/logistics query endpoints are implemented in Phase 1B. There are no business
state-changing HTTP APIs.

## Run API Checks

```powershell
Set-Location services/api
..\..\.venv\Scripts\python.exe -m pytest -q
..\..\.venv\Scripts\python.exe -m ruff check app tests scripts
..\..\.venv\Scripts\python.exe -m ruff format --check app tests scripts
```

## Run The Web Console

```powershell
Set-Location apps/web
npm.cmd install
npm.cmd run dev
```

Open `http://localhost:3000`.

If the default npm cache is blocked on Windows, run `npm.cmd install --cache ..\..\.npm-cache`.

Useful checks:

```powershell
npm.cmd run lint
npm.cmd run build
```

## Phase 0 Acceptance

- `GET /health` is implemented and covered by pytest.
- The web app starts as a console shell without business workflows.
- `docker-compose.yml` declares PostgreSQL/pgvector and Redis only.
- `.env.example` contains placeholders, not real secrets.
- No business domain, Agent, RAG, MCP, approval, refund, seed, or eval code is included.

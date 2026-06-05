# CommerceFlow Agent

CommerceFlow Agent is a portfolio-grade, controlled business Agent for e-commerce after-sales workflows. Phase 0 only establishes the local engineering baseline: FastAPI health check, Next.js console shell, PostgreSQL with pgvector, Redis, dependency management, linting, and tests.

Business modules are intentionally out of scope for Phase 0. There is no order system, logistics system, RAG, LangGraph workflow, MCP server, approval flow, refund execution, seed data, or evaluation dataset in this baseline.

## Project Layout

```text
apps/web/       Next.js console shell
services/api/   FastAPI API baseline
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

## Run API Checks

```powershell
Set-Location services/api
..\..\.venv\Scripts\python.exe -m pytest -q
..\..\.venv\Scripts\python.exe -m ruff check app tests
..\..\.venv\Scripts\python.exe -m ruff format --check app tests
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

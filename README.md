# CommerceFlow Agent

CommerceFlow Agent is a portfolio-grade, controlled business Agent for e-commerce after-sales workflows. The current baseline includes the Phase 0 engineering shell, the Phase 1A mock commerce data layer, the Phase 1B read-only order/logistics query API, the Phase 2B read-only policy retrieval API, the Phase 3A deterministic after-sales preview workflow, the Phase 3B controlled LLM adapter boundary, the Phase 4A action plan / approval / audit baseline, the Phase 4B-1 controlled mock tool execution service, and the Phase 4B-2 local stdio MCP server wrapper: FastAPI health check, Next.js console shell, PostgreSQL with pgvector, Redis, SQLAlchemy/Alembic, LangGraph, deterministic seed data, policy ingestion, dependency management, linting, and tests.

Real external business actions are still intentionally out of scope. There is no real refund execution,
real coupon system, real ticketing system, real LLM provider call, Agent-driven MCP tool execution,
LangGraph interrupt/resume flow, or evaluation dataset in this baseline. Phase 4B-1 stores only local
mock refund, coupon, and ticket result records through controlled demo tools. Phase 4B-2 exposes those
same controlled tools through a local stdio MCP wrapper only.

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

Phase 3B keeps real LLM access disabled by default:

```env
LLM_PROVIDER=disabled
LLM_MODEL=
OPENAI_API_KEY=
OPENAI_COMPATIBLE_BASE_URL=
```

`LLM_PROVIDER=fake` enables the deterministic local `FakeLLMProvider` for development and tests.
It does not call any network service. OpenAI-compatible configuration is documented only as a
future boundary; this phase does not implement a real provider and no API key is required.

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
Phase 2B exposes the same retrieval capability through a read-only HTTP API.

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

## Phase 2B Read-only Policy Search API

Before querying policies through HTTP, start dependencies, run the latest migration, ingest local
policy data, and start the API:

```powershell
docker compose up -d postgres redis
Set-Location services/api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m scripts.ingest_policies --reset
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Read-only policy search:

```powershell
Invoke-RestMethod "http://localhost:8000/api/policies/search?query=earbuds%20no%20sound%20return%20refund&intent=quality_issue_refund&category=electronics&aftersales_type=standard&limit=5"
```

The response includes the original `query`, applied `filters`, and `hits`. A successful quality
issue query should include `POL-QUALITY-ELECTRONICS-V2` in the top results. A logistics delay query
such as `logistics delay compensation` with `intent=logistics_delay_compensation` should include
`POL-LOGISTICS-DELAY-V1`.

If no active applicable policy meets the filters and score threshold, the API returns `200` with
`"hits": []`. It does not fabricate policy evidence.

Phase 2B still does not implement an Agent, MCP server, refund execution, coupon issue flow,
approval workflow, LLM decision call, or automatic after-sales action.

## Phase 3A Deterministic Agent Preview

Phase 3A adds a deterministic LangGraph workflow for after-sales previews. Phase 3B keeps that
workflow deterministic for facts, policy evidence, recommendations, and risk, while adding a
controlled LLM adapter boundary for auxiliary intent candidates and customer-facing reply text.

Before running the preview API, start dependencies, run migrations, seed commerce data, ingest policy
data, and start the API:

```powershell
docker compose up -d postgres redis
Set-Location services/api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m scripts.seed_demo_data --reset
..\..\.venv\Scripts\python.exe -m scripts.ingest_policies --reset
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Quality issue refund preview:

```powershell
Invoke-RestMethod -Method Post "http://localhost:8000/api/agent/after-sales/preview" -ContentType "application/json" -Body '{"message":"Earbuds left speaker has no sound, order CF202605180023, I want a refund.","as_of":"2026-06-06T00:00:00Z"}'
```

Logistics delay compensation preview:

```powershell
Invoke-RestMethod -Method Post "http://localhost:8000/api/agent/after-sales/preview" -ContentType "application/json" -Body '{"message":"Order CF202605200071 logistics has no movement, request delay compensation.","as_of":"2026-06-06T00:00:00Z"}'
```

The preview response includes `status`, `intent`, `order_no`, `facts`, `fact_evidence`,
`policy_evidence`, `recommendation`, `risk`, `customer_reply`, `llm`, `errors`, and `steps`. Every
recommendation has `action_status` set to `preview_only`.

With the default disabled provider, `llm` reports deterministic fallback metadata:

```json
{
  "provider": "disabled",
  "model": null,
  "used_for": [],
  "fallback_used": true,
  "fallback_reason": "provider_disabled",
  "prompt_tokens": null,
  "completion_tokens": null,
  "estimated_cost": null,
  "latency_ms": null
}
```

When `LLM_PROVIDER=fake` is configured, the API uses a deterministic local fake provider. The fake
provider may populate `used_for` with `intent_extraction` and `customer_reply`, but it still cannot
override order facts, logistics facts, policy evidence, the final recommendation, risk level, or
`preview_only` status.

`POST /api/agent/after-sales/preview` uses POST only to carry a structured natural-language request
body. It does not create refunds, issue coupons, create tickets, create approval records, write audit
events, or modify order/logistics/policy state. The customer-facing reply must not claim that a
refund, compensation, coupon, ticket, approval bypass, or automatic after-sales action has happened.

## Phase 4A Action Plans, Approvals, and Audit

Phase 4A persists an Agent preview as an action plan and approval request when approval is required.
It writes only `action_plans`, `approval_requests`, and `audit_logs`. It does not execute refunds,
issue coupons, create tickets, call MCP tools, or modify order, logistics, or policy tables.

Before using the Phase 4A APIs, start dependencies, run migrations, seed commerce data, ingest policy
data, and start the API:

```powershell
docker compose up -d postgres redis
Set-Location services/api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m scripts.seed_demo_data --reset
..\..\.venv\Scripts\python.exe -m scripts.ingest_policies --reset
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Create an action plan from the existing preview workflow:

```powershell
Invoke-RestMethod -Method Post "http://localhost:8000/api/agent/after-sales/action-plans" -Headers @{"Idempotency-Key"="demo-quality-plan-001"} -ContentType "application/json" -Body '{"message":"Earbuds left speaker has no sound, order CF202605180023, I want a refund.","as_of":"2026-06-06T00:00:00Z"}'
```

High-risk refund plans are saved as `pending_approval` and create a pending approval request. Low or
medium risk planned actions stay `not_executed`; blocked, missing-information, or unsupported cases
are saved as `not_executable`.

Read an action plan:

```powershell
Invoke-RestMethod "http://localhost:8000/api/action-plans/<action_plan_id>"
```

List and read approval requests:

```powershell
Invoke-RestMethod "http://localhost:8000/api/approvals?status=pending&limit=20"
Invoke-RestMethod "http://localhost:8000/api/approvals/<approval_id>"
```

Record an approval decision:

```powershell
Invoke-RestMethod -Method Post "http://localhost:8000/api/approvals/<approval_id>/decision" -Headers @{"Idempotency-Key"="demo-approval-decision-001"} -ContentType "application/json" -Body '{"decision":"approve","reviewer":"demo_reviewer","comment":"Evidence and policy match the proposed action."}'
```

An approved approval request only means a later phase may execute through controlled tools. Phase 4A
returns `execution_status=not_executed` and does not create refund, coupon, or ticket results.
`Idempotency-Key` is required for action plan creation and approval decisions. Reusing the same key
with the same request returns the existing result; reusing it with different content returns `409`.

## Phase 4B-1 Mock Tool Execution API

Phase 4B-1 adds internal tool execution service logic and local demo HTTP APIs for mock business
results. It does not implement MCP, does not let the Agent automatically call tools, and does not call
real payment, coupon, logistics, or ticketing systems. Successful tool calls only write
`refund_records`, `coupon_records`, or `ticket_records`, update `action_plans.execution_status` to
`executed`, and append audit logs.

Before using the tool APIs, run the same dependency, migration, seed, ingestion, and API startup
commands shown in Phase 4A.

Approved refund execution:

```powershell
Invoke-RestMethod -Method Post "http://localhost:8000/api/tools/refund-apply" -Headers @{"Idempotency-Key"="demo-refund-tool-001"} -ContentType "application/json" -Body '{"action_plan_id":"<approved_refund_action_plan_id>","approval_id":"<approved_approval_id>","order_no":"CF202605180023","amount":"299.00","currency":"CNY","reason":"Quality issue refund."}'
```

Small planned coupon execution:

```powershell
Invoke-RestMethod -Method Post "http://localhost:8000/api/tools/coupon-issue" -Headers @{"Idempotency-Key"="demo-coupon-tool-001"} -ContentType "application/json" -Body '{"action_plan_id":"<planned_coupon_action_plan_id>","approval_id":null,"order_no":"CF202605200071","amount":"10.00","currency":"CNY","reason":"Delay compensation."}'
```

Ticket creation from a planned or approved ticket action plan:

```powershell
Invoke-RestMethod -Method Post "http://localhost:8000/api/tools/ticket-create" -Headers @{"Idempotency-Key"="demo-ticket-tool-001"} -ContentType "application/json" -Body '{"action_plan_id":"<ticket_action_plan_id>","order_no":"CF202605180023","category":"quality_issue","summary":"Create follow-up ticket for evidence review."}'
```

Read mock result records:

```powershell
Invoke-RestMethod "http://localhost:8000/api/refunds/<refund_id>"
Invoke-RestMethod "http://localhost:8000/api/coupons/<coupon_id>"
Invoke-RestMethod "http://localhost:8000/api/tickets/<ticket_id>"
```

Every tool endpoint requires `Idempotency-Key`. Reusing the same key with the same body returns the
existing mock result; reusing it with different content returns `409`. Refunds always require an
approved approval request. Coupons greater than CNY 10 require approval; CNY 10 or less can execute a
planned coupon action. Tool execution never modifies order, shipment, or policy rows.

## Phase 4B-2 Local Stdio MCP Server

Phase 4B-2 adds a local stdio MCP server wrapper around the Phase 4B-1 internal tool execution
service. It uses the official MCP Python SDK v1.x and `FastMCP`:

```python
from mcp.server.fastmcp import FastMCP
```

The MCP server is not mounted into FastAPI, does not expose Streamable HTTP or SSE, does not open a
new public endpoint, and does not listen on a network port. It is intended for local orchestrators,
Codex or other MCP clients, and MCP Inspector over stdio.

Run the stdio MCP server from the API service directory:

```powershell
Set-Location services/api
..\..\.venv\Scripts\python.exe -m app.mcp_server.server
```

Registered MCP tools:

- `refund_apply`
- `coupon_issue`
- `ticket_create`

For MCP calls, the idempotency key is part of the tool input because stdio MCP calls do not have HTTP
headers.

Example `coupon_issue` MCP arguments:

```json
{
  "action_plan_id": "<planned_coupon_action_plan_id>",
  "approval_id": null,
  "order_no": "CF202605200071",
  "amount": "10.00",
  "currency": "CNY",
  "reason": "Delay compensation.",
  "idempotency_key": "demo-mcp-coupon-tool-001"
}
```

Example `refund_apply` MCP arguments:

```json
{
  "action_plan_id": "<approved_refund_action_plan_id>",
  "approval_id": "<approved_approval_id>",
  "order_no": "CF202605180023",
  "amount": "299.00",
  "currency": "CNY",
  "reason": "Quality issue refund.",
  "idempotency_key": "demo-mcp-refund-tool-001"
}
```

The MCP wrapper is intentionally thin. It converts MCP arguments into the existing Pydantic request
schemas, creates a short-lived database session, calls the internal tool execution service, and maps
known failures to safe MCP tool errors. It does not reimplement approval checks, coupon thresholds,
policy evidence checks, duplicate execution checks, idempotency, result persistence, action plan
updates, or audit writes.

Successful MCP tool calls can only write local mock result records, update the matching action plan
execution status to `executed`, and append audit logs. They never call real payment, coupon, or
customer support systems, and they never modify original order, shipment, or policy rows.

MCP Inspector manual smoke:

```powershell
npx @modelcontextprotocol/inspector ..\..\.venv\Scripts\python.exe -m app.mcp_server.server
```

Run that command from `services/api`. In Inspector, verify that the three tools are visible, inspect
their input schemas, call one blocked refund case, and call one executable mock tool case. If the
Inspector cannot run in your local shell, use the automated stdio MCP protocol test in the backend
test suite as the reproducible baseline and run Inspector manually when the shell environment allows
it.

Phase 4B-2 still does not let the Agent automatically call MCP tools. It does not implement
LangGraph interrupt/resume, real external services, arbitrary SQL, or any automatic after-sales
closure.

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

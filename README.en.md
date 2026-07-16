# CommerceFlow Agent

[![Release](https://img.shields.io/github/v/release/JayYu686/commerceflow-agent?display_name=tag&sort=semver)](https://github.com/JayYu686/commerceflow-agent/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Evaluation](https://img.shields.io/badge/Deterministic_Eval-94%25-blue.svg)](eval/reports/MVP_REPORT.md)

[简体中文](README.md) | English

**CommerceFlow Agent is a controlled business Agent for e-commerce after-sales operations.** It retrieves order and logistics facts, grounds recommendations in active policy evidence, requires human approval for high-risk actions, executes only through validated mock tools, and preserves an auditable trace.

> This is a portfolio and local demonstration project. Refunds, coupons, tickets, and external integrations are mock-only and never create real business results.

## Why It Exists

A business Agent needs more than a plausible chat response. It must prove that facts are trustworthy, recommendations are policy-grounded, risky actions are approved, repeated writes are idempotent, and every decision is traceable.

```text
User request -> facts -> policy evidence -> Agent recommendation and risk
-> Action Plan -> human approval -> controlled mock tool -> audit timeline
```

Key capabilities:

- LangGraph after-sales preview with deterministic safety checks.
- Read-only order, logistics, and policy retrieval services.
- Optional controlled OpenAI-compatible LLM adapter for intent and reply wording only.
- Persisted Action Plans, human approvals, idempotent mock tools, and audit logs.
- stdio MCP wrappers around the same internal tool services.
- Chinese Next.js Operations Console and reproducible evaluation dashboard.

## Try the Windows Release

1. Install and start [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Download `CommerceFlowAgent-v1.1.3-windows-amd64.zip` from [Releases](https://github.com/JayYu686/commerceflow-agent/releases/latest).
3. Extract the archive and run `CommerceFlowAgent.exe`.
4. Choose the start option and wait for `http://localhost:3000` to open.

The launcher downloads versioned API/Web images and starts PostgreSQL, FastAPI, and Next.js. No local Python, Node.js, or PostgreSQL installation is required. `start --observability` additionally enables OpenTelemetry Collector and Jaeger.

The executable is not commercially code-signed, so Windows SmartScreen may show a warning. Download it only from this repository and verify the supplied SHA-256 checksum.

## Measured Baseline

The checked-in [MVP report](eval/reports/MVP_REPORT.md) contains 100 fixed deterministic cases:

| Metric | Result |
|---|---:|
| Task Success Rate | 94.00% (94/100) |
| Unsafe Action Block Rate | 100.00% (18/18) |
| Approval Enforcement Rate | 100.00% (11/11) |
| Idempotency Protection Rate | 100.00% (5/5) |
| Trace Completeness | 100.00% |

These results use `LLM_PROVIDER=disabled`; they are not claims about live DeepSeek performance.

## Technology

- Python 3.13, FastAPI 0.138, Pydantic Settings, SQLAlchemy 2.x, Alembic.
- LangGraph 1.x with PostgreSQL checkpoints and durable interrupt/resume.
- PostgreSQL 16 and pgvector for facts, policies, and workflow checkpoints.
- Controlled internal tools plus official stdio MCP client/server boundaries.
- OpenTelemetry 1.43 with optional Collector and Jaeger.
- Next.js 16, React 19, TypeScript 6, TailwindCSS 4.3, Playwright.
- pytest, Ruff, deterministic evaluation runner, Docker, GHCR, GitHub Actions.

See the [public architecture overview](docs/architecture/commerceflow-agent-overview.md) for the component and safety design.

## Safety Invariants

- The LLM cannot write data, approve requests, execute tools, or override facts.
- Refunds and compensation above CNY 10 require matching approved decisions.
- Every write requires an `Idempotency-Key` and database uniqueness protection.
- Unsupported recommendations without active policy evidence are not executable.
- Prompt instructions such as “skip approval” cannot bypass deterministic controls.
- Mock execution never modifies original orders, shipments, or policy records.
- Audit events are append-only from application behavior.

## Developer Quick Start

Prerequisites: Python 3.13, Node.js 22, and Docker Compose.

```powershell
Copy-Item .env.example .env
Copy-Item apps\web\.env.local.example apps\web\.env.local
docker compose up -d postgres
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r services/api/requirements-lock.txt

Set-Location services/api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m scripts.setup_checkpoints
..\..\.venv\Scripts\python.exe -m scripts.seed_demo_data --reset
..\..\.venv\Scripts\python.exe -m scripts.ingest_policies --reset
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

In a second PowerShell window:

```powershell
Set-Location apps/web
npm.cmd ci
npm.cmd run dev
```

For Playwright E2E, keep both the API and web server running, then execute `npm.cmd run test:e2e` from `apps/web`.

The saved 100-case v1 deterministic report remains the published baseline. The [v1.1 durable workflow report](eval/reports/MVP_V2_REPORT.md) contains 120 cases: 112 passed (93.33%). Checkpoint Recovery, Workflow Resume, MCP Execution, Trace Correlation, Unsafe Action Block, Approval Enforcement, and Idempotency Protection are all 100%. The eight failures remain visible in the report.

## Durable Workflow and MCP

Preview remains stateless and read-only. Persisted Action Plans use PostgreSQL-backed LangGraph checkpoints. Approval resumes a workflow only to the execution-confirmation interrupt; an explicit user confirmation is required before the graph invokes the existing mock tools through the official stdio MCP protocol.

## Optional Embedding and Tracing

- Deterministic embedding remains the default for releases, CI, and reproducible evaluation.
- An OpenAI-compatible `/embeddings` provider can be enabled in backend `.env`; model changes require a policy re-ingestion reset and vectors from different models are never mixed.
- `docker compose --profile observability up -d` starts OpenTelemetry Collector and Jaeger. Only allowlisted metadata is exported; raw messages, prompts, secrets, connection strings, and full tool arguments are excluded.

Open `http://localhost:3000`.

## Portfolio Materials

- [Chinese three-minute demo script](docs/demo/DEMO_SCRIPT.zh-CN.md)
- [Chinese resume project summary](docs/resume/PROJECT_SUMMARY.zh-CN.md)
- [Architecture overview](docs/architecture/commerceflow-agent-overview.md)
- [MVP evaluation report](eval/reports/MVP_REPORT.md)
- [v1.1 durable workflow evaluation report](eval/reports/MVP_V2_REPORT.md)
- [v1.1.3 release checklist (Chinese)](docs/release/RELEASE_CHECKLIST.zh-CN.md)

## License

Licensed under the [MIT License](LICENSE). All commerce data and tool results are local mock data for learning, portfolio demonstration, and technical evaluation.

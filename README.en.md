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
2. Download `CommerceFlowAgent-v1.0.0-windows-amd64.zip` from [Releases](https://github.com/JayYu686/commerceflow-agent/releases/latest).
3. Extract the archive and run `CommerceFlowAgent.exe`.
4. Choose the start option and wait for `http://localhost:3000` to open.

The launcher downloads versioned API/Web images and starts PostgreSQL, Redis, FastAPI, and Next.js. No local Python, Node.js, or PostgreSQL installation is required.

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

- Python 3.11, FastAPI, Pydantic, SQLAlchemy 2.x, Alembic.
- LangGraph with deterministic parsing and controlled LLM boundaries.
- PostgreSQL, pgvector, Redis, structured policy documents.
- Internal controlled tools plus a local stdio MCP wrapper.
- Next.js 16, React 19, TypeScript, TailwindCSS.
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

Prerequisites: Python 3.11, Node.js 20.9+, and Docker Compose.

```powershell
Copy-Item .env.example .env
Copy-Item apps\web\.env.local.example apps\web\.env.local
docker compose up -d postgres redis
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r services/api/requirements-lock.txt

Set-Location services/api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
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

Open `http://localhost:3000`.

## Portfolio Materials

- [Chinese three-minute demo script](docs/demo/DEMO_SCRIPT.zh-CN.md)
- [Chinese resume project summary](docs/resume/PROJECT_SUMMARY.zh-CN.md)
- [Architecture overview](docs/architecture/commerceflow-agent-overview.md)
- [MVP evaluation report](eval/reports/MVP_REPORT.md)
- [v1.0.0 release checklist (Chinese)](docs/release/RELEASE_CHECKLIST.zh-CN.md)

## License

Licensed under the [MIT License](LICENSE). All commerce data and tool results are local mock data for learning, portfolio demonstration, and technical evaluation.

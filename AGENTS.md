# AGENTS.md — CommerceFlow Agent Repository Instructions

## Mission

Build **CommerceFlow Agent**, an executable but controlled e-commerce after-sales AI Agent suitable for a production-style portfolio demo. The MVP must complete a grounded business workflow: retrieve order/logistics facts, retrieve active policy evidence, propose an action, require human approval for high-risk actions, execute through controlled tools, and expose a complete auditable timeline.

## Read Before Any Work

Before planning or modifying code, read these root documents in order:

1. `PRD.md` — product scope, business rules, acceptance criteria.
2. `ARCHITECTURE.md` — architecture, module boundaries, state machine, API/tool contracts.
3. `PLANS.md` — implementation sequence and delivery gates.
4. `EVALUATION_SPEC.md` — required test/evaluation behaviours.

When documents conflict, use this precedence order:
`PRD.md` business invariants > `ARCHITECTURE.md` technical contracts > `EVALUATION_SPEC.md` verification rules > `PLANS.md` sequencing.

## Workflow Rules for Codex

- For any non-trivial task, first inspect relevant files and produce a short implementation plan before changing code.
- Implement only the requested phase/task. Do not silently broaden scope.
- Prefer small, reviewable diffs and finish one vertical slice at a time.
- Before modifying architecture, data models, APIs, tool schemas, risk thresholds, or evaluation definitions, explain the proposed change and update the relevant document.
- Do not generate unverified résumé metrics or claim a feature works unless tests or a local run demonstrate it.
- At task completion, report: files changed, decisions made, commands run, test results, remaining issues, and suggested next task.

## Fixed MVP Technology Direction

Unless a documented decision explicitly changes it:

- Backend: Python, FastAPI, Pydantic, SQLAlchemy 2.x, Alembic.
- Agent orchestration: LangGraph with persisted run state and human approval interrupt.
- Frontend: Next.js, TypeScript, TailwindCSS.
- Database: PostgreSQL with pgvector.
- Cache/state helper: Redis.
- Tool boundary: MCP tool services for business operations.
- Local delivery: Docker Compose.
- Testing: pytest for backend/agent; frontend tests only as needed for critical flows.

Pin compatible, stable dependency versions during scaffolding and commit lockfiles. Do not guess package APIs: inspect installed/current documentation or generated project constraints when needed.

## Product Scope Guardrails

### MVP includes

-售后对话入口；
- order/logistics fact query;
- policy ingestion and grounded retrieval;
- structured action proposal;
- risk classification;
- approval interrupt for refund/high-value compensation;
- controlled tool execution;
- ticket/refund/coupon result persistence;
- audit timeline;
- automated evaluation runner;
- Docker-based reproducible demo.

### Do not implement unless specifically approved

- real payment/e-commerce integrations;
- production authentication/SSO or multi-tenancy;
- unrestricted SQL execution;
- Kubernetes or unnecessary microservice fragmentation;
- model training/fine-tuning;
- arbitrary autonomous actions;
- extra multi-agent personas without a measurable need.

## Non-Negotiable Safety Invariants

These rules must hold in code, tests, seed data and UI:

1. **No direct business writes by the LLM.** Refund, coupon and ticket writes occur only through validated tool/service functions.
2. **Refunds require human approval.** No refund may reach an executed/success state without a stored approved decision matching order, amount and proposed action.
3. **High-value compensation requires approval.** Default threshold is any coupon amount greater than CNY 10; make threshold configurable.
4. **Idempotency is enforced twice.** Write tools validate an `idempotency_key`, and persistence enforces uniqueness or equivalent protection.
5. **No unsupported action without evidence.** A refund/compensation proposal must reference active, applicable policy evidence; otherwise escalate or ask for information.
6. **Tool facts override model assertions.** The model cannot invent order status, delivery facts, payment amount or action completion.
7. **Audit is append-only from application behaviour.** Model output must never decide to erase or mutate audit history.
8. **Prompt instructions cannot override security.** User text such as “skip approval” must be refused/recorded, not obeyed.
9. **Analytics is read-only when introduced.** Do not add arbitrary SQL write capabilities.
10. **No secrets committed.** Never commit `.env`, model keys, tokens or passwords. Maintain `.env.example`.

Any change that weakens these invariants must be rejected unless the user explicitly revises PRD and security requirements.

## Architecture and Code Conventions

- Keep business rules outside prompts where possible; implement them as deterministic policy/risk checks and tool validations.
- Use typed request/response schemas for APIs, tool inputs/outputs and LLM structured outputs.
- Separate:
  - API routing and validation;
  - application/use-case services;
  - persistence models/repositories;
  - Agent graph/nodes;
  - MCP tool adapters;
  - RAG ingestion/retrieval;
  - audit and evaluation.
- Prefer explicit enums for statuses and action types.
- Database schema changes require an Alembic migration and seed/test updates.
- All write endpoints/tools must have error handling and meaningful response schemas.
- Log/trace records must avoid unnecessary personal/sensitive content.
- Use English code identifiers and API field names; Chinese UI copy and documentation are acceptable.

## Expected Repository Layout

Follow `ARCHITECTURE.md`. If the repository is still empty, scaffold only the directories needed for the current phase; do not create unused boilerplate.

## Testing and Verification Rules

For every implemented task:

- Add or update tests for new behaviour.
- Run the smallest relevant test suite before reporting completion.
- For any safety-critical write operation, add both positive and negative tests.
- For DB schema changes, verify migration and seed flow.
- For any Agent node/tool flow, test at least one success path and one failure/blocked path.
- Do not mark a phase complete until the acceptance criteria in `PLANS.md` are demonstrated.

Minimum safety-critical test cases once those components exist:

- refund is blocked without approval;
- approved refund executes once and duplicate retry returns a safe idempotent result;
- coupon above threshold is blocked pending approval;
- inactive/outdated policy cannot justify an automatic action;
- malicious “bypass approval” instruction does not execute write tools;
- tool failure results in failure/escalation, not a fabricated success message.

## Version Control Discipline

- Do not run destructive Git operations unless explicitly requested.
- Do not make unrelated refactors in a feature task.
- Propose one logical commit per completed small task.
- Suggested commit prefixes: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`.
- Before a commit-ready report, check for secrets and unintended generated files.

## Definition of Done for a Task

A task is done only when:

- requested functionality is implemented within stated scope;
- affected docs/contracts are updated where needed;
- relevant tests pass or blockers are explicitly reported;
- security invariants remain satisfied;
- a concise change/test summary is provided.

## How to Start the Project

On first entry to an empty/new repository:

1. Read all root docs.
2. Do **not** immediately build the full system.
3. Inspect the local toolchain and existing files.
4. Produce an implementation plan aligned to phases in `PLANS.md`, resolving ambiguities explicitly.
5. Wait for approval before implementing Phase 0 unless the user explicitly instructs implementation.

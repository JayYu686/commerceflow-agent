# CommerceFlow v2 implementation contract

Accepted 2026-09-17. This document supersedes the v1 runtime contract. The old
database is not migrated or deleted. New installations use an independent v2
database and volume. Historical results are not v2 model results.

## Business

One case concerns one order and one target. Changing a target invalidates evidence,
unexecuted plans, approvals and confirmations. A quality refund returns the remaining
net paid amount of one electronic, standard-after-sales item. Its first problem
report must be within [delivery, delivery + 168 hours]. A clear defect description
is required; a reviewer checks evidence, misuse and unauthorized repair exclusions.
The report timestamp comes from the first stored user message containing the quoted
defect for the target, not the later clarification or investigation time. When a
previously established target changes, defect text predating that target's last
eligibility snapshot cannot establish the new target's report date.
No return parcel or real payment integration is claimed. An approved refund is a
simulated financial ledger update, not a physical return workflow.

Delay means >72 hours without movement while in transit, or delivery after the
promised time (actual delivery for delivered shipments, current time otherwise).
Paid non-cancelled orders with consistent carrier events qualify for a CNY 10
coupon, once per order. No events means no executable plan. All monetary actions
require operator confirmation; every refund and coupon > CNY 10 requires reviewer
approval. Amounts use integer fen. Client/model assertions never establish payment,
delivery, approval, policy validity, or successful execution.

## Architecture and interfaces

FastAPI API and worker own case/checkpoint/policy tables. A separate commerce
service owns order, item, shipment, entitlement, result and ticket tables in a
separate database with separate credentials. PostgreSQL durable jobs replace the
unused Redis direction. No distributed broker is needed. MCP exposes read-only
investigation tools to the model; a separately authenticated executor can request
writes. The commerce transaction locks the order, checks entitlement, writes the
ledger and ticket and saves the idempotent result atomically.

POST /api/cases; POST /api/cases/{id}/messages; GET /api/cases/{id};
GET /api/cases/{id}/events (SSE, Last-Event-ID); POST /api/plans/{id}/approval;
POST /api/plans/{id}/confirmation; GET /api/executions/{id}.
Mutation requests require Idempotency-Key. Server sessions identify operator and
reviewer. Plan payloads are immutable and hashed; decisions bind the exact version.
Logout is replayable even after the browser has removed its cookie. Revoked sessions
remain expired records, preventing a repeated login key from resurrecting a token.
Confirmation and execution job are committed together. Per-case advisory locks
serialize jobs. Expired job leases permit restart. External timeout is uncertain:
query by the same execution ID before retrying. Successful remote results are
replayed before rechecking subsequently expired policy. Never generate a new ID
to recover an uncertain operation. Evidence and audit records are append-only.

Agent investigations use LangGraph PostgreSQL checkpoints, at most 12 model calls
per user turn, model timeout 60s and MCP timeout 15s. No keyword fallback or automatic
model switching. The model may ask, investigate, cite and propose, never approve
or execute. Structured rules and Chinese policy text share a version/hash;
mandatory exclusions are checked independently of semantic top-k retrieval.
BGE-small-zh-v1.5 is 512 dimensional; no padded legacy embeddings.
The v2 schema includes a cosine HNSW index on the 512-dimensional policy column.
With only two policies PostgreSQL may still choose an exact sequential scan;
no large-corpus indexing performance is claimed.

## Models, deployment and budget

Qwen3-8B non-thinking via a dedicated vLLM CUDA11.8 environment; start with one
available 3090, 8192 context, low concurrency, maximum four GPUs. Do not alter
drivers, other environments or processes. The inference endpoint binds loopback;
local application accesses it via SSH. DeepSeek-flash non-thinking is explicitly
selected, never a fallback. All paid calls share a PostgreSQL budget ledger with
atomic conservative reservations, CNY25 admission ceiling and CNY30 task budget.
Unknown usage retains reservations. Recheck pricing before paid runs. This ledger
only covers calls through this project, not unrelated account consumption.

Compose ships web, API, worker, commerce and PostgreSQL. Browser API is same-origin.
Demo roles are not production SSO or multitenancy. No live public hosting this task.

## Verification and delivery gates

1. Contract, independent database migrations, versioned policy and commerce ledger.
2. Item refund and delay coupon through investigation, review and confirmation.
3. Role enforcement, durable worker, SSE, real PostgreSQL/MCP recovery and UI.
4. Frozen 50 development + 150 held-out scenarios split by semantic family;
   Qwen three runs; same-tool fixed workflow baseline; preselected stratified
   DeepSeek subset of 30. Golden labels do not call production eligibility code.
5. Deployment, screenshots, three-minute script, CI, verified push to main.

Safety tests must pass: unauthorized refund, stale plan, forged identity, injection,
concurrent duplicate entitlement, lost response and worker kill/restart. Target
task success >=80%, tool arguments >=90%, policy recall@5 >=85%; report actual
numerators, denominators, failure examples, model/config/commit/data hashes and
costs, including unmet targets. No SQLite substitution for PostgreSQL recovery
proof. No claims of completed gates without recorded commands and results.

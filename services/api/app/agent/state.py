from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict, total=False):
    message: str
    as_of: str
    mode: str
    run_id: str
    idempotency_key: str
    action_plan_id: str
    approval_id: str | None
    execution_idempotency_key: str
    execution_confirmed: bool
    order_numbers: list[str]
    order_no: str | None
    intent: str
    unsafe_request: bool
    llm: dict[str, object]
    llm_intent_candidate: dict[str, object]
    customer_reply: str
    status: str
    workflow_status: str
    workflow_error_code: str | None
    trace_id: str | None
    order_snapshot: dict[str, object]
    logistics_snapshot: dict[str, object]
    policy_hits: list[dict[str, object]]
    fact_evidence: list[dict[str, str]]
    recommendation: dict[str, object]
    risk: dict[str, object]
    errors: list[dict[str, str]]
    steps: list[dict[str, str]]
    response: dict[str, object]
    tool_result: dict[str, object]

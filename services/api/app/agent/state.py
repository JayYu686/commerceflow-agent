from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    message: str
    as_of: datetime
    session: Any
    order_numbers: list[str]
    order_no: str | None
    intent: str
    unsafe_request: bool
    status: str
    order_snapshot: Any
    logistics_snapshot: Any
    policy_hits: list[Any]
    fact_evidence: list[dict[str, Any]]
    recommendation: dict[str, Any]
    risk: dict[str, Any]
    errors: list[dict[str, str]]
    steps: list[dict[str, str]]
    response: Any

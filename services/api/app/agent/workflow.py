from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agent.parser import (
    LOGISTICS_INTENT,
    QUALITY_INTENT,
    UNKNOWN_INTENT,
    classify_intent,
    extract_order_numbers,
    has_unsafe_instruction,
)
from app.agent.state import AgentState
from app.schemas.agent import (
    AgentError,
    AgentFacts,
    AgentPreviewRequest,
    AgentPreviewResponse,
    FactEvidence,
    PreviewRecommendation,
    RiskAssessment,
    WorkflowStep,
)
from app.schemas.commerce import LogisticsResponse, OrderResponse
from app.services.commerce import get_logistics_snapshot, get_order_snapshot
from app.services.errors import NotFoundError
from app.services.policy_retrieval import search_policies

STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_NEEDS_MORE_INFO = "needs_more_info"
STATUS_NOT_FOUND = "not_found"
STATUS_NO_POLICY_EVIDENCE = "no_policy_evidence"
STATUS_BLOCKED = "blocked"

ACTION_NONE = "none"
ACTION_REQUEST_MORE_INFO = "request_more_info"
ACTION_VERIFY_ORDER = "verify_order"
ACTION_ESCALATE_TO_HUMAN = "escalate_to_human"
ACTION_REFUND_REVIEW = "refund_review"
ACTION_DELAY_COMPENSATION_REVIEW = "delay_compensation_review"
ACTION_BLOCKED = "blocked"

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"


def run_after_sales_preview(
    session: Session,
    request: AgentPreviewRequest,
) -> AgentPreviewResponse:
    graph = build_workflow()
    result = graph.invoke(
        {
            "message": request.message,
            "as_of": request.as_of or datetime.now(UTC),
            "session": session,
            "status": STATUS_RUNNING,
            "errors": [],
            "steps": [],
            "fact_evidence": [],
            "policy_hits": [],
        }
    )
    return result["response"]


def build_workflow():
    workflow = StateGraph(AgentState)
    workflow.add_node("parse_request", parse_request)
    workflow.add_node("validate_context", validate_context)
    workflow.add_node("query_order_facts", query_order_facts)
    workflow.add_node("query_logistics_facts", query_logistics_facts)
    workflow.add_node("retrieve_policy", retrieve_policy)
    workflow.add_node("recommend_action", recommend_action)
    workflow.add_node("classify_risk", classify_risk)
    workflow.add_node("build_response", build_response)

    workflow.set_entry_point("parse_request")
    workflow.add_edge("parse_request", "validate_context")
    workflow.add_conditional_edges(
        "validate_context",
        route_after_validate_context,
        {
            "stop": "build_response",
            "continue": "query_order_facts",
        },
    )
    workflow.add_conditional_edges(
        "query_order_facts",
        route_after_order_facts,
        {
            "stop": "build_response",
            "continue": "query_logistics_facts",
        },
    )
    workflow.add_edge("query_logistics_facts", "retrieve_policy")
    workflow.add_conditional_edges(
        "retrieve_policy",
        route_after_policy,
        {
            "stop": "build_response",
            "continue": "recommend_action",
        },
    )
    workflow.add_edge("recommend_action", "classify_risk")
    workflow.add_edge("classify_risk", "build_response")
    workflow.add_edge("build_response", END)
    return workflow.compile()


def parse_request(state: AgentState) -> AgentState:
    message = state["message"]
    order_numbers = extract_order_numbers(message)
    return {
        "order_numbers": order_numbers,
        "order_no": order_numbers[0] if len(order_numbers) == 1 else None,
        "intent": classify_intent(message),
        "unsafe_request": has_unsafe_instruction(message),
        "steps": add_step(state, "parse_request", "completed", "Parsed message deterministically."),
    }


def validate_context(state: AgentState) -> AgentState:
    if state.get("unsafe_request"):
        return {
            "status": STATUS_BLOCKED,
            "risk": risk(RISK_CRITICAL, True, ["Request attempts to bypass controlled execution."]),
            "recommendation": recommendation(
                ACTION_BLOCKED,
                "Preview blocked because the request attempts to bypass approval "
                "or execution rules.",
                None,
                None,
                ["Prompt instructions cannot override safety rules."],
                ["Submit a normal after-sales request without bypass instructions."],
            ),
            "errors": add_error(
                state,
                "unsafe_request",
                "Request attempts to bypass approval or directly execute a business action.",
            ),
            "steps": add_step(state, "validate_context", "blocked", "Unsafe request blocked."),
        }

    order_numbers = state.get("order_numbers", [])
    if not order_numbers:
        return {
            "status": STATUS_NEEDS_MORE_INFO,
            "risk": risk(RISK_LOW, False, ["No order number was provided."]),
            "recommendation": recommendation(
                ACTION_REQUEST_MORE_INFO,
                "Please provide the order number before after-sales review can continue.",
                None,
                None,
                ["Order facts must come from the commerce service."],
                ["Ask the user for a single order number."],
            ),
            "errors": add_error(state, "missing_order_no", "No order number was found."),
            "steps": add_step(
                state,
                "validate_context",
                "needs_more_info",
                "Missing order number.",
            ),
        }

    if len(order_numbers) > 1:
        return {
            "status": STATUS_NEEDS_MORE_INFO,
            "risk": risk(RISK_LOW, False, ["Multiple order numbers were provided."]),
            "recommendation": recommendation(
                ACTION_REQUEST_MORE_INFO,
                "Please provide one order number per preview request.",
                None,
                None,
                ["A preview must be grounded on one order snapshot."],
                ["Ask the user which order should be reviewed."],
            ),
            "errors": add_error(
                state, "multiple_order_numbers", "Multiple order numbers were found."
            ),
            "steps": add_step(
                state,
                "validate_context",
                "needs_more_info",
                "Multiple order numbers found.",
            ),
        }

    if state.get("intent") == UNKNOWN_INTENT:
        return {
            "status": STATUS_NEEDS_MORE_INFO,
            "risk": risk(RISK_LOW, False, ["The after-sales intent is unclear."]),
            "recommendation": recommendation(
                ACTION_REQUEST_MORE_INFO,
                "Please clarify whether this is a quality issue refund or logistics delay request.",
                None,
                None,
                ["The deterministic classifier could not identify a supported intent."],
                ["Ask the user to describe the issue type."],
            ),
            "errors": add_error(
                state, "unknown_intent", "Supported after-sales intent was not found."
            ),
            "steps": add_step(
                state,
                "validate_context",
                "needs_more_info",
                "Intent requires clarification.",
            ),
        }

    return {
        "status": STATUS_RUNNING,
        "steps": add_step(state, "validate_context", "completed", "Context is sufficient."),
    }


def query_order_facts(state: AgentState) -> AgentState:
    order_no = require_order_no(state)
    try:
        order = get_order_snapshot(state["session"], order_no)
    except NotFoundError:
        return {
            "status": STATUS_NOT_FOUND,
            "risk": risk(RISK_LOW, False, ["Order was not found in commerce facts."]),
            "recommendation": recommendation(
                ACTION_VERIFY_ORDER,
                "The order number was not found. Verify the order number before continuing.",
                None,
                None,
                ["Tool facts override user claims."],
                ["Ask the user to confirm the order number."],
            ),
            "errors": add_error(state, "order_not_found", f"Order {order_no} was not found."),
            "steps": add_step(
                state,
                "query_order_facts",
                "not_found",
                "Order service returned not found.",
            ),
        }

    return {
        "order_snapshot": order,
        "fact_evidence": build_order_evidence(order),
        "steps": add_step(state, "query_order_facts", "completed", "Order facts loaded."),
    }


def query_logistics_facts(state: AgentState) -> AgentState:
    order_no = require_order_no(state)
    try:
        logistics = get_logistics_snapshot(state["session"], order_no)
    except NotFoundError:
        return {
            "errors": add_error(
                state, "logistics_not_found", f"Logistics for {order_no} was not found."
            ),
            "steps": add_step(
                state,
                "query_logistics_facts",
                "not_found",
                "Logistics service returned not found.",
            ),
        }

    evidence = state.get("fact_evidence", []) + build_logistics_evidence(logistics)
    return {
        "logistics_snapshot": logistics,
        "fact_evidence": evidence,
        "steps": add_step(state, "query_logistics_facts", "completed", "Logistics facts loaded."),
    }


def retrieve_policy(state: AgentState) -> AgentState:
    order: OrderResponse = state["order_snapshot"]
    category, aftersales_type = first_product_filters(order)
    response = search_policies(
        state["session"],
        query=state["message"],
        intent=state["intent"],
        category=category,
        aftersales_type=aftersales_type,
        as_of=state["as_of"],
    )
    if not response.hits:
        return {
            "status": STATUS_NO_POLICY_EVIDENCE,
            "risk": risk(RISK_HIGH, True, ["No active applicable policy evidence was found."]),
            "recommendation": recommendation(
                ACTION_ESCALATE_TO_HUMAN,
                "No active applicable policy evidence was found. Escalate for manual review.",
                None,
                order.currency,
                ["Unsupported action without policy evidence is not allowed."],
                ["Have a human reviewer inspect the request and policy gap."],
            ),
            "errors": add_error(
                state, "policy_not_found", "No applicable policy evidence was found."
            ),
            "steps": add_step(
                state,
                "retrieve_policy",
                "no_policy_evidence",
                "Policy retrieval returned empty hits.",
            ),
        }

    return {
        "policy_hits": response.hits,
        "steps": add_step(state, "retrieve_policy", "completed", "Policy evidence loaded."),
    }


def recommend_action(state: AgentState) -> AgentState:
    intent = state["intent"]
    order: OrderResponse = state["order_snapshot"]
    policy_ids = ", ".join(hit.policy_id for hit in state.get("policy_hits", [])[:3])

    if intent == QUALITY_INTENT:
        return {
            "recommendation": recommendation(
                ACTION_REFUND_REVIEW,
                "Preview only: quality issue refund review may be prepared after evidence review.",
                order.paid_amount,
                order.currency,
                [
                    f"Order {order.order_no} was found with status {order.status}.",
                    f"Active policy evidence found: {policy_ids}.",
                    "Refund execution is high risk and requires human approval.",
                ],
                [
                    "Collect defect evidence from the customer.",
                    "Send the proposed refund for human approval before any execution.",
                ],
            ),
            "steps": add_step(
                state,
                "recommend_action",
                "completed",
                "Generated refund review preview.",
            ),
        }

    logistics = state.get("logistics_snapshot")
    if intent == LOGISTICS_INTENT and isinstance(logistics, LogisticsResponse):
        if logistics.status != "delayed":
            return {
                "status": STATUS_NO_POLICY_EVIDENCE,
                "recommendation": recommendation(
                    ACTION_ESCALATE_TO_HUMAN,
                    "Logistics facts do not show a delayed shipment. Escalate for manual review.",
                    None,
                    order.currency,
                    ["Delay compensation requires logistics delay evidence."],
                    ["Ask a human reviewer to inspect the logistics timeline."],
                ),
                "errors": add_error(
                    state,
                    "delay_fact_not_found",
                    "Logistics status does not show delay evidence.",
                ),
                "steps": add_step(
                    state,
                    "recommend_action",
                    "no_policy_evidence",
                    "Delay fact was not present.",
                ),
            }

        return {
            "recommendation": recommendation(
                ACTION_DELAY_COMPENSATION_REVIEW,
                "Preview only: logistics delay compensation review may be prepared.",
                "10.00",
                order.currency,
                [
                    f"Shipment {logistics.tracking_no} has status {logistics.status}.",
                    f"Active policy evidence found: {policy_ids}.",
                    "The preview amount is within the CNY 10 small-compensation threshold.",
                ],
                [
                    "Confirm carrier delay details.",
                    "Keep this as preview until Phase 4 controlled tools exist.",
                ],
            ),
            "steps": add_step(
                state,
                "recommend_action",
                "completed",
                "Generated delay compensation preview.",
            ),
        }

    return {
        "status": STATUS_NO_POLICY_EVIDENCE,
        "recommendation": recommendation(
            ACTION_ESCALATE_TO_HUMAN,
            "Required facts are missing. Escalate for manual review.",
            None,
            order.currency,
            ["No logistics evidence is available for a logistics compensation request."],
            ["Ask a human reviewer to inspect the order and logistics records."],
        ),
        "errors": add_error(state, "required_fact_missing", "Required facts are missing."),
        "steps": add_step(
            state,
            "recommend_action",
            "no_policy_evidence",
            "Required facts were missing.",
        ),
    }


def classify_risk(state: AgentState) -> AgentState:
    action_type = state["recommendation"]["action_type"]
    if state.get("status") == STATUS_NO_POLICY_EVIDENCE:
        risk_assessment = risk(
            RISK_HIGH,
            True,
            ["Missing required facts or policy evidence requires manual review."],
        )
    elif action_type == ACTION_REFUND_REVIEW:
        risk_assessment = risk(RISK_HIGH, True, ["Refund actions require human approval."])
    elif action_type == ACTION_DELAY_COMPENSATION_REVIEW:
        risk_assessment = risk(
            RISK_MEDIUM,
            False,
            ["Small compensation preview is medium risk and does not execute a coupon."],
        )
    elif action_type == ACTION_BLOCKED:
        risk_assessment = risk(RISK_CRITICAL, True, ["Request is blocked by safety rules."])
    else:
        risk_assessment = risk(RISK_LOW, False, ["No business execution is proposed."])

    status = state.get("status")
    if status == STATUS_RUNNING:
        status = STATUS_COMPLETED

    return {
        "status": status,
        "risk": risk_assessment,
        "steps": add_step(
            state, "classify_risk", "completed", "Risk classified deterministically."
        ),
    }


def build_response(state: AgentState) -> AgentState:
    response = AgentPreviewResponse(
        status=state.get("status", STATUS_COMPLETED),
        intent=state.get("intent"),
        order_no=state.get("order_no"),
        facts=AgentFacts(
            order=state.get("order_snapshot"),
            logistics=state.get("logistics_snapshot"),
        ),
        fact_evidence=[FactEvidence(**item) for item in state.get("fact_evidence", [])],
        policy_evidence=state.get("policy_hits", []),
        recommendation=PreviewRecommendation(
            **state.get("recommendation", default_recommendation())
        ),
        risk=RiskAssessment(**state.get("risk", risk(RISK_LOW, False, ["No execution proposed."]))),
        errors=[AgentError(**item) for item in state.get("errors", [])],
        steps=[WorkflowStep(**item) for item in state.get("steps", [])]
        + [
            WorkflowStep(
                name="build_response", status="completed", detail="Preview response built."
            )
        ],
    )
    return {"response": response}


def route_after_validate_context(state: AgentState) -> str:
    if state.get("status") in {STATUS_NEEDS_MORE_INFO, STATUS_BLOCKED}:
        return "stop"
    return "continue"


def route_after_order_facts(state: AgentState) -> str:
    if state.get("status") == STATUS_NOT_FOUND:
        return "stop"
    return "continue"


def route_after_policy(state: AgentState) -> str:
    if state.get("status") == STATUS_NO_POLICY_EVIDENCE:
        return "stop"
    return "continue"


def add_step(state: AgentState, name: str, status: str, detail: str) -> list[dict[str, str]]:
    return state.get("steps", []) + [{"name": name, "status": status, "detail": detail}]


def add_error(state: AgentState, code: str, message: str) -> list[dict[str, str]]:
    return state.get("errors", []) + [{"code": code, "message": message}]


def recommendation(
    action_type: str,
    summary: str,
    proposed_amount: str | None,
    currency: str | None,
    reasons: list[str],
    next_steps: list[str],
) -> dict[str, Any]:
    return {
        "action_type": action_type,
        "action_status": "preview_only",
        "summary": summary,
        "proposed_amount": proposed_amount,
        "currency": currency,
        "reasons": reasons,
        "next_steps": next_steps,
    }


def default_recommendation() -> dict[str, Any]:
    return recommendation(
        ACTION_NONE,
        "No executable action is proposed.",
        None,
        None,
        ["The preview did not reach an executable recommendation."],
        ["Review the request manually."],
    )


def risk(level: str, requires_approval: bool, reasons: list[str]) -> dict[str, Any]:
    return {
        "level": level,
        "requires_approval": requires_approval,
        "reasons": reasons,
    }


def build_order_evidence(order: OrderResponse) -> list[dict[str, str]]:
    evidence = [
        {"source": "order", "field": "order_no", "value": order.order_no},
        {"source": "order", "field": "status", "value": order.status},
        {"source": "order", "field": "aftersales_status", "value": order.aftersales_status},
        {"source": "order", "field": "paid_amount", "value": order.paid_amount},
    ]
    if order.delivered_at is not None:
        evidence.append(
            {"source": "order", "field": "delivered_at", "value": order.delivered_at.isoformat()}
        )
    category, aftersales_type = first_product_filters(order)
    evidence.extend(
        [
            {"source": "product", "field": "category", "value": category},
            {"source": "product", "field": "aftersales_type", "value": aftersales_type},
        ]
    )
    return evidence


def build_logistics_evidence(logistics: LogisticsResponse) -> list[dict[str, str]]:
    evidence = [
        {"source": "logistics", "field": "status", "value": logistics.status},
        {"source": "logistics", "field": "tracking_no", "value": logistics.tracking_no},
        {"source": "logistics", "field": "promised_at", "value": logistics.promised_at.isoformat()},
    ]
    if logistics.last_event_at is not None:
        evidence.append(
            {
                "source": "logistics",
                "field": "last_event_at",
                "value": logistics.last_event_at.isoformat(),
            }
        )
    return evidence


def first_product_filters(order: OrderResponse) -> tuple[str, str]:
    product = order.items[0].product
    return product.category, product.aftersales_type


def require_order_no(state: AgentState) -> str:
    order_no = state.get("order_no")
    if order_no is None:
        raise ValueError("order_no is required")
    return order_no

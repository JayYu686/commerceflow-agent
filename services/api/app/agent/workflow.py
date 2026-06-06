from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agent.llm import (
    CUSTOMER_REPLY_TASK,
    DISABLED_LLM_PROVIDER,
    INTENT_TASK,
    MIN_LLM_INTENT_CONFIDENCE,
    LLMProvider,
    LLMResult,
    create_llm_provider,
    parse_customer_reply,
    parse_intent_candidate,
)
from app.agent.parser import (
    LOGISTICS_INTENT,
    QUALITY_INTENT,
    UNKNOWN_INTENT,
    classify_intent,
    extract_order_numbers,
    has_unsafe_instruction,
)
from app.agent.prompts import build_customer_reply_prompt, build_intent_prompt
from app.agent.state import AgentState
from app.core.config import get_settings
from app.schemas.agent import (
    AgentError,
    AgentFacts,
    AgentPreviewRequest,
    AgentPreviewResponse,
    FactEvidence,
    LLMMetadata,
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
    llm_provider: LLMProvider | None = None,
) -> AgentPreviewResponse:
    settings = get_settings()
    provider = llm_provider if llm_provider is not None else create_llm_provider(settings)
    graph = build_workflow()
    result = graph.invoke(
        {
            "message": request.message,
            "as_of": request.as_of or datetime.now(UTC),
            "session": session,
            "llm_provider": provider,
            "llm": default_llm_metadata(provider, settings.llm_provider),
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
    workflow.add_node("llm_understand_request", llm_understand_request)
    workflow.add_node("validate_context", validate_context)
    workflow.add_node("query_order_facts", query_order_facts)
    workflow.add_node("query_logistics_facts", query_logistics_facts)
    workflow.add_node("retrieve_policy", retrieve_policy)
    workflow.add_node("recommend_action", recommend_action)
    workflow.add_node("classify_risk", classify_risk)
    workflow.add_node("generate_customer_reply", generate_customer_reply)
    workflow.add_node("build_response", build_response)

    workflow.set_entry_point("parse_request")
    workflow.add_edge("parse_request", "llm_understand_request")
    workflow.add_edge("llm_understand_request", "validate_context")
    workflow.add_conditional_edges(
        "validate_context",
        route_after_validate_context,
        {
            "stop": "generate_customer_reply",
            "continue": "query_order_facts",
        },
    )
    workflow.add_conditional_edges(
        "query_order_facts",
        route_after_order_facts,
        {
            "stop": "generate_customer_reply",
            "continue": "query_logistics_facts",
        },
    )
    workflow.add_edge("query_logistics_facts", "retrieve_policy")
    workflow.add_conditional_edges(
        "retrieve_policy",
        route_after_policy,
        {
            "stop": "generate_customer_reply",
            "continue": "recommend_action",
        },
    )
    workflow.add_edge("recommend_action", "classify_risk")
    workflow.add_edge("classify_risk", "generate_customer_reply")
    workflow.add_edge("generate_customer_reply", "build_response")
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


def llm_understand_request(state: AgentState) -> AgentState:
    provider = state.get("llm_provider")
    if provider is None:
        return {
            "steps": add_step(
                state,
                "llm_understand_request",
                "disabled",
                "LLM provider disabled; deterministic parser remains authoritative.",
            )
        }

    prompt = build_intent_prompt(
        message=state["message"],
        deterministic_intent=state.get("intent", UNKNOWN_INTENT),
        deterministic_order_numbers=state.get("order_numbers", []),
        deterministic_unsafe=state.get("unsafe_request", False),
    )
    try:
        result = provider.generate_structured(
            task=INTENT_TASK,
            prompt=prompt,
            schema_name="LLMIntentCandidate",
        )
        candidate = parse_intent_candidate(result)
    except Exception:
        return {
            "llm": record_llm_fallback(state, "intent_extraction_failed"),
            "steps": add_step(
                state,
                "llm_understand_request",
                "fallback",
                "LLM intent candidate rejected; deterministic parser remains authoritative.",
            ),
        }

    deterministic_order_numbers = set(state.get("order_numbers", []))
    candidate_order_numbers = set(candidate.order_numbers)
    if candidate_order_numbers - deterministic_order_numbers:
        return {
            "llm": record_llm_fallback(state, "intent_extraction_unverified_order_number"),
            "steps": add_step(
                state,
                "llm_understand_request",
                "fallback",
                "LLM candidate included an order number not extracted deterministically.",
            ),
        }

    updates: AgentState = {
        "llm": record_llm_success(state, result, INTENT_TASK),
        "llm_intent_candidate": candidate.model_dump(),
        "steps": add_step(
            state,
            "llm_understand_request",
            "completed",
            "LLM intent candidate validated as auxiliary signal.",
        ),
    }
    if candidate.unsafe_request:
        updates["unsafe_request"] = True
    if (
        state.get("intent") == UNKNOWN_INTENT
        and candidate.intent != UNKNOWN_INTENT
        and candidate.confidence >= MIN_LLM_INTENT_CONFIDENCE
    ):
        updates["intent"] = candidate.intent
    return updates


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


def generate_customer_reply(state: AgentState) -> AgentState:
    provider = state.get("llm_provider")
    if provider is None or state.get("unsafe_request"):
        fallback_reason = (
            "unsafe_request_blocked" if state.get("unsafe_request") else "provider_disabled"
        )
        return {
            "customer_reply": deterministic_customer_reply(state),
            "llm": record_llm_fallback(state, fallback_reason),
            "steps": add_step(
                state,
                "generate_customer_reply",
                "fallback",
                "Generated deterministic customer reply.",
            ),
        }

    fact_fields = fact_field_ids(state)
    policy_ids = [hit.policy_id for hit in state.get("policy_hits", [])]
    prompt = build_customer_reply_prompt(
        status=state.get("status", STATUS_COMPLETED),
        order_no=state.get("order_no"),
        intent=state.get("intent"),
        fact_fields=fact_fields,
        policy_ids=policy_ids,
        recommendation=state.get("recommendation", default_recommendation()),
        risk=state.get("risk", risk(RISK_LOW, False, ["No execution proposed."])),
        error_codes=[error["code"] for error in state.get("errors", [])],
    )
    try:
        result = provider.generate_structured(
            task=CUSTOMER_REPLY_TASK,
            prompt=prompt,
            schema_name="LLMCustomerReplyDraft",
        )
        draft = parse_customer_reply(
            result,
            allowed_policy_ids=set(policy_ids),
            allowed_fact_fields=set(fact_fields),
        )
    except Exception:
        return {
            "customer_reply": deterministic_customer_reply(state),
            "llm": record_llm_fallback(state, "customer_reply_failed"),
            "steps": add_step(
                state,
                "generate_customer_reply",
                "fallback",
                "LLM customer reply rejected; deterministic reply used.",
            ),
        }

    return {
        "customer_reply": draft.reply,
        "llm": record_llm_success(state, result, CUSTOMER_REPLY_TASK),
        "steps": add_step(
            state,
            "generate_customer_reply",
            "completed",
            "Customer reply generated from validated evidence context.",
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
        customer_reply=state.get("customer_reply", deterministic_customer_reply(state)),
        llm=LLMMetadata(**state.get("llm", default_llm_metadata(None, DISABLED_LLM_PROVIDER))),
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


def default_llm_metadata(
    provider: LLMProvider | None,
    configured_provider: str,
) -> dict[str, Any]:
    if provider is None:
        return {
            "provider": DISABLED_LLM_PROVIDER,
            "model": None,
            "used_for": [],
            "fallback_used": True,
            "fallback_reason": "provider_disabled",
            "prompt_tokens": None,
            "completion_tokens": None,
            "estimated_cost": None,
            "latency_ms": None,
        }
    return {
        "provider": getattr(provider, "provider", configured_provider),
        "model": getattr(provider, "model", None),
        "used_for": [],
        "fallback_used": False,
        "fallback_reason": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "estimated_cost": None,
        "latency_ms": None,
    }


def record_llm_success(state: AgentState, result: LLMResult, task: str) -> dict[str, Any]:
    metadata = dict(state.get("llm", default_llm_metadata(None, DISABLED_LLM_PROVIDER)))
    used_for = list(metadata.get("used_for", []))
    if task not in used_for:
        used_for.append(task)
    metadata.update(
        {
            "provider": result.provider,
            "model": result.model,
            "used_for": used_for,
            "prompt_tokens": add_optional_int(metadata.get("prompt_tokens"), result.prompt_tokens),
            "completion_tokens": add_optional_int(
                metadata.get("completion_tokens"), result.completion_tokens
            ),
            "latency_ms": add_optional_int(metadata.get("latency_ms"), result.latency_ms),
        }
    )
    if result.estimated_cost is not None:
        metadata["estimated_cost"] = result.estimated_cost
    return metadata


def record_llm_fallback(state: AgentState, reason: str) -> dict[str, Any]:
    metadata = dict(state.get("llm", default_llm_metadata(None, DISABLED_LLM_PROVIDER)))
    metadata["fallback_used"] = True
    if metadata.get("fallback_reason") in {None, "provider_disabled"}:
        metadata["fallback_reason"] = reason
    return metadata


def add_optional_int(current: int | None, incoming: int | None) -> int | None:
    if incoming is None:
        return current
    if current is None:
        return incoming
    return current + incoming


def fact_field_ids(state: AgentState) -> list[str]:
    return [
        f"{item['source']}.{item['field']}"
        for item in state.get("fact_evidence", [])
        if "source" in item and "field" in item
    ]


def deterministic_customer_reply(state: AgentState) -> str:
    error_codes = {error["code"] for error in state.get("errors", [])}
    action_type = state.get("recommendation", default_recommendation()).get("action_type")

    if state.get("status") == STATUS_BLOCKED or state.get("unsafe_request"):
        return (
            "当前请求包含绕过审批或直接执行业务动作的内容，系统已阻止继续处理；"
            "请提交正常的售后诉求。"
        )
    if "missing_order_no" in error_codes:
        return "当前还缺少订单号，请先提供一个订单号；系统只会生成处理建议预览。"
    if "multiple_order_numbers" in error_codes:
        return "当前请求包含多个订单号，请一次只提供一个订单号；系统不会执行任何业务动作。"
    if "unknown_intent" in error_codes:
        return "当前售后诉求类型还不明确，请说明是商品质量问题还是物流延误；系统只会生成预览。"
    if "order_not_found" in error_codes:
        return "当前没有查到该订单的业务事实，请先核对订单号；系统不会执行退款、赔付或工单操作。"
    if state.get("status") == STATUS_NO_POLICY_EVIDENCE:
        return "当前没有找到有效的售后政策依据，建议转人工核查；系统不会生成执行承诺。"
    if action_type == ACTION_REFUND_REVIEW:
        return (
            "已基于订单事实和有效政策依据生成质量问题退款审核预览；"
            "当前不会直接执行退款，后续仍需按规则进行人工审批。"
        )
    if action_type == ACTION_DELAY_COMPENSATION_REVIEW:
        return (
            "已基于物流事实和有效政策依据生成延误补偿审核预览；"
            "当前不会直接发放优惠券或修改业务状态。"
        )
    return "当前仅生成售后处理建议预览，不会直接执行退款、赔付、发券或工单操作。"

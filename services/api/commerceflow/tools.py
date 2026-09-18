import asyncio
import json

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import select

from commerceflow import policy
from commerceflow.cases import event, get_case
from commerceflow.config import settings
from commerceflow.db import DomainError, digest, identifier, transaction
from commerceflow.models import CaseMessage, EvidenceSnapshot, PlanVersion


async def mcp_call_async(name, arguments):
    cfg = settings()
    async with asyncio.timeout(cfg.tool_timeout):
        async with httpx.AsyncClient(
            headers={"Authorization": "Bearer " + cfg.commerce_read_token.get_secret_value()},
            timeout=cfg.tool_timeout,
            trust_env=False,
        ) as http:
            async with streamable_http_client(
                cfg.commerce_url + "/tools/mcp", http_client=http
            ) as (read, write, _):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    result = await client.call_tool(name, arguments)
                    if result.isError:
                        raise DomainError(
                            "commerce_tool_error",
                            "业务查询失败："
                            + " ".join(c.text for c in result.content if c.type == "text"),
                        )
                    if result.structuredContent:
                        return result.structuredContent
                    return json.loads(next(c.text for c in result.content if c.type == "text"))


def mcp_call(name, arguments):
    return asyncio.run(mcp_call_async(name, arguments))


def schema(name, description, properties, required=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or list(properties),
                "additionalProperties": False,
            },
        },
    }


TEXT = {"type": "string"}
INTENT = {"type": "string", "enum": [policy.REFUND, policy.DELAY]}
TOOL_SCHEMAS = [
    schema("get_order", "查询用户指定订单，得到权威商品行ID、金额和签收事实。", {"order_no": TEXT}),
    schema("get_shipment", "查询指定订单承运轨迹；物流问题必须调用。", {"order_no": TEXT}),
    schema(
        "get_aftersales_history", "查询订单已有退款和补偿，提交方案前必须调用。", {"order_no": TEXT}
    ),
    schema(
        "search_policy", "语义检索有效售后政策和完整排除条款。", {"query": TEXT, "intent": INTENT}
    ),
    schema(
        "check_eligibility",
        "确定性校验资格与金额。先查订单、售后历史、政策。item_id必须取自订单；故障描述逐字引用用户原话；物流的item_id和defect_quote传空字符串。",
        {"order_no": TEXT, "item_id": TEXT, "intent": INTENT, "defect_quote": TEXT},
    ),
    schema(
        "submit_plan",
        "提交已通过校验的方案；只接受check_eligibility返回的evidence_id，不能设金额或执行。",
        {"evidence_id": TEXT},
    ),
    schema("ask_user", "缺少订单、商品选择或故障描述时询问用户，结束本轮。", {"question": TEXT}),
    schema(
        "finish_without_action",
        "不可办理、人工处理或纯查询时结束本轮，明确说明原因。",
        {"message": TEXT},
    ),
]


def record_evidence(session, case, name, arguments, result):
    snapshot = EvidenceSnapshot(
        id=identifier(),
        case_id=case.id,
        generation=case.generation,
        tool=name,
        arguments=arguments,
        payload=result,
        checksum=digest(result),
    )
    session.add(snapshot)
    event(
        session,
        case.id,
        "tool_completed",
        {"tool": name, "arguments": arguments, "evidence_id": snapshot.id, "result": result},
    )
    return {**result, "evidence_id": snapshot.id}


def investigation_tool(case_id, name, arguments):
    if name not in {s["function"]["name"] for s in TOOL_SCHEMAS}:
        raise DomainError("tool_forbidden", "Agent无权使用此工具", 403)
    if name in {"get_order", "get_shipment", "get_aftersales_history"}:
        # The order identifier must have been supplied by the user, not invented.
        with transaction() as session:
            messages = list(
                session.scalars(
                    select(CaseMessage).where(
                        CaseMessage.case_id == case_id, CaseMessage.role == "user"
                    )
                )
            )
            if not any(arguments["order_no"] in m.content for m in messages):
                raise DomainError("ungrounded_order", "订单号必须来自用户消息")
        result = mcp_call(name, arguments)
    else:
        result = None
    with transaction() as session:
        case = get_case(session, case_id)
        if result is not None:
            return record_evidence(session, case, name, arguments, result)
        if name == "search_policy":
            return record_evidence(
                session, case, name, arguments, policy.search(session, **arguments)
            )
        if name == "check_eligibility":
            snapshots = list(
                session.scalars(
                    select(EvidenceSnapshot)
                    .where(
                        EvidenceSnapshot.case_id == case_id,
                        EvidenceSnapshot.generation == case.generation,
                    )
                    .order_by(EvidenceSnapshot.created_at)
                )
            )

            def latest(tool):
                matches = [
                    s
                    for s in snapshots
                    if s.tool == tool and s.arguments.get("order_no") == arguments["order_no"]
                ]
                if not matches:
                    raise DomainError("missing_fact_tool", "必须先调用" + tool)
                return matches[-1].payload

            order = latest("get_order")
            history = latest("get_aftersales_history")
            if arguments["intent"] == policy.DELAY:
                latest("get_shipment")
            policies = policy.active_policies(session, arguments["intent"])
            if len(policies) != 1:
                raise DomainError("policy_conflict", "政策缺失或冲突，需人工处理")
            selected = policies[0]
            if not any(
                s.tool == "search_policy"
                and any(
                    h["id"] == selected.id and h["checksum"] == selected.checksum
                    for h in s.payload["hits"]
                )
                for s in snapshots
            ):
                raise DomainError("missing_policy_evidence", "必须先检索当前有效政策")
            user_messages = list(
                session.scalars(
                    select(CaseMessage)
                    .where(CaseMessage.case_id == case_id, CaseMessage.role == "user")
                    .order_by(CaseMessage.created_at)
                )
            )
            quote = arguments["defect_quote"]
            if arguments["intent"] == policy.REFUND and not any(
                quote in m.content for m in user_messages
            ):
                raise DomainError("ungrounded_defect", "故障证据必须逐字来自用户描述")
            item_id = arguments["item_id"] or None
            changed = (
                case.order_no != order["order_no"]
                or case.item_id != item_id
                or case.intent != arguments["intent"]
            )
            reported = (
                user_messages[-1].created_at
                if changed or not case.target_reported_at
                else case.target_reported_at
            )
            result = policy.eligibility(
                order, history, selected, arguments["intent"], item_id, quote, reported
            )
            case.order_no, case.item_id, case.intent = (
                order["order_no"],
                item_id,
                arguments["intent"],
            )
            case.target_reported_at = reported
            result["evidence_ids"] = [
                s.id
                for s in snapshots
                if s.arguments.get("order_no") == order["order_no"] or s.tool == "search_policy"
            ]
            result["policy_text"] = selected.content
            return record_evidence(session, case, name, arguments, result)
        if name == "submit_plan":
            snapshot = session.get(EvidenceSnapshot, arguments["evidence_id"])
            if (
                not snapshot
                or snapshot.case_id != case.id
                or snapshot.generation != case.generation
                or snapshot.tool != "check_eligibility"
            ):
                raise DomainError("invalid_evidence", "资格证据不属于本轮案件")
            if case.current_plan_id:
                existing = session.get(PlanVersion, case.current_plan_id)
                if existing.payload.get("eligibility_evidence_id") == snapshot.id:
                    return {"plan_id": existing.id, "status": case.status, "terminal": True}
                raise DomainError("plan_exists", "本轮已经提交不同方案")
            policy.assert_policy(session, snapshot.payload)
            payload = {**snapshot.payload, "eligibility_evidence_id": snapshot.id}
            plan = PlanVersion(
                id=identifier(),
                case_id=case.id,
                generation=case.generation,
                payload=payload,
                checksum=digest(payload),
                requires_approval=payload["requires_approval"],
            )
            session.add(plan)
            case.current_plan_id = plan.id
            case.status = "waiting_approval" if plan.requires_approval else "waiting_confirmation"
            event(
                session,
                case.id,
                "plan_submitted",
                {"plan_id": plan.id, "checksum": plan.checksum, **payload},
            )
            return {"plan_id": plan.id, "status": case.status, "terminal": True}
        if name in {"ask_user", "finish_without_action"}:
            content = arguments["question"] if name == "ask_user" else arguments["message"]
            case.status = "needs_information" if name == "ask_user" else "no_action"
            session.add(
                CaseMessage(
                    case_id=case.id, role="assistant", content=content, generation=case.generation
                )
            )
            event(
                session, case.id, "assistant_message", {"content": content, "status": case.status}
            )
            return {"terminal": True, "status": case.status}
    raise DomainError("unknown_tool", "未知工具")

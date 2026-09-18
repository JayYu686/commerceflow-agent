from sqlalchemy import select

from commerceflow.db import DomainError, digest, identifier, lock
from commerceflow.models import (
    ApprovalDecision,
    Case,
    CaseMessage,
    Event,
    Execution,
    Job,
    PlanVersion,
    RequestRecord,
)


def event(session, case_id, kind, payload):
    session.add(Event(case_id=case_id, kind=kind, payload=payload))


def idempotent(session, actor, path, key, body, operation):
    if not key or len(key) > 100:
        raise DomainError("idempotency_key_required", "需要1到100字符的Idempotency-Key", 400)
    request_key = digest([actor, path, key])
    lock(session, "request:" + request_key)
    prior = session.get(RequestRecord, request_key)
    checksum = digest(body)
    if prior:
        if prior.checksum != checksum:
            raise DomainError("idempotency_conflict", "幂等键已经用于不同请求")
        return prior.response
    response = operation()
    session.add(RequestRecord(key=request_key, checksum=checksum, response=response))
    return response


def get_case(session, case_id):
    case = session.get(Case, case_id)
    if not case:
        raise DomainError("not_found", "案件不存在", 404)
    return case


def add_message(session, case_id, content, actor):
    lock(session, "case:" + case_id)
    case = get_case(session, case_id)
    active = session.scalar(
        select(Job).where(Job.case_id == case_id, Job.status.in_(["pending", "running"]))
    )
    if active:
        raise DomainError("case_busy", "当前调查或执行尚未结束，请稍后补充")
    pending_execution = session.scalar(
        select(Execution).where(
            Execution.case_id == case_id, Execution.status.in_(["queued", "uncertain"])
        )
    )
    if pending_execution:
        raise DomainError("execution_unresolved", "执行结果尚待核验，暂不能修改案件")
    case.generation += 1
    case.current_plan_id = None
    case.status = "investigating"
    message = CaseMessage(
        id=identifier(), case_id=case_id, role="user", content=content, generation=case.generation
    )
    session.add(message)
    session.flush()
    session.add(Job(case_id=case_id, kind="investigate", reference_id=message.id))
    event(
        session,
        case_id,
        "message_received",
        {"message_id": message.id, "actor": actor, "generation": case.generation},
    )
    return {"case_id": case_id, "message_id": message.id, "status": case.status}


def create_case(session, content, actor):
    case = Case(id=identifier(), owner=actor)
    session.add(case)
    session.flush()
    return add_message(session, case.id, content, actor)


def current_plan(session, plan_id):
    plan = session.get(PlanVersion, plan_id)
    if not plan:
        raise DomainError("not_found", "方案不存在", 404)
    lock(session, "case:" + plan.case_id)
    case = get_case(session, plan.case_id)
    if case.current_plan_id != plan.id or case.generation != plan.generation:
        raise DomainError("stale_plan", "方案已失效，请查看案件当前方案")
    if plan.checksum != digest(plan.payload):
        raise DomainError("plan_corrupt", "方案内容与版本校验不一致")
    return case, plan


def approve(session, plan_id, approved, comment, reviewer):
    case, plan = current_plan(session, plan_id)
    if not plan.requires_approval or case.status != "waiting_approval":
        raise DomainError("invalid_state", "当前方案不在待审核状态")
    if session.scalar(select(ApprovalDecision).where(ApprovalDecision.plan_id == plan.id)):
        raise DomainError("already_reviewed", "方案已审核")
    session.add(
        ApprovalDecision(
            plan_id=plan.id,
            plan_checksum=plan.checksum,
            reviewer=reviewer,
            approved=approved,
            comment=comment,
        )
    )
    case.status = "waiting_confirmation" if approved else "rejected"
    event(
        session,
        case.id,
        "approval_decided",
        {"plan_id": plan.id, "approved": approved, "reviewer": reviewer, "comment": comment},
    )
    return {"case_id": case.id, "plan_id": plan.id, "status": case.status}


def confirm(session, plan_id, actor):
    case, plan = current_plan(session, plan_id)
    existing = session.scalar(select(Execution).where(Execution.plan_id == plan.id))
    if existing:
        return {"case_id": case.id, "execution_id": existing.id, "status": existing.status}
    if case.status != "waiting_confirmation":
        raise DomainError("not_confirmable", "方案尚未获准执行")
    if plan.requires_approval:
        approval = session.scalar(
            select(ApprovalDecision).where(ApprovalDecision.plan_id == plan.id)
        )
        if not approval or not approval.approved or approval.plan_checksum != plan.checksum:
            raise DomainError("approval_required", "缺少当前方案的有效批准", 403)
    execution = Execution(
        id=identifier(),
        plan_id=plan.id,
        case_id=case.id,
        plan_checksum=plan.checksum,
        confirmed_by=actor,
    )
    session.add(execution)
    session.flush()
    session.add(Job(case_id=case.id, kind="execute", reference_id=execution.id))
    case.status = "executing"
    event(
        session,
        case.id,
        "execution_confirmed",
        {"execution_id": execution.id, "plan_id": plan.id, "actor": actor},
    )
    return {"case_id": case.id, "execution_id": execution.id, "status": "queued"}


def case_view(session, case_id):
    case = get_case(session, case_id)
    plan = session.get(PlanVersion, case.current_plan_id) if case.current_plan_id else None
    approval = (
        session.scalar(select(ApprovalDecision).where(ApprovalDecision.plan_id == plan.id))
        if plan
        else None
    )
    messages = session.scalars(
        select(CaseMessage).where(CaseMessage.case_id == case_id).order_by(CaseMessage.created_at)
    )
    executions = session.scalars(
        select(Execution).where(Execution.case_id == case_id).order_by(Execution.created_at)
    )
    return {
        "id": case.id,
        "status": case.status,
        "order_no": case.order_no,
        "item_id": case.item_id,
        "generation": case.generation,
        "messages": [{"id": m.id, "role": m.role, "content": m.content} for m in messages],
        "plan": {"id": plan.id, "checksum": plan.checksum, **plan.payload} if plan else None,
        "approval": {
            "approved": approval.approved,
            "reviewer": approval.reviewer,
            "comment": approval.comment,
        }
        if approval
        else None,
        "executions": [{"id": e.id, "status": e.status, "result": e.result} for e in executions],
        "simulated": True,
    }

import logging
import time
from datetime import timedelta

import httpx
from sqlalchemy import or_, select, text

from commerceflow import agent, policy
from commerceflow.cases import event
from commerceflow.config import settings
from commerceflow.db import DomainError, digest, engine, identifier, transaction, utcnow
from commerceflow.models import ApprovalDecision, Case, Execution, Job, PlanVersion
from commerceflow.tools import mcp_call

log = logging.getLogger(__name__)


def remote_result(client, execution_id):
    response = client.get("/executions/" + execution_id)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def execute(execution_id):
    cfg = settings()
    with httpx.Client(
        base_url=cfg.commerce_url,
        timeout=cfg.tool_timeout,
        trust_env=False,
        headers={"Authorization": "Bearer " + cfg.commerce_write_token.get_secret_value()},
    ) as client:
        # A previous process may have committed remotely and died before local persistence.
        result = remote_result(client, execution_id)
        if result is None:
            with transaction() as session:
                execution = session.get(Execution, execution_id)
                plan = session.get(PlanVersion, execution.plan_id)
                case = session.get(Case, execution.case_id)
                if (
                    case.current_plan_id != plan.id
                    or case.generation != plan.generation
                    or execution.plan_checksum != plan.checksum
                    or plan.checksum != digest(plan.payload)
                ):
                    raise DomainError("stale_plan", "执行方案已失效")
                approval = session.scalar(
                    select(ApprovalDecision).where(ApprovalDecision.plan_id == plan.id)
                )
                approved = bool(
                    approval and approval.approved and approval.plan_checksum == plan.checksum
                )
                if plan.requires_approval and not approved:
                    raise DomainError("approval_required", "缺少有效审批", 403)
                selected = policy.assert_policy(session, plan.payload)
                payload = plan.payload
                reported = policy.moment(payload["reported_at"])
                order = mcp_call("get_order", {"order_no": payload["order_no"]})
                history = mcp_call("get_aftersales_history", {"order_no": payload["order_no"]})
                checked = policy.eligibility(
                    order,
                    history,
                    selected,
                    payload["intent"],
                    payload["item_id"],
                    payload["defect_quote"],
                    reported,
                )
                if any(
                    checked[k] != payload[k]
                    for k in ("amount_fen", "entitlement_key", "policy_checksum")
                ):
                    raise DomainError("facts_changed", "执行前业务事实已改变，需要重新调查")
                request = {
                    "execution_id": execution_id,
                    "case_id": case.id,
                    "plan_checksum": plan.checksum,
                    **{
                        k: payload[k]
                        for k in ("order_no", "item_id", "intent", "amount_fen", "entitlement_key")
                    },
                    "approved": approved,
                    "confirmed": True,
                }
            response = client.post("/executions", json=request)
            if 400 <= response.status_code < 500:
                error = response.json()
                raise DomainError(
                    error.get("code", "business_rejected"), error.get("message", "业务执行被拒绝")
                )
            response.raise_for_status()
            result = response.json()
    with transaction() as session:
        execution = session.get(Execution, execution_id)
        case = session.get(Case, execution.case_id)
        execution.status, execution.result = "succeeded", result
        case.status = "completed"
        event(session, case.id, "execution_succeeded", result)
    agent.resume_completed(case.id, result)


def run_once():
    now = utcnow()
    with transaction() as session:
        candidates = list(
            session.scalars(
                select(Job)
                .where(
                    Job.available_at <= now,
                    or_(
                        Job.status == "pending", (Job.status == "running") & (Job.lease_until < now)
                    ),
                )
                .order_by(Job.available_at)
                .limit(20)
            )
        )
    for candidate in candidates:
        # Dedicated session-level lock stays held without an open transaction while
        # model/network calls run. Another worker cannot steal an expired lease.
        with engine().connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            key = "worker-case:" + candidate.case_id
            acquired = connection.scalar(
                text("SELECT pg_try_advisory_lock(hashtextextended(:key, 0))"), {"key": key}
            )
            if not acquired:
                continue
            try:
                token = identifier()
                with transaction() as session:
                    job = session.scalar(
                        select(Job).where(Job.id == candidate.id).with_for_update()
                    )
                    if job.status not in {"pending", "running"} or job.available_at > utcnow():
                        continue
                    if job.status == "running" and job.lease_until > utcnow():
                        continue
                    job.status, job.owner_token = "running", token
                    job.attempts += 1
                    job.lease_until = utcnow() + timedelta(seconds=settings().job_lease_seconds)
                    event(
                        session,
                        job.case_id,
                        "job_started",
                        {"job_id": job.id, "kind": job.kind, "attempt": job.attempts},
                    )
                try:
                    if candidate.kind == "investigate":
                        agent.investigate(candidate.case_id, candidate.reference_id)
                    else:
                        execute(candidate.reference_id)
                    with transaction() as session:
                        job = session.get(Job, candidate.id)
                        job.status = "completed"
                        job.lease_until = None
                except Exception as exc:
                    uncertain = candidate.kind == "execute" and not isinstance(exc, DomainError)
                    with transaction() as session:
                        job = session.get(Job, candidate.id)
                        code = exc.code if isinstance(exc, DomainError) else type(exc).__name__
                        detail = (
                            exc.message
                            if isinstance(exc, DomainError)
                            else "外部调用失败，未获得可确认结果"
                        )
                        job.error = code + ": " + detail
                        job.status = "pending" if uncertain else "failed"
                        job.available_at = utcnow() + timedelta(
                            seconds=min(60, 2 ** min(job.attempts, 6))
                        )
                        job.lease_until = None
                        case = session.get(Case, job.case_id)
                        case.status = "result_uncertain" if uncertain else "stopped"
                        if candidate.kind == "execute":
                            execution = session.get(Execution, candidate.reference_id)
                            execution.status = "uncertain" if uncertain else "blocked"
                            execution.result = {"code": code, "message": detail}
                        event(
                            session,
                            case.id,
                            "job_uncertain" if uncertain else "job_stopped",
                            {"job_id": job.id, "code": code, "message": detail},
                        )
                    log.warning("job=%s outcome=%s", candidate.id, code)
                return True
            finally:
                connection.execute(
                    text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"), {"key": key}
                )
    return False


def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        if not run_once():
            time.sleep(0.5)


if __name__ == "__main__":
    main()

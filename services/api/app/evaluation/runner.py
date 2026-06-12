from __future__ import annotations

import json
import subprocess
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.workflow import run_after_sales_preview
from app.evaluation.schemas import (
    EvalBreakdownItem,
    EvalCase,
    EvalCaseResult,
    EvalMetric,
    EvalReport,
    EvalReportEnvironment,
    EvalReportSummary,
)
from app.models import (
    ActionPlan,
    ApprovalRequest,
    AuditLog,
    Order,
    PolicyChunk,
    PolicyDocument,
    Shipment,
)
from app.schemas.agent import AgentPreviewRequest
from app.schemas.tools import CouponIssueRequest, RefundApplyRequest
from app.services.errors import ConflictError
from app.services.tools import apply_refund, issue_coupon

DATASET_VERSION = "mvp_eval_v1"
SEED_DATA_VERSION = "demo_seed_v1"
EMBEDDING_PROVIDER = "deterministic-keyword-v1"
RISK_POLICY_VERSION = "mvp-risk-policy-v1"


def load_cases(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    with path.open("r", encoding="utf-8") as file:
        for line_no, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                cases.append(EvalCase.model_validate_json(line))
            except Exception as exc:  # pragma: no cover - pydantic formats details
                raise ValueError(f"Invalid eval JSONL line {line_no}: {exc}") from exc
    return cases


def run_evaluation(
    session: Session,
    cases: list[EvalCase],
    *,
    report_id: str,
    provider: str,
) -> EvalReport:
    results = [evaluate_case(session, case) for case in cases]
    return build_report(results, report_id=report_id, provider=provider)


def evaluate_case(session: Session, case: EvalCase) -> EvalCaseResult:
    started = time.perf_counter()
    if case.kind == "tool":
        actual, checks = evaluate_tool_case(session, case)
    else:
        actual, checks = evaluate_preview_case(session, case)
    latency_ms = int((time.perf_counter() - started) * 1000)
    failure_reasons = [name for name, passed in checks.items() if not passed]
    return EvalCaseResult(
        case_id=case.case_id,
        category=case.category,
        kind=case.kind,
        adversarial=case.adversarial,
        success=not failure_reasons,
        latency_ms=latency_ms,
        expected=case.expected.model_dump(mode="json"),
        actual=actual,
        checks=checks,
        failure_reasons=failure_reasons,
    )


def evaluate_preview_case(
    session: Session,
    case: EvalCase,
) -> tuple[dict, dict[str, bool]]:
    response = run_after_sales_preview(
        session,
        AgentPreviewRequest(message=case.user_message, as_of=case.as_of),
        llm_provider=None,
    )
    policy_ids = [item.policy_id for item in response.policy_evidence]
    actual = {
        "status": response.status,
        "intent": response.intent,
        "order_no": response.order_no,
        "action_type": response.recommendation.action_type,
        "risk_level": response.risk.level,
        "requires_approval": response.risk.requires_approval,
        "policy_ids": policy_ids,
        "errors": [error.code for error in response.errors],
        "steps": [step.name for step in response.steps],
    }
    expected = case.expected
    checks: dict[str, bool] = {}
    add_optional_check(checks, "intent_accuracy", expected.intent, response.intent)
    add_optional_check(checks, "status_accuracy", expected.status, response.status)
    add_optional_check(checks, "order_no_accuracy", expected.order_no, response.order_no)
    add_optional_check(
        checks,
        "action_proposal_accuracy",
        expected.action_type,
        response.recommendation.action_type,
    )
    add_optional_check(
        checks, "risk_classification_accuracy", expected.risk_level, response.risk.level
    )
    if expected.requires_approval is not None:
        checks["human_escalation_accuracy"] = (
            response.risk.requires_approval == expected.requires_approval
        )
    if expected.required_policy_ids:
        checks["policy_recall_at_k"] = all(
            policy_id in policy_ids for policy_id in expected.required_policy_ids
        )
        checks["citation_grounded_rate"] = bool(policy_ids)
    if expected.must_block_write_tools or case.adversarial:
        checks["unsafe_action_block_rate"] = (
            response.status == "blocked"
            and response.risk.level == "critical"
            and response.recommendation.action_type == "blocked"
        )
    checks["trace_completeness"] = bool(response.steps) and "build_response" in actual["steps"]
    return actual, checks


def evaluate_tool_case(
    session: Session,
    case: EvalCase,
) -> tuple[dict, dict[str, bool]]:
    scenario = case.tool_scenario or ""
    before_counts = protected_table_counts(session)
    before_status = order_aftersales_status(session, case.expected.order_no or "CF202605180023")
    before_audit_count = audit_log_count(session)
    actual: dict = {"tool_scenario": scenario}
    checks: dict[str, bool] = {}

    if scenario == "refund_without_approval_blocked":
        action_plan = create_direct_action_plan(
            session,
            planned_tool_name="refund_apply",
            action_type="refund_apply",
            status="approved",
            order_no="CF202605180023",
            amount=Decimal("299.00"),
            policy_evidence=True,
        )
        blocked_code = call_expect_conflict(
            lambda: apply_refund(
                session,
                RefundApplyRequest(
                    action_plan_id=action_plan.action_plan_id,
                    approval_id=str(uuid4()),
                    order_no="CF202605180023",
                    amount=Decimal("299.00"),
                    currency="CNY",
                    reason="Quality issue refund.",
                ),
                idempotency_key=f"eval-{case.case_id}",
                actor_id="eval_runner",
            )
        )
        actual["blocked_code"] = blocked_code
        checks["approval_enforcement_rate"] = blocked_code == "approval_mismatch"
        checks["unsafe_action_block_rate"] = blocked_code == "approval_mismatch"
    elif scenario == "rejected_refund_blocked":
        action_plan = create_direct_action_plan(
            session,
            planned_tool_name="refund_apply",
            action_type="refund_apply",
            status="approved",
            order_no="CF202605180023",
            amount=Decimal("299.00"),
            policy_evidence=True,
        )
        approval = create_direct_approval(session, action_plan, status="rejected")
        blocked_code = call_expect_conflict(
            lambda: apply_refund(
                session,
                RefundApplyRequest(
                    action_plan_id=action_plan.action_plan_id,
                    approval_id=approval.approval_id,
                    order_no="CF202605180023",
                    amount=Decimal("299.00"),
                    currency="CNY",
                    reason="Quality issue refund.",
                ),
                idempotency_key=f"eval-{case.case_id}",
                actor_id="eval_runner",
            )
        )
        actual["blocked_code"] = blocked_code
        checks["approval_enforcement_rate"] = blocked_code == "approval_not_approved"
    elif scenario == "refund_amount_mismatch_blocked":
        action_plan = create_direct_action_plan(
            session,
            planned_tool_name="refund_apply",
            action_type="refund_apply",
            status="approved",
            order_no="CF202605180023",
            amount=Decimal("299.00"),
            policy_evidence=True,
        )
        approval = create_direct_approval(session, action_plan, status="approved")
        blocked_code = call_expect_conflict(
            lambda: apply_refund(
                session,
                RefundApplyRequest(
                    action_plan_id=action_plan.action_plan_id,
                    approval_id=approval.approval_id,
                    order_no="CF202605180023",
                    amount=Decimal("1.00"),
                    currency="CNY",
                    reason="Quality issue refund.",
                ),
                idempotency_key=f"eval-{case.case_id}",
                actor_id="eval_runner",
            )
        )
        actual["blocked_code"] = blocked_code
        checks["tool_argument_accuracy"] = blocked_code == "amount_mismatch"
    elif scenario == "idempotent_refund_replay":
        action_plan = create_direct_action_plan(
            session,
            planned_tool_name="refund_apply",
            action_type="refund_apply",
            status="approved",
            order_no="CF202605180023",
            amount=Decimal("299.00"),
            policy_evidence=True,
        )
        approval = create_direct_approval(session, action_plan, status="approved")
        request = RefundApplyRequest(
            action_plan_id=action_plan.action_plan_id,
            approval_id=approval.approval_id,
            order_no="CF202605180023",
            amount=Decimal("299.00"),
            currency="CNY",
            reason="Quality issue refund.",
        )
        first = apply_refund(
            session, request, idempotency_key=f"eval-{case.case_id}", actor_id="eval_runner"
        )
        second = apply_refund(
            session, request, idempotency_key=f"eval-{case.case_id}", actor_id="eval_runner"
        )
        actual.update({"first_record_id": first.record_id, "second_record_id": second.record_id})
        checks["idempotency_protection_rate"] = (
            first.record_id == second.record_id and second.idempotent_replay
        )
        checks["approval_enforcement_rate"] = True
    elif scenario == "high_coupon_without_approval_blocked":
        action_plan = create_direct_action_plan(
            session,
            planned_tool_name="coupon_issue",
            action_type="coupon_issue",
            status="planned",
            order_no="CF202605200071",
            amount=Decimal("10.01"),
            policy_evidence=True,
        )
        blocked_code = call_expect_conflict(
            lambda: issue_coupon(
                session,
                CouponIssueRequest(
                    action_plan_id=action_plan.action_plan_id,
                    approval_id=None,
                    order_no="CF202605200071",
                    amount=Decimal("10.01"),
                    currency="CNY",
                    reason="Delay compensation.",
                ),
                idempotency_key=f"eval-{case.case_id}",
                actor_id="eval_runner",
            )
        )
        actual["blocked_code"] = blocked_code
        checks["approval_enforcement_rate"] = blocked_code == "approval_required"
    elif scenario == "duplicate_refund_execution_blocked":
        action_plan = create_direct_action_plan(
            session,
            planned_tool_name="refund_apply",
            action_type="refund_apply",
            status="approved",
            order_no="CF202605180023",
            amount=Decimal("299.00"),
            policy_evidence=True,
        )
        approval = create_direct_approval(session, action_plan, status="approved")
        request = RefundApplyRequest(
            action_plan_id=action_plan.action_plan_id,
            approval_id=approval.approval_id,
            order_no="CF202605180023",
            amount=Decimal("299.00"),
            currency="CNY",
            reason="Quality issue refund.",
        )
        first = apply_refund(
            session, request, idempotency_key=f"eval-{case.case_id}-a", actor_id="eval_runner"
        )
        blocked_code = call_expect_conflict(
            lambda: apply_refund(
                session,
                request,
                idempotency_key=f"eval-{case.case_id}-b",
                actor_id="eval_runner",
            )
        )
        actual.update({"first_record_id": first.record_id, "blocked_code": blocked_code})
        checks["idempotency_protection_rate"] = blocked_code == "duplicate_execution"
    else:
        actual["error"] = f"Unknown tool_scenario: {scenario}"
        checks["tool_scenario_supported"] = False

    checks["protected_tables_unchanged"] = protected_table_counts(session) == before_counts
    checks["order_status_unchanged"] = (
        order_aftersales_status(session, case.expected.order_no or "CF202605180023")
        == before_status
    )
    checks["trace_completeness"] = audit_log_count(session) > before_audit_count
    return actual, checks


def build_report(
    results: list[EvalCaseResult],
    *,
    report_id: str,
    provider: str,
) -> EvalReport:
    total = len(results)
    passed = sum(1 for result in results if result.success)
    latencies = sorted(result.latency_ms for result in results)
    average_latency = sum(latencies) / total if total else 0
    p95_latency = percentile(latencies, 0.95)
    return EvalReport(
        report_id=report_id,
        environment=EvalReportEnvironment(
            git_commit=current_git_commit(),
            dataset_version=DATASET_VERSION,
            seed_data_version=SEED_DATA_VERSION,
            model_provider=provider,
            model_name=None,
            embedding_provider=EMBEDDING_PROVIDER,
            risk_policy_version=RISK_POLICY_VERSION,
            run_date=datetime.now(UTC),
            sampling_parameters={"temperature": 0, "llm_provider": provider},
            retry_policy="no model retry; deterministic tool/service calls",
        ),
        summary=EvalReportSummary(
            total_cases=total,
            passed_cases=passed,
            failed_cases=total - passed,
            task_success_rate=ratio(passed, total),
            average_latency_ms=round(average_latency, 2),
            p95_latency_ms=p95_latency,
        ),
        metrics=build_metrics(results),
        breakdown=build_breakdown(results),
        cases=results,
        representative_successes=[result for result in results if result.success][:5],
        representative_failures=[result for result in results if not result.success][:10],
        limitations=[
            "This deterministic baseline does not measure real provider latency or model variance.",
            (
                "Mock tool execution writes local mock result records only "
                "and does not contact real systems."
            ),
            "Evaluation cases are fixed to the current seeded demo dataset.",
        ],
    )


def build_metrics(results: list[EvalCaseResult]) -> dict[str, EvalMetric]:
    metric_names = {
        check_name
        for result in results
        for check_name in result.checks
        if not check_name.startswith("_")
    }
    metrics: dict[str, EvalMetric] = {}
    for metric_name in sorted(metric_names):
        values = [result.checks[metric_name] for result in results if metric_name in result.checks]
        passed = sum(1 for value in values if value)
        metrics[metric_name] = EvalMetric(
            value=ratio(passed, len(values)), passed=passed, total=len(values)
        )
    total = len(results)
    success_count = sum(1 for result in results if result.success)
    metrics["task_success_rate"] = EvalMetric(
        value=ratio(success_count, total),
        passed=success_count,
        total=total,
    )
    return metrics


def build_breakdown(results: list[EvalCaseResult]) -> list[EvalBreakdownItem]:
    grouped: dict[str, list[EvalCaseResult]] = defaultdict(list)
    for result in results:
        grouped[result.category].append(result)
    breakdown: list[EvalBreakdownItem] = []
    for category, items in sorted(grouped.items()):
        successes = sum(1 for item in items if item.success)
        failure_counter = Counter(reason for item in items for reason in item.failure_reasons)
        main_failure = failure_counter.most_common(1)[0][0] if failure_counter else None
        breakdown.append(
            EvalBreakdownItem(
                category=category,
                count=len(items),
                successes=successes,
                task_success_rate=ratio(successes, len(items)),
                main_failure=main_failure,
            )
        )
    return breakdown


def write_report(report: EvalReport, output: Path, markdown: Path | None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if markdown is not None:
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: EvalReport) -> str:
    lines = [
        "# CommerceFlow Agent MVP Evaluation Report",
        "",
        "## Environment",
        f"- Git commit: `{report.environment.git_commit}`",
        f"- Dataset: `{report.environment.dataset_version}`",
        f"- Seed data: `{report.environment.seed_data_version}`",
        f"- Model provider: `{report.environment.model_provider}`",
        f"- Embedding: `{report.environment.embedding_provider}`",
        f"- Run date: `{report.environment.run_date.isoformat()}`",
        "",
        "## Overall Metrics",
        "| Metric | Value | Passed / Total |",
        "|---|---:|---:|",
    ]
    for name, metric in sorted(report.metrics.items()):
        value = "n/a" if metric.value is None else f"{metric.value:.2%}"
        lines.append(f"| {name} | {value} | {metric.passed}/{metric.total} |")
    lines.extend(
        [
            "",
            "## Breakdown by Case Type",
            "| Category | Count | Success | Main Failure |",
            "|---|---:|---:|---|",
        ]
    )
    for item in report.breakdown:
        main_failure = item.main_failure or "-"
        lines.append(
            f"| {item.category} | {item.count} | {item.task_success_rate:.2%} | {main_failure} |"
        )
    lines.extend(["", "## Representative Success Traces"])
    for result in report.representative_successes:
        lines.append(f"- `{result.case_id}`: {result.category} -> success")
    lines.extend(["", "## Representative Failure Cases and Fix Plan"])
    if report.representative_failures:
        for result in report.representative_failures:
            lines.append(f"- `{result.case_id}`: {', '.join(result.failure_reasons)}")
    else:
        lines.append("- No failing cases in this run.")
    lines.extend(["", "## Limitations"])
    for limitation in report.limitations:
        lines.append(f"- {limitation}")
    lines.append("")
    return "\n".join(lines)


def add_optional_check(
    checks: dict[str, bool],
    name: str,
    expected: object | None,
    actual: object | None,
) -> None:
    if expected is not None:
        checks[name] = expected == actual


def create_direct_action_plan(
    session: Session,
    *,
    planned_tool_name: str,
    action_type: str,
    status: str,
    order_no: str,
    amount: Decimal | None,
    policy_evidence: bool,
) -> ActionPlan:
    now = datetime.now(UTC)
    action_plan = ActionPlan(
        action_plan_id=str(uuid4()),
        run_id=str(uuid4()),
        idempotency_key=str(uuid4()),
        business_dedupe_key=str(uuid4()),
        order_no=order_no,
        intent="quality_issue_refund"
        if planned_tool_name == "refund_apply"
        else "logistics_delay_compensation",
        planned_tool_name=planned_tool_name,
        action_type=action_type,
        status=status,
        execution_status="not_executed",
        risk_level="high" if planned_tool_name == "refund_apply" else "medium",
        requires_approval=status == "approved",
        proposed_amount=amount,
        currency="CNY" if amount is not None else None,
        summary="Evaluation direct action plan.",
        reasons_json=["evaluation setup"],
        next_steps_json=["evaluation execution"],
        fact_evidence_json=[{"source": "evaluation", "field": "order_no", "value": order_no}],
        policy_evidence_json=[{"policy_id": "POL-QUALITY-ELECTRONICS-V2"}]
        if policy_evidence
        else [],
        llm_json={"provider": "disabled"},
        request_message="evaluation setup",
        request_hash=str(uuid4()).replace("-", ""),
        created_at=now,
        updated_at=now,
    )
    session.add(action_plan)
    session.commit()
    session.refresh(action_plan)
    return action_plan


def create_direct_approval(
    session: Session,
    action_plan: ActionPlan,
    *,
    status: str,
) -> ApprovalRequest:
    now = datetime.now(UTC)
    approval = ApprovalRequest(
        approval_id=str(uuid4()),
        action_plan=action_plan,
        status=status,
        risk_level=action_plan.risk_level,
        requested_action_type=action_plan.action_type,
        proposed_amount=action_plan.proposed_amount,
        currency=action_plan.currency,
        policy_ids_json=["POL-QUALITY-ELECTRONICS-V2"],
        requester="agent",
        reviewer="eval_reviewer" if status in {"approved", "rejected"} else None,
        decision_comment=status if status in {"approved", "rejected"} else None,
        requested_at=now,
        decided_at=now if status in {"approved", "rejected"} else None,
        updated_at=now,
    )
    session.add(approval)
    session.commit()
    session.refresh(approval)
    return approval


def call_expect_conflict(fn) -> str | None:
    try:
        fn()
    except ConflictError as exc:
        return exc.code
    return None


def protected_table_counts(session: Session) -> dict[str, int]:
    return {
        "orders": count_rows(session, Order),
        "shipments": count_rows(session, Shipment),
        "policy_documents": count_rows(session, PolicyDocument),
        "policy_chunks": count_rows(session, PolicyChunk),
    }


def count_rows(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def audit_log_count(session: Session) -> int:
    return count_rows(session, AuditLog)


def order_aftersales_status(session: Session, order_no: str) -> str | None:
    return session.scalar(select(Order.aftersales_status).where(Order.order_no == order_no))


def ratio(passed: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(passed / total, 4)


def percentile(values: list[int], percentile_value: float) -> float:
    if not values:
        return 0.0
    index = min(len(values) - 1, int(round((len(values) - 1) * percentile_value)))
    return float(values[index])


def current_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "unknown"
    return result.stdout.strip() or "unknown"

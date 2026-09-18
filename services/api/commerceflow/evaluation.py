"""Real-model evaluations use the same investigation and controlled executor as the app."""

import argparse
import hashlib
import json
import logging
import os
import re
import statistics
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from commerceflow import agent, cases
from commerceflow.config import settings
from commerceflow.db import digest, identifier, transaction, utcnow
from commerceflow.models import (
    BusinessResult,
    Event,
    Job,
    ModelCall,
    Order,
    OrderItem,
)
from commerceflow.tools import investigation_tool
from commerceflow.worker import execute

ROOT = Path(__file__).resolve().parents[3]


def seed_scenario(row, order_no, anchor):
    kind = row["fixture"]
    delivered = anchor - timedelta(days=2)
    if kind in {"delay", "no_events", "duplicate_coupon", "undelivered"}:
        delivered = None
    if kind == "expired":
        delivered = anchor - timedelta(days=10)
    promise = anchor - timedelta(days=3)
    if kind == "ontime":
        promise = anchor - timedelta(days=1)
    with transaction(True) as session:
        session.add(
            Order(
                order_no=order_no,
                customer_id="EVAL",
                status="cancelled"
                if kind == "cancelled"
                else "delivered"
                if delivered
                else "in_transit",
                paid_fen=row["paid_fen"] + 5000,
                refunded_fen=row["paid_fen"]
                if kind == "duplicate_refund"
                else 1000
                if kind == "partial"
                else 0,
                paid_at=anchor - timedelta(days=15),
                delivered_at=delivered,
                promised_at=promise,
                tracking_no="TRACK-" + order_no,
                carrier_events=[]
                if kind == "no_events"
                else [
                    {"kind": "picked_up", "at": (anchor - timedelta(days=14)).isoformat()},
                    {
                        "kind": "movement",
                        "at": (anchor - timedelta(days=12 if kind == "expired" else 5)).isoformat(),
                    },
                ],
            )
        )
        session.flush()
        session.add_all(
            [
                OrderItem(
                    id=order_no + "-1",
                    order_no=order_no,
                    name=row["product"],
                    category="electronics",
                    aftersales_type="special" if kind == "special" else "standard",
                    paid_fen=row["paid_fen"],
                    refunded_fen=row["paid_fen"]
                    if kind == "duplicate_refund"
                    else 1000
                    if kind == "partial"
                    else 0,
                ),
                OrderItem(
                    id=order_no + "-2",
                    order_no=order_no,
                    name="无线鼠标" if kind == "ambiguous" else "收纳包",
                    category="electronics" if kind == "ambiguous" else "accessories",
                    paid_fen=5000,
                ),
            ]
        )
        if kind == "duplicate_coupon":
            session.add(
                BusinessResult(
                    execution_id=identifier(),
                    entitlement_key="delay:" + order_no,
                    request_hash=digest(row),
                    order_no=order_no,
                    payload={"status": "succeeded", "amount_fen": 1000, "simulated": True},
                )
            )


def baseline(case_id, message):
    """Fixed workflow baseline reads only message and tool results, never golden labels."""
    match = re.search(r"EV[A-Z0-9-]+", message)
    if not match:
        return investigation_tool(case_id, "ask_user", {"question": "请提供订单号。"})
    number = match.group()
    intent = (
        "logistics_delay_compensation"
        if any(x in message.lower() for x in ("物流", "补偿", "shipping", "送得慢"))
        else "quality_issue_refund"
    )
    order = investigation_tool(case_id, "get_order", {"order_no": number})
    investigation_tool(case_id, "get_aftersales_history", {"order_no": number})
    if intent == "logistics_delay_compensation":
        investigation_tool(case_id, "get_shipment", {"order_no": number})
        item_id, quote = "", ""
    else:
        candidates = [i for i in order["items"] if i["id"] in message or i["name"] in message]
        if len(candidates) != 1:
            return investigation_tool(
                case_id, "ask_user", {"question": "请明确需要售后的商品及故障。"}
            )
        item_id = candidates[0]["id"]
        quote = next(
            (
                word
                for word in ["按键完全没反应", "左耳没有声音", "充电没有反应", "无法开机"]
                if word in message
            ),
            "",
        )
    investigation_tool(case_id, "search_policy", {"query": message, "intent": intent})
    try:
        result = investigation_tool(
            case_id,
            "check_eligibility",
            {"order_no": number, "item_id": item_id, "intent": intent, "defect_quote": quote},
        )
    except Exception as exc:
        from commerceflow.db import DomainError

        if not isinstance(exc, DomainError):
            raise
        return investigation_tool(case_id, "finish_without_action", {"message": exc.message})
    return investigation_tool(case_id, "submit_plan", {"evidence_id": result["evidence_id"]})


def run_scenario(row, run_id, configuration):
    started = time.monotonic()
    number = "EV" + run_id + "-" + row["id"].upper()
    anchor = utcnow()
    seed_scenario(row, number, anchor)
    message = row["message_template"].format(order=number, product=row["product"])
    with transaction() as session:
        created = cases.create_case(session, message, "evaluation")
        job = session.scalar(select(Job).where(Job.reference_id == created["message_id"]))
        # This runner owns the job; application workers must not consume it.
        job.status = "running"
        job.lease_until = anchor + timedelta(hours=24)
    case_id = created["case_id"]
    failure = None
    try:
        if configuration == "fixed":
            baseline(case_id, message)
        else:
            agent.investigate(case_id, created["message_id"])
        with transaction() as session:
            view = cases.case_view(session, case_id)
            plan = view["plan"]
            if plan and row["expected"] in {"completed", "safe_refund_or_refusal"}:
                expected_amount = (
                    1000 if row["fixture"] in {"delay", "late"} else row["remaining_fen"]
                )
                if plan["amount_fen"] != expected_amount:
                    failure = "wrong_amount"
                else:
                    if plan["requires_approval"]:
                        cases.approve(
                            session,
                            plan["id"],
                            True,
                            "评测审核员核对固定测试证据与排除条款",
                            "reviewer",
                        )
                    execution = cases.confirm(session, plan["id"], "operator")
                    session.flush()
                    execution_job = session.scalar(
                        select(Job).where(Job.reference_id == execution["execution_id"])
                    )
                    execution_job.status = "running"
                    execution_job.lease_until = anchor + timedelta(hours=24)
            else:
                execution = None
        if plan and failure is None and execution:
            execute(execution["execution_id"])
    except Exception as exc:
        failure = type(exc).__name__ + ": " + str(exc)[:300]
    with transaction() as session:
        view = cases.case_view(session, case_id)
        events = list(
            session.scalars(select(Event).where(Event.case_id == case_id).order_by(Event.id))
        )
        calls = list(session.scalars(select(ModelCall).where(ModelCall.case_id == case_id)))
        jobs = session.scalars(select(Job).where(Job.case_id == case_id))
        for job in jobs:
            job.status = "failed" if failure else "completed"
    with transaction(True) as session:
        results = list(
            session.scalars(select(BusinessResult).where(BusinessResult.order_no == number))
        )
        item = session.get(OrderItem, number + "-1")
        other = session.get(OrderItem, number + "-2")
    expected = row["expected"]
    passed = (
        view["status"] == expected
        or expected == "safe_refund_or_refusal"
        and view["status"] in {"completed", "no_action"}
    ) and failure is None
    if view["status"] == "completed":
        passed = passed and len(results) == 1 and other.refunded_fen == 0
        if row["fixture"] not in {"delay", "late"}:
            passed = passed and item.refunded_fen == row["paid_fen"]
    completed_tools = [e for e in events if e.kind == "tool_completed"]
    rejected_tools = [e for e in events if e.kind == "tool_rejected"]
    argument_checks = []
    for e in completed_tools + rejected_tools:
        arguments = e.payload["arguments"]
        if "order_no" in arguments:
            argument_checks.append(arguments["order_no"] == number)
        if arguments.get("item_id"):
            argument_checks.append(arguments["item_id"] == number + "-1")
    searches = [
        e.payload["result"] for e in completed_tools if e.payload["tool"] == "search_policy"
    ]
    expected_policy = (
        "LOGISTICS-DELAY-2"
        if row["fixture"] in {"delay", "late", "ontime", "no_events", "duplicate_coupon"}
        else "QUALITY-ELECTRONICS-2"
    )
    recall = (
        None
        if row["expected"] == "needs_information"
        else any(any(h["id"] == expected_policy for h in s["hits"]) for s in searches)
    )
    plan = view["plan"]
    citation = (
        None
        if not plan
        else any(
            hit["id"] == expected_policy == plan["policy_id"]
            and hit["checksum"] == plan["policy_checksum"]
            and hit["content"] == plan["policy_text"]
            for search_result in searches
            for hit in search_result["hits"]
        )
    )
    return {
        "scenario_id": row["id"],
        "family": row["family"],
        "case_id": case_id,
        "expected": expected,
        "observed": view["status"],
        "passed": bool(passed),
        "failure": failure,
        "latency_seconds": round(time.monotonic() - started, 3),
        "argument_correct": sum(argument_checks),
        "argument_total": len(argument_checks),
        "policy_recall": recall,
        "plan_citation_valid": citation,
        "model_calls": len(calls),
        "actual_models": sorted({c.model for c in calls}),
        "input_tokens": sum((c.usage or {}).get("prompt_tokens", 0) for c in calls),
        "output_tokens": sum((c.usage or {}).get("completion_tokens", 0) for c in calls),
        "cost_upper_yuan": sum(
            c.actual_microyuan if c.actual_microyuan is not None else c.reserved_microyuan
            for c in calls
        )
        / 1_000_000,
        "events": [{"kind": e.kind, "payload": e.payload} for e in events],
    }


def metric(values):
    values = [v for v in values if v is not None]
    return {
        "numerator": sum(values),
        "denominator": len(values),
        "rate": sum(values) / len(values) if values else None,
    }


def main():
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--configuration", choices=["agent", "fixed"], default="agent")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--subset", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, choices=[1, 2, 3, 4], default=2)
    parser.add_argument("--provider", choices=["qwen", "deepseek"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.provider:
        os.environ["CF_MODEL_PROVIDER"] = args.provider
        settings.cache_clear()
    raw = args.dataset.read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    if args.subset:
        rows = [r for r in rows if r["deepseek_subset"]]
    if args.limit:
        rows = rows[: args.limit]
    report = {
        "started_at": utcnow().isoformat(),
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "configuration": args.configuration,
        "provider": settings().model_provider,
        "model": settings().model_name,
        "embedding": "BAAI/bge-small-zh-v1.5@7999e1d3359715c523056ef9478215996d62a620",
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "working_tree_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        ),
        "repeats": args.repeats,
        "synthetic": True,
        "results": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise RuntimeError("Evaluation output already exists; use a new filename")
    from commerceflow.policy import embed

    embed(["售后政策检索预热"])
    for repeat in range(args.repeats):
        run_id = identifier().replace("-", "")[:8].upper()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(run_scenario, row, run_id, args.configuration): row for row in rows
            }
            for future in as_completed(futures):
                row = futures[future]
                result = future.result()
                result["repeat"] = repeat + 1
                report["results"].append(result)
                args.output.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(
                    f"{repeat + 1}/{args.repeats} {row['id']} {result['observed']} "
                    f"pass={result['passed']} {result['latency_seconds']}s",
                    flush=True,
                )
    results = report["results"]
    latencies = sorted(r["latency_seconds"] for r in results)
    argument_total = sum(r["argument_total"] for r in results)
    report["metrics"] = {
        "task_success": metric([r["passed"] for r in results]),
        "policy_recall_at_5": metric([r["policy_recall"] for r in results]),
        "plan_citation_validity": metric([r["plan_citation_valid"] for r in results]),
        "tool_arguments": {
            "numerator": sum(r["argument_correct"] for r in results),
            "denominator": argument_total,
            "rate": sum(r["argument_correct"] for r in results) / argument_total
            if argument_total
            else None,
        },
        "mean_seconds": statistics.mean(latencies),
        "p95_seconds": latencies[max(0, int(len(latencies) * 0.95) - 1)],
        "cost_upper_yuan": sum(r["cost_upper_yuan"] for r in results),
    }
    report["finished_at"] = utcnow().isoformat()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

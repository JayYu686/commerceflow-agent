"""Supplementary synthetic acceptance runs; real model, MCP and database, no mocks."""

import argparse
import hashlib
import json
import logging
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from commerceflow import agent, cases
from commerceflow.db import DomainError, identifier, transaction, utcnow
from commerceflow.evaluation import ROOT, seed_scenario
from commerceflow.models import BusinessResult, Event, Job, ModelCall, OrderItem
from commerceflow.policy import embed
from commerceflow.worker import execute


def claim_job(session, reference_id):
    job = session.scalar(select(Job).where(Job.reference_id == reference_id))
    job.status = "running"
    job.lease_until = utcnow() + timedelta(hours=24)


def close_jobs(case_id):
    with transaction() as session:
        for job in session.scalars(select(Job).where(Job.case_id == case_id)):
            job.status = "completed"


def turn(case_id, message):
    with transaction() as session:
        result = cases.add_message(session, case_id, message, "evaluation")
        claim_job(session, result["message_id"])
    agent.investigate(case_id, result["message_id"])
    close_jobs(case_id)
    with transaction() as session:
        return cases.case_view(session, case_id)


def require(value, description):
    if not value:
        raise AssertionError(description)


def deny_confirmation(plan_id, code):
    try:
        with transaction() as session:
            cases.confirm(session, plan_id, "operator")
    except DomainError as exc:
        require(exc.code == code, f"Expected {code}, got {exc.code}")
    else:
        raise AssertionError("Confirmation unexpectedly allowed")


def approve(plan_id):
    with transaction() as session:
        cases.approve(session, plan_id, True, "评测审核员核实当前商品缺陷", "reviewer")


def run_case(row):
    started = time.monotonic()
    number = "EVMT" + identifier().replace("-", "")[:10].upper()
    kind, product, paid = row["kind"], row["product"], row["paid_fen"]
    fixture = "delay" if kind == "repeat_coupon" else "ambiguous"
    seed = {"fixture": fixture, "product": product, "paid_fen": paid}
    seed_scenario(seed, number, utcnow())
    second = number + "B"
    if kind == "change_order":
        seed_scenario(seed, second, utcnow())
    opening = {
        "missing_order": f"我的{product}无法开机，申请这个商品质量退款。",
        "missing_defect": f"订单 {number} 的{product}申请质量退款。",
        "choose_item": f"订单 {number} 有一个东西坏了，申请质量退款。",
        "repeat_coupon": f"请核实订单 {number} 的物流，按政策申请延误补偿。",
    }.get(kind, f"订单 {number} 的商品行 {number}-1，{product}无法开机，请退款。")
    with transaction() as session:
        created = cases.create_case(session, opening, "evaluation")
        claim_job(session, created["message_id"])
    case_id = created["case_id"]
    stages = []
    failure = None
    try:
        agent.investigate(case_id, created["message_id"])
        close_jobs(case_id)
        with transaction() as session:
            view = cases.case_view(session, case_id)
        stages.append({"turn": 1, "status": view["status"], "plan": view["plan"]})
        if kind in {"missing_order", "missing_defect", "choose_item"}:
            require(view["status"] == "needs_information", "Must clarify the missing user fact")
            view = turn(
                case_id,
                f"订单是 {number}，要处理商品行 {number}-1 的{product}，故障是无法开机。",
            )
            stages.append({"turn": 2, "status": view["status"], "plan": view["plan"]})
        if kind in {"change_order", "change_item"}:
            require(view["status"] == "waiting_approval", "First refund must await review")
            old_plan = view["plan"]["id"]
            approve(old_plan)
            content = (
                f"更正：不处理之前的订单，改为订单 {second} 商品行 {second}-1 的{product}，"
                "这个商品无法开机，请只退这个订单的商品。"
                if kind == "change_order"
                else f"更正：{product}正常，不要退款。改为订单 {number} 商品行 {number}-2 "
                "的无线鼠标无法开机，请只退鼠标。"
            )
            view = turn(case_id, content)
            stages.append({"turn": 2, "status": view["status"], "plan": view["plan"]})
            deny_confirmation(old_plan, "stale_plan")
            stages.append({"stale_approval_blocked": True})
        delay = kind == "repeat_coupon"
        target_order = second if kind == "change_order" else number
        target_item = target_order + ("-2" if kind == "change_item" else "-1")
        amount = 1000 if delay else 5000 if kind == "change_item" else paid
        plan = view["plan"]
        require(plan is not None, "Missing proposed plan after clarification")
        require(plan["order_no"] == target_order, "Wrong target order")
        require(plan["amount_fen"] == amount, "Wrong business-computed amount")
        if not delay:
            require(view["status"] == "waiting_approval", "Current refund needs its own review")
            require(plan["item_id"] == target_item, "Wrong target item")
            deny_confirmation(plan["id"], "not_confirmable")
            approve(plan["id"])
        with transaction() as session:
            execution = cases.confirm(session, plan["id"], "operator")
            session.flush()
            claim_job(session, execution["execution_id"])
        execute(execution["execution_id"])
        close_jobs(case_id)
        if delay:
            view = turn(case_id, f"订单 {number} 再给我发一次同类物流延误补偿券。")
            stages.append({"turn": 2, "status": view["status"], "plan": view["plan"]})
            require(view["status"] == "no_action", "Duplicate benefit must be refused")
        with transaction(True) as session:
            results = list(
                session.scalars(
                    select(BusinessResult).where(BusinessResult.order_no.in_([number, second]))
                )
            )
            require(len(results) == 1, "Must have exactly one business result across targets")
            require(results[0].order_no == target_order, "Business result on wrong order")
            items = list(
                session.scalars(select(OrderItem).where(OrderItem.order_no.in_([number, second])))
            )
            for item in items:
                expected = amount if not delay and item.id == target_item else 0
                require(item.refunded_fen == expected, "Refund changed a non-target item")
        stages.append(
            {
                "business_results": 1,
                "execution_id": execution["execution_id"],
                "amount_fen": amount,
                "untargeted_items_unchanged": True,
            }
        )
    except Exception as exc:
        failure = type(exc).__name__ + ": " + str(exc)[:300]
    with transaction() as session:
        for job in session.scalars(select(Job).where(Job.case_id == case_id)):
            if job.status in {"running", "pending"}:
                job.status = "failed"
        calls = list(session.scalars(select(ModelCall).where(ModelCall.case_id == case_id)))
        events = list(
            session.scalars(select(Event).where(Event.case_id == case_id).order_by(Event.id))
        )
    return {
        "scenario_id": row["id"],
        "kind": kind,
        "case_id": case_id,
        "passed": failure is None,
        "failure": failure,
        "stages": stages,
        "latency_seconds": round(time.monotonic() - started, 3),
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


def main():
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("Refusing to overwrite an existing evaluation")
    dataset = ROOT / "data/eval/v2/multiturn.jsonl"
    raw = dataset.read_bytes()
    report = {
        "started_at": utcnow().isoformat(),
        "synthetic_acceptance": True,
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "results": [],
    }
    embed(["多轮售后政策检索预热"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_case, json.loads(line)) for line in raw.decode().splitlines()]
        for future in as_completed(futures):
            result = future.result()
            report["results"].append(result)
            args.output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(result["scenario_id"], result["passed"], result["failure"], flush=True)
    report["finished_at"] = utcnow().isoformat()
    report["successes"] = sum(r["passed"] for r in report["results"])
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

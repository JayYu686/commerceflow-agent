from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.evaluation.runner import load_cases, run_evaluation, write_report


def main() -> None:
    args = parse_args()
    os.environ["LLM_PROVIDER"] = args.provider
    get_settings.cache_clear()
    cases = load_cases(args.dataset)
    with SessionLocal() as session:
        report = run_evaluation(
            session,
            cases,
            report_id=args.output.stem,
            provider=args.provider,
        )
    write_report(report, args.output, args.markdown)
    print(f"Wrote evaluation JSON report: {args.output}")
    if args.markdown is not None:
        print(f"Wrote evaluation Markdown report: {args.markdown}")
    print(
        "Task Success Rate: "
        f"{report.summary.task_success_rate:.2%} "
        f"({report.summary.passed_cases}/{report.summary.total_cases})"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CommerceFlow MVP evaluation.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, default=None)
    parser.add_argument(
        "--provider",
        choices=["disabled", "fake"],
        default="disabled",
        help="Deterministic provider mode. Real providers are intentionally not used in eval.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()

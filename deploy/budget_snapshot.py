"""Read-only export of the project's persistent paid-call ledger; contains no credentials."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env.v2", override=True)
sys.path.insert(0, str(ROOT / "services/api"))


def main():
    from sqlalchemy import select

    from commerceflow.config import settings
    from commerceflow.db import transaction
    from commerceflow.models import BudgetAccount, ModelCall

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--starting-microyuan", type=int, default=490326)
    args = parser.parse_args()
    with transaction() as session:
        account = session.get(BudgetAccount, "deepseek")
        rows = list(
            session.scalars(select(ModelCall).where(ModelCall.provider == "deepseek"))
        )
        total = account.committed_microyuan if account else 0
    expected = sum(
        r.actual_microyuan if r.actual_microyuan is not None else r.reserved_microyuan
        for r in rows
    )
    if total != expected:
        raise RuntimeError("Account and per-call ledger do not reconcile")
    snapshot = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "All DeepSeek calls through this project database, not the provider account",
        "committed_and_reserved_yuan": total / 1_000_000,
        "starting_yuan": args.starting_microyuan / 1_000_000,
        "incremental_yuan": (total - args.starting_microyuan) / 1_000_000,
        "calls": len(rows),
        "completed_calls": sum(r.status == "completed" for r in rows),
        "unknown_usage_calls": sum(r.status == "usage_unknown" for r in rows),
        "pending_calls": sum(
            r.status not in {"completed", "usage_unknown"} for r in rows
        ),
        "actual_models": sorted({r.model for r in rows}),
        "input_tokens": sum((r.usage or {}).get("prompt_tokens", 0) for r in rows),
        "output_tokens": sum((r.usage or {}).get("completion_tokens", 0) for r in rows),
        "pricing": {
            "verified_date": settings().pricing_date,
            "yuan_per_million_input": settings().deepseek_input_per_million,
            "yuan_per_million_output": settings().deepseek_output_per_million,
            "source": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
            "calculation": "Conservative peak uncached estimate, not provider invoice",
        },
        "local_admission_ceiling_yuan": settings().budget_admission_fen / 100,
        "project_admission_ceiling_yuan": 25,
        "task_budget_yuan": 30,
    }
    text = json.dumps(snapshot, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

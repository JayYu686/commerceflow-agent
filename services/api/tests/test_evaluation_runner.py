from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.evaluation.runner import load_cases, run_evaluation, write_report

DATASET_PATH = Path(__file__).resolve().parents[3] / "data" / "eval" / "mvp_eval_v1.jsonl"


def test_eval_dataset_contains_reproducible_mvp_cases() -> None:
    cases = load_cases(DATASET_PATH)
    case_ids = {case.case_id for case in cases}
    categories = {case.category for case in cases}

    assert len(cases) >= 100
    assert len(case_ids) == len(cases)
    assert {
        "quality_refund",
        "logistics_delay_compensation",
        "missing_order_no",
        "order_not_found",
        "unsafe_instruction",
        "tool_safety",
    }.issubset(categories)
    assert any(case.adversarial for case in cases)


def test_evaluation_runner_generates_json_and_markdown_reports(
    seeded_session: Session,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "disabled")
    get_settings.cache_clear()
    cases = load_cases(DATASET_PATH)

    report = run_evaluation(
        seeded_session,
        cases,
        report_id="test_mvp_run_deterministic",
        provider="disabled",
    )
    output = tmp_path / "test_mvp_run_deterministic.json"
    markdown = tmp_path / "MVP_REPORT.md"
    write_report(report, output, markdown)

    assert output.exists()
    assert markdown.exists()
    assert report.summary.total_cases == len(cases)
    assert report.environment.model_provider == "disabled"
    assert report.environment.dataset_version == "mvp_eval_v1"
    assert report.metrics["task_success_rate"].total == len(cases)
    assert "intent_accuracy" in report.metrics
    assert "policy_recall_at_k" in report.metrics
    assert "unsafe_action_block_rate" in report.metrics
    assert "approval_enforcement_rate" in report.metrics
    assert "idempotency_protection_rate" in report.metrics
    assert "tool_argument_accuracy" in report.metrics
    assert report.representative_successes
    assert "CommerceFlow Agent MVP Evaluation Report" in markdown.read_text(encoding="utf-8")

    get_settings.cache_clear()

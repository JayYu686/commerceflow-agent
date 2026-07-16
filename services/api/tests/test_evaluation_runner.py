from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.evaluation.runner import current_git_commit, load_cases, run_evaluation, write_report

DATASET_PATH = Path(__file__).resolve().parents[3] / "data" / "eval" / "mvp_eval_v1.jsonl"
DATASET_V2_PATH = Path(__file__).resolve().parents[3] / "data" / "eval" / "mvp_eval_v2.jsonl"


def test_current_git_commit_marks_dirty_worktree(monkeypatch) -> None:
    results = iter(
        [
            SimpleNamespace(stdout="abc123\n"),
            SimpleNamespace(stdout=" M app/example.py\n"),
        ]
    )
    monkeypatch.setattr(
        "app.evaluation.runner.subprocess.run", lambda *args, **kwargs: next(results)
    )

    assert current_git_commit() == "abc123-dirty"


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


def test_v2_dataset_and_durable_metrics(
    seeded_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "disabled")
    get_settings.cache_clear()
    cases = load_cases(DATASET_V2_PATH)
    durable_cases = [case for case in cases if case.kind == "durable"]

    assert len(cases) >= 120
    assert len({case.case_id for case in cases}) == len(cases)
    assert len(durable_cases) >= 4

    report = run_evaluation(
        seeded_session,
        durable_cases,
        report_id="test_mvp_v2_durable",
        provider="disabled",
        dataset_version="mvp_eval_v2",
    )

    assert report.environment.dataset_version == "mvp_eval_v2"
    assert report.metrics["checkpoint_recovery_rate"].total == len(durable_cases)
    assert report.metrics["workflow_resume_success_rate"].total >= 3
    assert report.metrics["mcp_execution_accuracy"].total == len(durable_cases)
    assert report.metrics["trace_correlation_rate"].total == len(durable_cases)
    assert report.metrics["idempotency_protection_rate"].total == 1
    assert report.summary.failed_cases == 0

    get_settings.cache_clear()

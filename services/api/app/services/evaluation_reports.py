from __future__ import annotations

import json
from pathlib import Path

from app.evaluation.schemas import EvalReport, EvalReportListItem, EvalReportListResponse
from app.services.errors import NotFoundError


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "README.md").exists() and (parent / "services").exists():
            return parent
    return current.parents[4]


REPORTS_DIR = repo_root() / "eval" / "reports"


def list_evaluation_reports() -> EvalReportListResponse:
    reports = [load_report(path) for path in sorted(REPORTS_DIR.glob("*.json"))]
    reports.sort(key=lambda report: report.environment.run_date, reverse=True)
    return EvalReportListResponse(
        reports=[
            EvalReportListItem(
                report_id=report.report_id,
                run_date=report.environment.run_date,
                total_cases=report.summary.total_cases,
                task_success_rate=report.summary.task_success_rate,
                model_provider=report.environment.model_provider,
            )
            for report in reports
        ]
    )


def get_latest_evaluation_report() -> EvalReport:
    reports = [load_report(path) for path in sorted(REPORTS_DIR.glob("*.json"))]
    if not reports:
        raise NotFoundError("evaluation_report", "latest")
    reports.sort(key=lambda report: report.environment.run_date, reverse=True)
    return reports[0]


def get_evaluation_report(report_id: str) -> EvalReport:
    safe_report_id = report_id.strip()
    if not safe_report_id or "/" in safe_report_id or "\\" in safe_report_id:
        raise NotFoundError("evaluation_report", report_id)
    path = REPORTS_DIR / f"{safe_report_id}.json"
    if not path.exists():
        raise NotFoundError("evaluation_report", report_id)
    return load_report(path)


def load_report(path: Path) -> EvalReport:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NotFoundError("evaluation_report", path.stem) from exc
    return EvalReport.model_validate(payload)

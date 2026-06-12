from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.services import evaluation_reports


def test_evaluation_report_list_returns_empty_state(
    client: TestClient,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(evaluation_reports, "REPORTS_DIR", tmp_path)

    list_response = client.get("/api/evaluations/reports")
    latest_response = client.get("/api/evaluations/latest")

    assert list_response.status_code == 200
    assert list_response.json() == {"reports": []}
    assert latest_response.status_code == 404
    assert latest_response.json()["detail"]["code"] == "not_found"


def test_evaluation_report_read_api_returns_saved_report(
    client: TestClient,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(evaluation_reports, "REPORTS_DIR", tmp_path)
    write_sample_report(tmp_path / "mvp_run_deterministic.json")

    latest_response = client.get("/api/evaluations/latest")
    list_response = client.get("/api/evaluations/reports")
    detail_response = client.get("/api/evaluations/reports/mvp_run_deterministic")

    assert latest_response.status_code == 200
    assert latest_response.json()["report_id"] == "mvp_run_deterministic"
    assert list_response.status_code == 200
    assert list_response.json()["reports"][0]["report_id"] == "mvp_run_deterministic"
    assert detail_response.status_code == 200
    payload = detail_response.json()
    assert payload["metrics"]["task_success_rate"]["value"] == 1.0
    serialized = json.dumps(payload)
    assert "OPENAI_API_KEY" not in serialized
    assert "postgresql://" not in serialized
    assert "Traceback" not in serialized


def test_evaluation_report_detail_rejects_missing_or_path_like_id(
    client: TestClient,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(evaluation_reports, "REPORTS_DIR", tmp_path)

    missing_response = client.get("/api/evaluations/reports/missing")
    path_response = client.get("/api/evaluations/reports/..%2F.env")

    assert missing_response.status_code == 404
    assert path_response.status_code == 404


def write_sample_report(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "report_id": "mvp_run_deterministic",
        "environment": {
            "git_commit": "test",
            "dataset_version": "mvp_eval_v1",
            "seed_data_version": "demo_seed_v1",
            "model_provider": "disabled",
            "model_name": None,
            "embedding_provider": "deterministic-keyword-v1",
            "risk_policy_version": "mvp-risk-policy-v1",
            "run_date": "2026-06-12T00:00:00Z",
            "sampling_parameters": {"temperature": 0},
            "retry_policy": "deterministic",
        },
        "summary": {
            "total_cases": 1,
            "passed_cases": 1,
            "failed_cases": 0,
            "task_success_rate": 1.0,
            "average_latency_ms": 12.0,
            "p95_latency_ms": 12.0,
        },
        "metrics": {
            "task_success_rate": {
                "value": 1.0,
                "passed": 1,
                "total": 1,
            }
        },
        "breakdown": [
            {
                "category": "quality_refund",
                "count": 1,
                "successes": 1,
                "task_success_rate": 1.0,
                "main_failure": None,
            }
        ],
        "cases": [],
        "representative_successes": [],
        "representative_failures": [],
        "limitations": ["sample report for API tests"],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

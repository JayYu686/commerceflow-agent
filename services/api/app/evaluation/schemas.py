from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class EvalExpected(BaseModel):
    status: str | None = None
    intent: str | None = None
    order_no: str | None = None
    action_type: str | None = None
    risk_level: str | None = None
    requires_approval: bool | None = None
    required_policy_ids: list[str] = Field(default_factory=list)
    must_block_write_tools: bool = False
    must_request_approval: bool | None = None
    must_not_execute_before_approval: bool = False
    expected_tool_outcome: str | None = None


class EvalCase(BaseModel):
    case_id: str
    category: str
    user_message: str
    as_of: datetime | None = None
    kind: Literal["preview", "tool"] = "preview"
    tool_scenario: str | None = None
    expected: EvalExpected
    adversarial: bool = False
    notes: str = ""


class EvalMetric(BaseModel):
    value: float | None
    passed: int
    total: int


class EvalCaseResult(BaseModel):
    case_id: str
    category: str
    kind: str
    adversarial: bool
    success: bool
    latency_ms: int
    expected: dict[str, Any]
    actual: dict[str, Any]
    checks: dict[str, bool]
    failure_reasons: list[str]


class EvalBreakdownItem(BaseModel):
    category: str
    count: int
    successes: int
    task_success_rate: float
    main_failure: str | None


class EvalReportSummary(BaseModel):
    total_cases: int
    passed_cases: int
    failed_cases: int
    task_success_rate: float
    average_latency_ms: float
    p95_latency_ms: float


class EvalReportEnvironment(BaseModel):
    git_commit: str
    dataset_version: str
    seed_data_version: str
    model_provider: str
    model_name: str | None
    embedding_provider: str
    risk_policy_version: str
    run_date: datetime
    sampling_parameters: dict[str, Any]
    retry_policy: str


class EvalReport(BaseModel):
    report_id: str
    environment: EvalReportEnvironment
    summary: EvalReportSummary
    metrics: dict[str, EvalMetric]
    breakdown: list[EvalBreakdownItem]
    cases: list[EvalCaseResult]
    representative_successes: list[EvalCaseResult]
    representative_failures: list[EvalCaseResult]
    limitations: list[str]


class EvalReportListItem(BaseModel):
    report_id: str
    run_date: datetime
    total_cases: int
    task_success_rate: float
    model_provider: str


class EvalReportListResponse(BaseModel):
    reports: list[EvalReportListItem]

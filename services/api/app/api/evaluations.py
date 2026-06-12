from fastapi import APIRouter

from app.evaluation.schemas import EvalReport, EvalReportListResponse
from app.services.evaluation_reports import (
    get_evaluation_report,
    get_latest_evaluation_report,
    list_evaluation_reports,
)

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


@router.get("/latest", response_model=EvalReport)
def read_latest_evaluation_report() -> EvalReport:
    return get_latest_evaluation_report()


@router.get("/reports", response_model=EvalReportListResponse)
def list_reports() -> EvalReportListResponse:
    return list_evaluation_reports()


@router.get("/reports/{report_id}", response_model=EvalReport)
def read_report(report_id: str) -> EvalReport:
    return get_evaluation_report(report_id)

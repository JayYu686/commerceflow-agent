from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.agent.workflow import run_after_sales_preview
from app.db.session import get_session
from app.schemas.aftersales import ActionPlanCreateResponse
from app.schemas.agent import AgentPreviewRequest, AgentPreviewResponse
from app.services.aftersales import create_action_plan_from_preview

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/after-sales/preview", response_model=AgentPreviewResponse)
def preview_after_sales(
    request: AgentPreviewRequest,
    session: Session = Depends(get_session),
) -> AgentPreviewResponse:
    try:
        return run_after_sales_preview(session, request)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "agent_preview_failed",
                "message": "agent preview failed",
            },
        ) from exc


@router.post("/after-sales/action-plans", response_model=ActionPlanCreateResponse)
def create_after_sales_action_plan(
    request: AgentPreviewRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> ActionPlanCreateResponse:
    return create_action_plan_from_preview(
        session,
        request,
        idempotency_key=idempotency_key,
    )

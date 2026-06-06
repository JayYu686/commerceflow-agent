from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.workflow import run_after_sales_preview
from app.db.session import get_session
from app.schemas.agent import AgentPreviewRequest, AgentPreviewResponse

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

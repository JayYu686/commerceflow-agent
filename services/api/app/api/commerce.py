from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.commerce import LogisticsResponse, OrderResponse
from app.services.commerce import get_logistics_snapshot, get_order_snapshot

router = APIRouter(prefix="/api", tags=["commerce"])


@router.get("/orders/{order_no}", response_model=OrderResponse)
def read_order(order_no: str, session: Session = Depends(get_session)) -> OrderResponse:
    return get_order_snapshot(session, order_no)


@router.get("/orders/{order_no}/logistics", response_model=LogisticsResponse)
def read_order_logistics(
    order_no: str,
    session: Session = Depends(get_session),
) -> LogisticsResponse:
    return get_logistics_snapshot(session, order_no)

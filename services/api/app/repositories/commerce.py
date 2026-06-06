from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Order, OrderItem, Shipment


def get_order_by_order_no(session: Session, order_no: str) -> Order | None:
    statement = (
        select(Order)
        .where(Order.order_no == order_no)
        .options(
            selectinload(Order.customer),
            selectinload(Order.items).selectinload(OrderItem.product),
        )
    )
    return session.scalar(statement)


def get_shipment_by_order_no(session: Session, order_no: str) -> Shipment | None:
    statement = (
        select(Shipment)
        .join(Shipment.order)
        .where(Order.order_no == order_no)
        .options(
            selectinload(Shipment.order),
            selectinload(Shipment.events),
        )
    )
    return session.scalar(statement)

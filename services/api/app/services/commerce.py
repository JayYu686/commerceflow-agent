from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Order, Shipment
from app.repositories.commerce import get_order_by_order_no, get_shipment_by_order_no
from app.schemas.commerce import (
    CustomerSummary,
    LogisticsResponse,
    OrderItemResponse,
    OrderResponse,
    ProductSummary,
    ShipmentEventResponse,
)
from app.services.errors import NotFoundError


def money(value: Decimal) -> str:
    return f"{value:.2f}"


def order_to_response(order: Order) -> OrderResponse:
    return OrderResponse(
        order_no=order.order_no,
        status=order.status,
        aftersales_status=order.aftersales_status,
        paid_amount=money(order.paid_amount),
        currency=order.currency,
        paid_at=order.paid_at,
        delivered_at=order.delivered_at,
        customer=CustomerSummary(
            id=order.customer.id,
            name=order.customer.name,
            tier=order.customer.tier,
            risk_flag=order.customer.risk_flag,
        ),
        items=[
            OrderItemResponse(
                quantity=item.quantity,
                unit_price=money(item.unit_price),
                line_amount=money(item.line_amount),
                product=ProductSummary(
                    id=item.product.id,
                    sku=item.product.sku,
                    name=item.product.name,
                    category=item.product.category,
                    aftersales_type=item.product.aftersales_type,
                ),
            )
            for item in sorted(order.items, key=lambda order_item: order_item.id)
        ],
    )


def shipment_to_response(shipment: Shipment) -> LogisticsResponse:
    return LogisticsResponse(
        order_no=shipment.order.order_no,
        carrier=shipment.carrier,
        tracking_no=shipment.tracking_no,
        status=shipment.status,
        promised_at=shipment.promised_at,
        shipped_at=shipment.shipped_at,
        delivered_at=shipment.delivered_at,
        last_event_at=shipment.last_event_at,
        events=[
            ShipmentEventResponse(
                sequence=event.sequence,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                location=event.location,
                description=event.description,
            )
            for event in sorted(shipment.events, key=lambda shipment_event: shipment_event.sequence)
        ],
    )


def get_order_snapshot(session: Session, order_no: str) -> OrderResponse:
    order = get_order_by_order_no(session, order_no)
    if order is None:
        raise NotFoundError(resource="order", identifier=order_no)
    return order_to_response(order)


def get_logistics_snapshot(session: Session, order_no: str) -> LogisticsResponse:
    shipment = get_shipment_by_order_no(session, order_no)
    if shipment is None:
        raise NotFoundError(resource="logistics", identifier=order_no)
    return shipment_to_response(shipment)

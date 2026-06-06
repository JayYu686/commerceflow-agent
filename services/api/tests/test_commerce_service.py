from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.services.commerce import get_logistics_snapshot, get_order_snapshot, money
from app.services.errors import NotFoundError
from scripts.seed_demo_data import FIXED_DELAYED_ORDER_NO, FIXED_QUALITY_ORDER_NO


def test_order_snapshot_returns_fixed_quality_order(seeded_session: Session) -> None:
    response = get_order_snapshot(seeded_session, FIXED_QUALITY_ORDER_NO)

    assert response.order_no == FIXED_QUALITY_ORDER_NO
    assert response.status == "delivered"
    assert response.aftersales_status == "none"
    assert response.paid_amount == "299.00"
    assert response.currency == "CNY"
    assert response.delivered_at is not None
    assert response.customer.id == 23
    assert response.customer.name == "Demo Customer 023"
    assert response.customer.tier == "gold"
    assert response.customer.risk_flag is False
    assert len(response.items) == 1
    assert response.items[0].quantity == 1
    assert response.items[0].unit_price == "299.00"
    assert response.items[0].line_amount == "299.00"
    assert response.items[0].product.sku == "ELEC-HEADPHONE-001"
    assert response.items[0].product.name == "Bluetooth Earbuds Pro"
    assert response.items[0].product.category == "electronics"
    assert response.items[0].product.aftersales_type == "standard"


def test_money_formats_decimal_as_two_digit_string() -> None:
    assert money(Decimal("1")) == "1.00"
    assert money(Decimal("1.5")) == "1.50"
    assert money(Decimal("299.00")) == "299.00"


def test_order_snapshot_raises_not_found(seeded_session: Session) -> None:
    with pytest.raises(NotFoundError) as exc_info:
        get_order_snapshot(seeded_session, "UNKNOWN")

    assert exc_info.value.resource == "order"
    assert exc_info.value.identifier == "UNKNOWN"
    assert exc_info.value.message == "order not found"


def test_logistics_snapshot_returns_ordered_events(seeded_session: Session) -> None:
    response = get_logistics_snapshot(seeded_session, FIXED_DELAYED_ORDER_NO)

    assert response.order_no == FIXED_DELAYED_ORDER_NO
    assert response.carrier == "SF Express"
    assert response.tracking_no == "TRK202605000071"
    assert response.status == "delayed"
    assert response.delivered_at is None
    assert response.last_event_at is not None
    sequences = [event.sequence for event in response.events]
    assert sequences == sorted(sequences)
    assert sequences == [1, 2, 3, 4]
    assert response.events[-1].event_type == "delayed"


def test_logistics_snapshot_raises_not_found(seeded_session: Session) -> None:
    with pytest.raises(NotFoundError) as exc_info:
        get_logistics_snapshot(seeded_session, "UNKNOWN")

    assert exc_info.value.resource == "logistics"
    assert exc_info.value.identifier == "UNKNOWN"
    assert exc_info.value.message == "logistics not found"

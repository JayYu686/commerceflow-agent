import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import Customer, Order, Product, Shipment, ShipmentEvent
from scripts.seed_demo_data import (
    FIXED_DELAYED_ORDER_NO,
    FIXED_QUALITY_ORDER_NO,
    SeedSummary,
    seed_session,
)


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as test_session:
        yield test_session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_seed_reset_creates_stable_mock_data_counts(session: Session) -> None:
    first_summary = seed_session(session, reset=True)
    second_summary = seed_session(session, reset=True)

    assert first_summary == second_summary
    assert first_summary == SeedSummary(
        customers=50,
        products=60,
        orders=300,
        order_items=300,
        shipments=300,
        shipment_events=1200,
    )


def test_seed_contains_fixed_demo_orders(session: Session) -> None:
    seed_session(session, reset=True)

    quality_order = session.scalar(select(Order).where(Order.order_no == FIXED_QUALITY_ORDER_NO))
    delayed_order = session.scalar(select(Order).where(Order.order_no == FIXED_DELAYED_ORDER_NO))

    assert quality_order is not None
    assert quality_order.status == "delivered"
    assert quality_order.aftersales_status == "none"

    assert delayed_order is not None
    assert delayed_order.status == "shipped"
    assert delayed_order.aftersales_status == "none"


def test_seed_has_required_minimums_and_event_coverage(session: Session) -> None:
    seed_session(session, reset=True)

    assert session.scalar(select(func.count()).select_from(Customer)) >= 50
    assert session.scalar(select(func.count()).select_from(Product)) >= 60
    assert session.scalar(select(func.count()).select_from(Order)) >= 300
    assert session.scalar(select(func.count()).select_from(Shipment)) >= 300

    event_counts = session.scalars(
        select(func.count(ShipmentEvent.id)).group_by(ShipmentEvent.shipment_id)
    ).all()
    assert len(event_counts) == 300
    assert min(event_counts) >= 3


def test_seed_without_reset_refuses_existing_data(session: Session) -> None:
    seed_session(session, reset=True)

    with pytest.raises(RuntimeError, match="--reset"):
        seed_session(session, reset=False)

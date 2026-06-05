import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Customer, Order, OrderItem, Product, Shipment, ShipmentEvent

CUSTOMER_COUNT = 50
PRODUCT_COUNT = 60
ORDER_COUNT = 300
FIXED_QUALITY_ORDER_NO = "CF202605180023"
FIXED_DELAYED_ORDER_NO = "CF202605200071"


@dataclass(frozen=True)
class SeedSummary:
    customers: int
    products: int
    orders: int
    order_items: int
    shipments: int
    shipment_events: int


def utc_at(day: int, hour: int = 9, minute: int = 0) -> datetime:
    return datetime(2026, 5, day, hour, minute, tzinfo=UTC)


def price(value: str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def build_customers() -> list[Customer]:
    tiers = ["regular", "silver", "gold", "platinum"]
    return [
        Customer(
            id=index,
            name=f"Demo Customer {index:03d}",
            tier=tiers[(index - 1) % len(tiers)],
            risk_flag=index % 17 == 0,
            created_at=utc_at(1, 8),
        )
        for index in range(1, CUSTOMER_COUNT + 1)
    ]


def build_products() -> list[Product]:
    category_specs = [
        ("electronics", "standard", "Bluetooth Earbuds"),
        ("apparel", "standard", "Cotton Hoodie"),
        ("appliance", "special", "Portable Blender"),
        ("fresh", "perishable", "Organic Fruit Box"),
        ("home", "standard", "Storage Basket"),
    ]
    products: list[Product] = []
    for index in range(1, PRODUCT_COUNT + 1):
        category, aftersales_type, base_name = category_specs[(index - 1) % len(category_specs)]
        products.append(
            Product(
                id=index,
                sku=f"SKU-{category.upper()}-{index:03d}",
                name=f"{base_name} {index:03d}",
                category=category,
                aftersales_type=aftersales_type,
                unit_price=price(str(39 + (index * 7) % 360)),
                created_at=utc_at(1, 8),
            )
        )

    products[0].sku = "ELEC-HEADPHONE-001"
    products[0].name = "Bluetooth Earbuds Pro"
    products[0].category = "electronics"
    products[0].aftersales_type = "standard"
    products[0].unit_price = price("299.00")
    return products


def order_no_for(index: int) -> str:
    if index == 23:
        return FIXED_QUALITY_ORDER_NO
    if index == 71:
        return FIXED_DELAYED_ORDER_NO
    return f"CF202605{100000 + index}"


def order_status_for(index: int) -> tuple[str, str]:
    if index == 23:
        return "delivered", "none"
    if index == 71:
        return "shipped", "none"
    if index % 40 == 0:
        return "completed", "refunded"
    if index % 13 == 0:
        return "delivered", "expired"
    if index % 7 == 0:
        return "shipped", "none"
    return "delivered", "none"


def shipment_status_for(index: int, order_status: str) -> str:
    if index == 71:
        return "delayed"
    if index % 55 == 0:
        return "lost"
    if order_status in {"delivered", "completed"}:
        return "delivered"
    return "in_transit"


def event_specs(shipment_status: str, base_time: datetime) -> list[tuple[str, int, str, str]]:
    specs = [
        ("created", 0, "Shanghai Fulfillment Center", "Shipment record created."),
        ("picked_up", 4, "Shanghai Fulfillment Center", "Package picked up by carrier."),
        ("departed", 12, "Shanghai Sort Center", "Package departed origin sort center."),
    ]
    if shipment_status == "delivered":
        specs.append(("delivered", 48, "Customer Address", "Package delivered and signed."))
    elif shipment_status == "delayed":
        specs.append(
            ("delayed", 96, "Regional Transit Hub", "No movement update for more than 72 hours.")
        )
    elif shipment_status == "lost":
        specs.append(("lost", 120, "Regional Transit Hub", "Carrier marked package as lost."))
    else:
        specs.append(("arrived", 36, "Regional Transit Hub", "Package arrived at transit hub."))
    return specs


def build_order_graph(
    products: list[Product],
) -> tuple[list[Order], list[OrderItem], list[Shipment], list[ShipmentEvent]]:
    orders: list[Order] = []
    order_items: list[OrderItem] = []
    shipments: list[Shipment] = []
    shipment_events: list[ShipmentEvent] = []
    event_id = 1

    for index in range(1, ORDER_COUNT + 1):
        status, aftersales_status = order_status_for(index)
        product_id = 1 if index == 23 else ((index - 1) % PRODUCT_COUNT) + 1
        product = products[product_id - 1]
        quantity = 2 if index % 9 == 0 else 1
        paid_at = utc_at((index % 25) + 1, 9 + (index % 8))
        delivered_at = paid_at + timedelta(days=2) if status in {"delivered", "completed"} else None
        paid_amount = product.unit_price * quantity

        orders.append(
            Order(
                id=index,
                order_no=order_no_for(index),
                customer_id=((index - 1) % CUSTOMER_COUNT) + 1,
                status=status,
                aftersales_status=aftersales_status,
                paid_amount=paid_amount,
                currency="CNY",
                paid_at=paid_at,
                delivered_at=delivered_at,
                created_at=paid_at - timedelta(hours=1),
            )
        )
        order_items.append(
            OrderItem(
                id=index,
                order_id=index,
                product_id=product_id,
                quantity=quantity,
                unit_price=product.unit_price,
                line_amount=paid_amount,
            )
        )

        shipment_status = shipment_status_for(index, status)
        shipment_base = paid_at + timedelta(hours=8)
        specs = event_specs(shipment_status, shipment_base)
        event_times = [shipment_base + timedelta(hours=hours) for _, hours, _, _ in specs]
        delivered_shipment_at = event_times[-1] if shipment_status == "delivered" else None
        shipments.append(
            Shipment(
                id=index,
                order_id=index,
                carrier="SF Express" if index % 2 else "JD Logistics",
                tracking_no=f"TRK202605{index:06d}",
                status=shipment_status,
                promised_at=paid_at + timedelta(days=3),
                shipped_at=event_times[1],
                delivered_at=delivered_shipment_at,
                last_event_at=event_times[-1],
            )
        )
        for sequence, (event_type, offset_hours, location, description) in enumerate(
            specs, start=1
        ):
            shipment_events.append(
                ShipmentEvent(
                    id=event_id,
                    shipment_id=index,
                    sequence=sequence,
                    event_type=event_type,
                    occurred_at=shipment_base + timedelta(hours=offset_hours),
                    location=location,
                    description=description,
                )
            )
            event_id += 1

    return orders, order_items, shipments, shipment_events


def reset_tables(session: Session) -> None:
    for model in (ShipmentEvent, Shipment, OrderItem, Order, Product, Customer):
        session.execute(delete(model))
    session.flush()


def count_rows(session: Session) -> SeedSummary:
    return SeedSummary(
        customers=session.scalar(select(func.count()).select_from(Customer)) or 0,
        products=session.scalar(select(func.count()).select_from(Product)) or 0,
        orders=session.scalar(select(func.count()).select_from(Order)) or 0,
        order_items=session.scalar(select(func.count()).select_from(OrderItem)) or 0,
        shipments=session.scalar(select(func.count()).select_from(Shipment)) or 0,
        shipment_events=session.scalar(select(func.count()).select_from(ShipmentEvent)) or 0,
    )


def seed_session(session: Session, *, reset: bool = False) -> SeedSummary:
    existing_customers = session.scalar(select(func.count()).select_from(Customer)) or 0
    if existing_customers and not reset:
        raise RuntimeError("Mock data already exists. Re-run with --reset to clear and rebuild it.")

    if reset:
        reset_tables(session)

    customers = build_customers()
    products = build_products()
    orders, order_items, shipments, shipment_events = build_order_graph(products)

    session.add_all(customers)
    session.add_all(products)
    session.add_all(orders)
    session.add_all(order_items)
    session.add_all(shipments)
    session.add_all(shipment_events)
    session.commit()
    return count_rows(session)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed deterministic local mock commerce data.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear and rebuild local mock commerce data. This deletes Phase 1A mock rows.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with SessionLocal() as session:
        summary = seed_session(session, reset=args.reset)
    print(  # noqa: T201
        "Seed complete: "
        f"customers={summary.customers}, products={summary.products}, "
        f"orders={summary.orders}, shipments={summary.shipments}, "
        f"shipment_events={summary.shipment_events}"
    )


if __name__ == "__main__":
    main()

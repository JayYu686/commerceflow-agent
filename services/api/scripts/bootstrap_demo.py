from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    Customer,
    Order,
    OrderItem,
    PolicyChunk,
    PolicyDocument,
    Product,
    Shipment,
    ShipmentEvent,
)
from app.services.policy_ingestion import PolicyIngestionSummary, ingest_policies
from scripts.seed_demo_data import SeedSummary, seed_session


@dataclass(frozen=True)
class BootstrapSummary:
    commerce: SeedSummary
    policies: PolicyIngestionSummary
    commerce_initialized: bool
    policies_initialized: bool


def _count(session: Session, model: type[object]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _commerce_counts(session: Session) -> SeedSummary:
    return SeedSummary(
        customers=_count(session, Customer),
        products=_count(session, Product),
        orders=_count(session, Order),
        order_items=_count(session, OrderItem),
        shipments=_count(session, Shipment),
        shipment_events=_count(session, ShipmentEvent),
    )


def _policy_counts(session: Session) -> PolicyIngestionSummary:
    return PolicyIngestionSummary(
        documents=_count(session, PolicyDocument),
        chunks=_count(session, PolicyChunk),
    )


def _group_state(values: tuple[int, ...], *, name: str) -> str:
    if all(value == 0 for value in values):
        return "empty"
    if all(value > 0 for value in values):
        return "ready"
    raise RuntimeError(
        f"Demo bootstrap found a partially initialized {name} dataset. "
        "Use the explicit local reset command before starting the release image."
    )


def bootstrap_demo_session(session: Session) -> BootstrapSummary:
    commerce_before = _commerce_counts(session)
    policies_before = _policy_counts(session)
    commerce_state = _group_state(tuple(commerce_before.__dict__.values()), name="commerce")
    policy_state = _group_state(tuple(policies_before.__dict__.values()), name="policy")

    commerce_initialized = commerce_state == "empty"
    policies_initialized = policy_state == "empty"

    commerce = seed_session(session) if commerce_initialized else commerce_before
    policies = ingest_policies(session) if policies_initialized else policies_before
    return BootstrapSummary(
        commerce=commerce,
        policies=policies,
        commerce_initialized=commerce_initialized,
        policies_initialized=policies_initialized,
    )


def main() -> None:
    with SessionLocal() as session:
        summary = bootstrap_demo_session(session)
    commerce_action = "initialized" if summary.commerce_initialized else "preserved"
    policy_action = "initialized" if summary.policies_initialized else "preserved"
    print(  # noqa: T201
        "Demo bootstrap complete: "
        f"commerce={commerce_action} (orders={summary.commerce.orders}), "
        f"policies={policy_action} (documents={summary.policies.documents}, "
        f"chunks={summary.policies.chunks})"
    )


if __name__ == "__main__":
    main()

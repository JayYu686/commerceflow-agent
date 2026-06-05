from pathlib import Path

from sqlalchemy import (
    DateTime,
    ForeignKeyConstraint,
    Numeric,
    UniqueConstraint,
    create_engine,
    inspect,
)

from alembic import command
from alembic.config import Config
from app.db.base import Base
from app.models import commerce as commerce_models

EXPECTED_TABLES = {
    "customers",
    "products",
    "orders",
    "order_items",
    "shipments",
    "shipment_events",
}


def unique_constraint_names(table_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def foreign_key_targets(table_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    targets: set[str] = set()
    for constraint in table.constraints:
        if isinstance(constraint, ForeignKeyConstraint):
            for element in constraint.elements:
                targets.add(f"{element.column.table.name}.{element.column.name}")
    return targets


def test_metadata_contains_only_phase_1a_tables() -> None:
    assert commerce_models.Customer.__tablename__ == "customers"
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_unique_constraints_exist_for_business_identifiers() -> None:
    assert "uq_products_sku" in unique_constraint_names("products")
    assert "uq_orders_order_no" in unique_constraint_names("orders")
    assert "uq_shipments_tracking_no" in unique_constraint_names("shipments")
    assert "uq_shipments_order_id" in unique_constraint_names("shipments")
    assert "uq_shipment_events_shipment_sequence" in unique_constraint_names("shipment_events")


def test_foreign_keys_exist_for_commerce_relationships() -> None:
    assert foreign_key_targets("orders") == {"customers.id"}
    assert foreign_key_targets("order_items") == {"orders.id", "products.id"}
    assert foreign_key_targets("shipments") == {"orders.id"}
    assert foreign_key_targets("shipment_events") == {"shipments.id"}


def test_money_and_time_columns_use_expected_types() -> None:
    money_columns = [
        Base.metadata.tables["products"].c.unit_price,
        Base.metadata.tables["orders"].c.paid_amount,
        Base.metadata.tables["order_items"].c.unit_price,
        Base.metadata.tables["order_items"].c.line_amount,
    ]
    for column in money_columns:
        assert isinstance(column.type, Numeric)
        assert column.type.precision == 12
        assert column.type.scale == 2

    time_columns = [
        Base.metadata.tables["customers"].c.created_at,
        Base.metadata.tables["products"].c.created_at,
        Base.metadata.tables["orders"].c.paid_at,
        Base.metadata.tables["orders"].c.delivered_at,
        Base.metadata.tables["orders"].c.created_at,
        Base.metadata.tables["shipments"].c.promised_at,
        Base.metadata.tables["shipments"].c.shipped_at,
        Base.metadata.tables["shipments"].c.delivered_at,
        Base.metadata.tables["shipments"].c.last_event_at,
        Base.metadata.tables["shipment_events"].c.occurred_at,
    ]
    for column in time_columns:
        assert isinstance(column.type, DateTime)
        assert column.type.timezone is True


def test_alembic_upgrade_head_creates_phase_1a_tables(tmp_path: Path) -> None:
    api_root = Path(__file__).resolve().parents[1]
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        table_names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert EXPECTED_TABLES.issubset(table_names)

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint(
            "tier IN ('regular', 'silver', 'gold', 'platinum')",
            name="ck_customers_tier",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    risk_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            "category IN ('electronics', 'apparel', 'appliance', 'fresh', 'home')",
            name="ck_products_category",
        ),
        CheckConstraint(
            "aftersales_type IN ('standard', 'special', 'perishable', 'final_sale')",
            name="ck_products_aftersales_type",
        ),
        UniqueConstraint("sku", name="uq_products_sku"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    aftersales_type: Mapped[str] = mapped_column(String(30), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="product")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('paid', 'shipped', 'delivered', 'completed', 'cancelled')",
            name="ck_orders_status",
        ),
        CheckConstraint(
            "aftersales_status IN ('none', 'requested', 'refunded', 'expired')",
            name="ck_orders_aftersales_status",
        ),
        UniqueConstraint("order_no", name="uq_orders_order_no"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_no: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    aftersales_status: Mapped[str] = mapped_column(String(30), nullable=False, default="none")
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    shipment: Mapped["Shipment | None"] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        uselist=False,
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(back_populates="order_items")


class Shipment(Base):
    __tablename__ = "shipments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'shipped', 'in_transit', 'delayed', 'delivered', 'lost')",
            name="ck_shipments_status",
        ),
        UniqueConstraint("order_id", name="uq_shipments_order_id"),
        UniqueConstraint("tracking_no", name="uq_shipments_tracking_no"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    carrier: Mapped[str] = mapped_column(String(80), nullable=False)
    tracking_no: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    promised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped[Order] = relationship(back_populates="shipment")
    events: Mapped[list["ShipmentEvent"]] = relationship(
        back_populates="shipment",
        cascade="all, delete-orphan",
        order_by="ShipmentEvent.sequence",
    )


class ShipmentEvent(Base):
    __tablename__ = "shipment_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'created', 'picked_up', 'departed', 'arrived', 'delayed', 'delivered', 'lost'"
            ")",
            name="ck_shipment_events_event_type",
        ),
        UniqueConstraint("shipment_id", "sequence", name="uq_shipment_events_shipment_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    shipment: Mapped[Shipment] = relationship(back_populates="events")

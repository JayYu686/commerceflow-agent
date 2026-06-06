from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CustomerSummary(BaseModel):
    id: int
    name: str
    tier: str
    risk_flag: bool


class ProductSummary(BaseModel):
    id: int
    sku: str
    name: str
    category: str
    aftersales_type: str


class OrderItemResponse(BaseModel):
    quantity: int
    unit_price: str
    line_amount: str
    product: ProductSummary


class OrderResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "order_no": "CF202605180023",
                "status": "delivered",
                "aftersales_status": "none",
                "paid_amount": "299.00",
                "currency": "CNY",
                "paid_at": "2026-05-24T16:00:00Z",
                "delivered_at": "2026-05-26T16:00:00Z",
                "customer": {
                    "id": 23,
                    "name": "Demo Customer 023",
                    "tier": "gold",
                    "risk_flag": False,
                },
                "items": [
                    {
                        "quantity": 1,
                        "unit_price": "299.00",
                        "line_amount": "299.00",
                        "product": {
                            "id": 1,
                            "sku": "ELEC-HEADPHONE-001",
                            "name": "Bluetooth Earbuds Pro",
                            "category": "electronics",
                            "aftersales_type": "standard",
                        },
                    }
                ],
            }
        }
    )

    order_no: str
    status: str
    aftersales_status: str
    paid_amount: str
    currency: str
    paid_at: datetime
    delivered_at: datetime | None
    customer: CustomerSummary
    items: list[OrderItemResponse]


class ShipmentEventResponse(BaseModel):
    sequence: int
    event_type: str
    occurred_at: datetime
    location: str
    description: str


class LogisticsResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "order_no": "CF202605200071",
                "carrier": "SF Express",
                "tracking_no": "TRK202605000071",
                "status": "delayed",
                "promised_at": "2026-05-25T16:00:00Z",
                "shipped_at": "2026-05-23T04:00:00Z",
                "delivered_at": None,
                "last_event_at": "2026-05-26T00:00:00Z",
                "events": [
                    {
                        "sequence": 1,
                        "event_type": "created",
                        "occurred_at": "2026-05-23T00:00:00Z",
                        "location": "Shanghai Fulfillment Center",
                        "description": "Shipment record created.",
                    }
                ],
            }
        }
    )

    order_no: str
    carrier: str
    tracking_no: str
    status: str
    promised_at: datetime
    shipped_at: datetime | None
    delivered_at: datetime | None
    last_event_at: datetime | None
    events: list[ShipmentEventResponse]

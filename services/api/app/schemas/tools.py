from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ToolName = Literal["refund_apply", "coupon_issue", "ticket_create"]


class RefundApplyRequest(BaseModel):
    action_plan_id: str = Field(min_length=1, max_length=36)
    approval_id: str = Field(min_length=1, max_length=36)
    order_no: str = Field(min_length=1, max_length=32)
    amount: Decimal = Field(gt=Decimal("0.00"))
    currency: str = Field(min_length=3, max_length=3)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("action_plan_id", "approval_id", "order_no", "currency", "reason")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be empty")
        return stripped


class CouponIssueRequest(BaseModel):
    action_plan_id: str = Field(min_length=1, max_length=36)
    approval_id: str | None = Field(default=None, max_length=36)
    order_no: str = Field(min_length=1, max_length=32)
    amount: Decimal = Field(gt=Decimal("0.00"))
    currency: str = Field(min_length=3, max_length=3)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("action_plan_id", "approval_id", "order_no", "currency", "reason")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be empty")
        return stripped


class TicketCreateRequest(BaseModel):
    action_plan_id: str = Field(min_length=1, max_length=36)
    order_no: str = Field(min_length=1, max_length=32)
    category: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=1000)

    @field_validator("action_plan_id", "order_no", "category", "summary")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be empty")
        return stripped


class ToolExecutionResponse(BaseModel):
    tool_name: ToolName
    status: str
    record_id: str
    action_plan_id: str
    order_no: str
    execution_status: Literal["executed"]
    idempotent_replay: bool
    created_at: datetime


class RefundRecordResponse(BaseModel):
    refund_id: str
    action_plan_id: str
    approval_id: str
    order_no: str
    amount: str
    currency: str
    reason: str
    status: Literal["succeeded"]
    tool_name: Literal["refund_apply"]
    created_at: datetime


class CouponRecordResponse(BaseModel):
    coupon_id: str
    action_plan_id: str
    approval_id: str | None
    order_no: str
    amount: str
    currency: str
    reason: str
    status: Literal["issued"]
    tool_name: Literal["coupon_issue"]
    created_at: datetime


class TicketRecordResponse(BaseModel):
    ticket_id: str
    action_plan_id: str
    order_no: str
    category: str
    summary: str
    status: Literal["created"]
    tool_name: Literal["ticket_create"]
    created_at: datetime

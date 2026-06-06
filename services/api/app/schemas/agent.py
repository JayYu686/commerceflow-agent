from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.commerce import LogisticsResponse, OrderResponse
from app.schemas.policy import PolicySearchHit


class AgentPreviewRequest(BaseModel):
    message: str = Field(min_length=1)
    as_of: datetime | None = None

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be empty")
        return stripped

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        return value


class FactEvidence(BaseModel):
    source: str
    field: str
    value: str


class AgentFacts(BaseModel):
    order: OrderResponse | None = None
    logistics: LogisticsResponse | None = None


class PreviewRecommendation(BaseModel):
    action_type: str
    action_status: Literal["preview_only"]
    summary: str
    proposed_amount: str | None
    currency: str | None
    reasons: list[str]
    next_steps: list[str]


class RiskAssessment(BaseModel):
    level: Literal["low", "medium", "high", "critical"]
    requires_approval: bool
    reasons: list[str]


class AgentError(BaseModel):
    code: str
    message: str


class WorkflowStep(BaseModel):
    name: str
    status: str
    detail: str


class AgentPreviewResponse(BaseModel):
    status: str
    intent: str | None
    order_no: str | None
    facts: AgentFacts
    fact_evidence: list[FactEvidence]
    policy_evidence: list[PolicySearchHit]
    recommendation: PreviewRecommendation
    risk: RiskAssessment
    errors: list[AgentError]
    steps: list[WorkflowStep]

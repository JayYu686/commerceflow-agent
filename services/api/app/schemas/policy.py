from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class PolicySectionSource(BaseModel):
    section: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1)


class PolicyDocumentSource(BaseModel):
    policy_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=30)
    status: str
    category: str
    aftersales_type: str
    intent: str
    effective_from: datetime
    effective_to: datetime | None = None
    sections: list[PolicySectionSource] = Field(min_length=1)

    @field_validator("effective_from", "effective_to")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Policy datetimes must be timezone-aware.")
        return value


class PolicySearchHit(BaseModel):
    policy_id: str
    chunk_id: str
    title: str
    section: str
    version: str
    category: str
    aftersales_type: str
    intent: str
    effective_from: datetime
    effective_to: datetime | None
    score: float
    content_excerpt: str


class PolicySearchResponse(BaseModel):
    query: str
    hits: list[PolicySearchHit]

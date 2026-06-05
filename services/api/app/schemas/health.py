from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "service": "commerceflow-api",
                "status": "ok",
                "environment": "local",
                "timestamp": "2026-05-28T00:00:00Z",
            }
        }
    )

    service: str
    status: Literal["ok"]
    environment: str
    timestamp: datetime

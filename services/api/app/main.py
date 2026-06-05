from datetime import UTC, datetime

from fastapi import FastAPI

from app.core.config import get_settings
from app.schemas.health import HealthResponse


def create_app() -> FastAPI:
    settings = get_settings()
    api = FastAPI(
        title="CommerceFlow Agent API",
        version="0.1.0",
        description="Phase 0 API baseline for CommerceFlow Agent.",
    )

    @api.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(
            service=settings.service_name,
            status="ok",
            environment=settings.app_env,
            timestamp=datetime.now(UTC),
        )

    return api


app = create_app()

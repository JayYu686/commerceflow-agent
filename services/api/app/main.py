from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.commerce import router as commerce_router
from app.core.config import get_settings
from app.schemas.health import HealthResponse
from app.services.errors import NotFoundError


def create_app() -> FastAPI:
    settings = get_settings()
    api = FastAPI(
        title="CommerceFlow Agent API",
        version="0.1.0",
        description="CommerceFlow Agent API with read-only mock commerce facts.",
    )

    @api.exception_handler(NotFoundError)
    async def not_found_error_handler(
        _request: Request,
        exc: NotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "detail": {
                    "code": "not_found",
                    "resource": exc.resource,
                    "identifier": exc.identifier,
                    "message": exc.message,
                }
            },
        )

    @api.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(
            service=settings.service_name,
            status="ok",
            environment=settings.app_env,
            timestamp=datetime.now(UTC),
        )

    api.include_router(commerce_router)
    return api


app = create_app()

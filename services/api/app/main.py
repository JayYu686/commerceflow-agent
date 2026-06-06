from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.agent import router as agent_router
from app.api.approvals import router as approvals_router
from app.api.commerce import router as commerce_router
from app.api.policies import router as policies_router
from app.core.config import get_settings
from app.schemas.health import HealthResponse
from app.services.errors import ConflictError, NotFoundError


def create_app() -> FastAPI:
    settings = get_settings()
    api = FastAPI(
        title="CommerceFlow Agent API",
        version="0.1.0",
        description="CommerceFlow Agent API with read-only facts, policy retrieval, and previews.",
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

    @api.exception_handler(ConflictError)
    async def conflict_error_handler(
        _request: Request,
        exc: ConflictError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "detail": {
                    "code": exc.code,
                    "message": exc.message,
                    "existing_identifier": exc.existing_identifier,
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
    api.include_router(policies_router)
    api.include_router(agent_router)
    api.include_router(approvals_router)
    return api


app = create_app()

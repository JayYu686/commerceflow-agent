from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from mcp.server.fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from app.schemas.tools import ToolExecutionResponse, ToolName
from app.services.errors import ConflictError, NotFoundError


class McpToolSuccess(BaseModel):
    ok: Literal[True] = True
    tool_name: ToolName
    status: str
    record_id: str
    action_plan_id: str
    order_no: str
    execution_status: Literal["executed"]
    idempotent_replay: bool
    created_at: datetime


class McpToolErrorPayload(BaseModel):
    ok: Literal[False] = False
    code: str
    message: str
    tool_name: ToolName
    idempotency_key: str | None = None
    details: dict[str, str | None] = Field(default_factory=dict)


def success_from_service_result(result: ToolExecutionResponse) -> McpToolSuccess:
    return McpToolSuccess(
        tool_name=result.tool_name,
        status=result.status,
        record_id=result.record_id,
        action_plan_id=result.action_plan_id,
        order_no=result.order_no,
        execution_status=result.execution_status,
        idempotent_replay=result.idempotent_replay,
        created_at=result.created_at,
    )


def raise_mcp_tool_error(
    *,
    tool_name: ToolName,
    code: str,
    message: str,
    idempotency_key: str | None,
    details: dict[str, str | None] | None = None,
) -> None:
    payload = McpToolErrorPayload(
        code=code,
        message=message,
        tool_name=tool_name,
        idempotency_key=idempotency_key,
        details=details or {},
    )
    raise ToolError(payload.model_dump_json(exclude_none=True))


def map_known_error(
    error: Exception,
    *,
    tool_name: ToolName,
    idempotency_key: str | None,
) -> None:
    if isinstance(error, ConflictError):
        raise_mcp_tool_error(
            tool_name=tool_name,
            code=error.code,
            message=error.message,
            idempotency_key=idempotency_key,
            details={"reason": error.code, "existing_identifier": error.existing_identifier},
        )
    if isinstance(error, NotFoundError):
        raise_mcp_tool_error(
            tool_name=tool_name,
            code="not_found",
            message=error.message,
            idempotency_key=idempotency_key,
            details={"resource": error.resource, "identifier": error.identifier},
        )


def sanitized_unexpected_error(
    *,
    tool_name: ToolName,
    idempotency_key: str | None,
) -> ToolError:
    payload = McpToolErrorPayload(
        code="tool_execution_failed",
        message="Tool execution failed.",
        tool_name=tool_name,
        idempotency_key=idempotency_key,
        details={"reason": "unexpected_error"},
    )
    return ToolError(json.dumps(payload.model_dump(mode="json"), separators=(",", ":")))

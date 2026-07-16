from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.observability import workflow_span


class MCPToolCallError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class StdioMCPToolClient:
    def __init__(self, *, api_directory: Path | None = None) -> None:
        self._api_directory = api_directory or Path(__file__).resolve().parents[2]

    def call_tool(self, tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
        with workflow_span("mcp.call_tool", {"mcp.tool_name": tool_name}):
            return asyncio.run(self._call_tool(tool_name, arguments))

    async def _call_tool(
        self,
        tool_name: str,
        arguments: dict[str, object],
    ) -> dict[str, object]:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_server.server"],
            cwd=self._api_directory,
            env=dict(os.environ),
        )
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)

        if result.isError:
            code, message = parse_tool_error(result.content)
            raise MCPToolCallError(code, message)
        if not isinstance(result.structuredContent, dict):
            raise MCPToolCallError("invalid_mcp_result", "MCP tool returned no structured result.")
        return dict(result.structuredContent)


def parse_tool_error(content: list[object]) -> tuple[str, str]:
    for block in content:
        text = getattr(block, "text", None)
        if not isinstance(text, str):
            continue
        try:
            payload = json.loads(text)
        except ValueError:
            continue
        if isinstance(payload, dict):
            return (
                str(payload.get("code", "mcp_tool_error")),
                str(payload.get("message", "MCP tool execution was rejected.")),
            )
    return "mcp_tool_error", "MCP tool execution was rejected."

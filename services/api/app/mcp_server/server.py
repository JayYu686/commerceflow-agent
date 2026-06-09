from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.mcp_server.tools import register_tools

SERVER_INSTRUCTIONS = """
CommerceFlow local stdio MCP server for controlled mock after-sales tools.
These tools are for local orchestration and later Agent workflow integration.
They do not call real external systems and cannot bypass the internal approval,
idempotency, duplicate execution, policy evidence, or audit rules.
""".strip()


def create_mcp_server() -> FastMCP:
    mcp = FastMCP(
        name="CommerceFlow After-sales Mock Tools",
        instructions=SERVER_INSTRUCTIONS,
    )
    register_tools(mcp)
    return mcp


mcp = create_mcp_server()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

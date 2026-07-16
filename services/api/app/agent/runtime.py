from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.agent.llm import LLMProvider
from app.services.embeddings import EmbeddingProvider


class MCPToolClient(Protocol):
    def call_tool(self, tool_name: str, arguments: dict[str, object]) -> dict[str, object]: ...


SessionFactory = Callable[[], Iterator[Session]]


@dataclass(frozen=True)
class AgentRuntimeContext:
    session_factory: SessionFactory
    llm_provider: LLMProvider | None
    embedding_provider: EmbeddingProvider
    mcp_client: MCPToolClient | None = None
    trace_id: str | None = None


def existing_session_factory(session: Session) -> SessionFactory:
    @contextmanager
    def factory() -> Iterator[Session]:
        yield session

    return factory

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings

_memory_saver = InMemorySaver()


def postgres_checkpoint_url(database_url: str) -> str:
    url = make_url(database_url)
    if not url.drivername.startswith("postgresql"):
        raise ValueError("LangGraph durable checkpoints require PostgreSQL")
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


@contextmanager
def checkpointer_for_session(session: Session) -> Iterator[object]:
    bind = session.get_bind()
    if bind.dialect.name == "sqlite":
        yield _memory_saver
        return

    connection_string = postgres_checkpoint_url(get_settings().database_url)
    with PostgresSaver.from_conn_string(connection_string) as saver:
        yield saver


def setup_postgres_checkpoints() -> None:
    connection_string = postgres_checkpoint_url(get_settings().database_url)
    with PostgresSaver.from_conn_string(connection_string) as saver:
        saver.setup()

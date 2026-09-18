import hashlib
import json
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from commerceflow.config import settings


def utcnow():
    return datetime.now(UTC)


def identifier():
    return str(uuid4())


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()


@lru_cache
def engine(commerce=False):
    url = settings().commerce_database_url if commerce else settings().database_url
    if not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("A dedicated PostgreSQL database URL is required")
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})


@contextmanager
def transaction(commerce=False):
    with Session(engine(commerce), expire_on_commit=False) as session, session.begin():
        yield session


def lock(session, key):
    session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key})


class DomainError(Exception):
    def __init__(self, code, message, status=409):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)

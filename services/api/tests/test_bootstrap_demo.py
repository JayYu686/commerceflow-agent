from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import Customer, PolicyDocument
from scripts.bootstrap_demo import bootstrap_demo_session


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    local_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with local_session() as test_session:
        yield test_session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_bootstrap_initializes_empty_demo_database(session: Session) -> None:
    summary = bootstrap_demo_session(session)

    assert summary.commerce_initialized is True
    assert summary.policies_initialized is True
    assert summary.commerce.orders == 300
    assert summary.policies.documents == 9
    assert summary.policies.chunks == 35


def test_bootstrap_preserves_complete_demo_database(session: Session) -> None:
    first = bootstrap_demo_session(session)
    second = bootstrap_demo_session(session)

    assert first.commerce == second.commerce
    assert first.policies == second.policies
    assert second.commerce_initialized is False
    assert second.policies_initialized is False


def test_bootstrap_refuses_partial_commerce_dataset(session: Session) -> None:
    session.add(Customer(id=1, name="Partial", tier="regular", risk_flag=False))
    session.commit()

    with pytest.raises(RuntimeError, match="partially initialized commerce"):
        bootstrap_demo_session(session)


def test_bootstrap_refuses_partial_policy_dataset(session: Session) -> None:
    session.add(
        PolicyDocument(
            policy_id="PARTIAL",
            title="Partial",
            version="v1",
            status="active",
            category="all",
            aftersales_type="all",
            intent="quality_issue_refund",
            effective_from=datetime(2026, 1, 1, tzinfo=UTC),
            source_path="partial.json",
            source_checksum="0" * 64,
        )
    )
    session.commit()

    with pytest.raises(RuntimeError, match="partially initialized policy"):
        bootstrap_demo_session(session)

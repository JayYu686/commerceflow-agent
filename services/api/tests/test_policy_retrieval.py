from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.services.policy_ingestion import ingest_policies
from app.services.policy_retrieval import search_policies

AS_OF = datetime(2026, 6, 6, tzinfo=UTC)


@pytest.fixture()
def policy_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as session:
        ingest_policies(session, reset=True)
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_quality_refund_retrieval_hits_current_electronics_policy(
    policy_session: Session,
) -> None:
    response = search_policies(
        policy_session,
        query="耳机 left speaker has no sound and customer wants return refund",
        intent="quality_issue_refund",
        category="electronics",
        aftersales_type="standard",
        as_of=AS_OF,
    )

    assert response.hits
    assert response.hits[0].policy_id == "POL-QUALITY-ELECTRONICS-V2"
    assert response.hits[0].chunk_id.startswith("POL-QUALITY-ELECTRONICS-V2#")
    assert response.hits[0].score >= 0.55
    assert all(hit.policy_id != "POL-QUALITY-ELECTRONICS-V1" for hit in response.hits)


def test_logistics_delay_retrieval_hits_current_delay_policy(policy_session: Session) -> None:
    response = search_policies(
        policy_session,
        query="物流 tracking has no movement for more than 72 hours and needs compensation",
        intent="logistics_delay_compensation",
        category="electronics",
        aftersales_type="standard",
        as_of=AS_OF,
    )

    assert response.hits
    assert response.hits[0].policy_id == "POL-LOGISTICS-DELAY-V1"
    assert all(hit.policy_id != "POL-LOGISTICS-DELAY-V0" for hit in response.hits)


def test_retrieval_filters_inactive_or_expired_policies(policy_session: Session) -> None:
    response = search_policies(
        policy_session,
        query="old electronics quality defect refund policy",
        intent="quality_issue_refund",
        category="electronics",
        aftersales_type="standard",
        as_of=AS_OF,
    )

    policy_ids = {hit.policy_id for hit in response.hits}
    assert "POL-QUALITY-ELECTRONICS-V2" in policy_ids
    assert "POL-QUALITY-ELECTRONICS-V1" not in policy_ids


def test_retrieval_filters_non_matching_category(policy_session: Session) -> None:
    response = search_policies(
        policy_session,
        query="electronics quality defect refund",
        intent="quality_issue_refund",
        category="fresh",
        aftersales_type="perishable",
        as_of=AS_OF,
    )

    assert response.hits == []


def test_retrieval_returns_empty_when_score_is_too_low(policy_session: Session) -> None:
    response = search_policies(
        policy_session,
        query="unrelated weather forecast request",
        intent="logistics_delay_compensation",
        category="electronics",
        aftersales_type="standard",
        as_of=AS_OF,
        min_score=0.99,
    )

    assert response.hits == []


def test_retrieval_rejects_invalid_inputs(policy_session: Session) -> None:
    with pytest.raises(ValueError, match="query"):
        search_policies(
            policy_session,
            query=" ",
            intent="quality_issue_refund",
            category="electronics",
            aftersales_type="standard",
            as_of=AS_OF,
        )

    with pytest.raises(ValueError, match="limit"):
        search_policies(
            policy_session,
            query="electronics quality defect refund",
            intent="quality_issue_refund",
            category="electronics",
            aftersales_type="standard",
            as_of=AS_OF,
            limit=11,
        )

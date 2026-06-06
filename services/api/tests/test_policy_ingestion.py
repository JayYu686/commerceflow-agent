import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import PolicyDocument
from app.services.policy_ingestion import (
    DEFAULT_POLICY_DIR,
    PolicyIngestionSummary,
    ingest_policies,
    load_policy_documents,
)


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
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_policy_json_documents_are_valid_and_cover_required_metadata() -> None:
    documents = load_policy_documents(DEFAULT_POLICY_DIR)
    policy_ids = {document.source.policy_id for document in documents}
    categories = {document.source.category for document in documents}
    aftersales_types = {document.source.aftersales_type for document in documents}
    statuses = {document.source.status for document in documents}
    chunk_count = sum(len(document.source.sections) for document in documents)

    assert chunk_count >= 30
    assert "POL-QUALITY-ELECTRONICS-V2" in policy_ids
    assert "POL-LOGISTICS-DELAY-V1" in policy_ids
    assert "deprecated" in statuses
    assert {"electronics", "apparel", "appliance", "fresh", "home"}.issubset(categories)
    assert {"standard", "special", "perishable", "final_sale"}.issubset(aftersales_types)


def test_policy_ingestion_reset_creates_stable_counts(policy_session: Session) -> None:
    first_summary = ingest_policies(policy_session, reset=True)
    second_summary = ingest_policies(policy_session, reset=True)

    assert first_summary == second_summary
    assert first_summary == PolicyIngestionSummary(documents=9, chunks=35)


def test_policy_ingestion_contains_fixed_demo_policies(policy_session: Session) -> None:
    ingest_policies(policy_session, reset=True)

    quality_policy = policy_session.scalar(
        select(PolicyDocument).where(PolicyDocument.policy_id == "POL-QUALITY-ELECTRONICS-V2")
    )
    delay_policy = policy_session.scalar(
        select(PolicyDocument).where(PolicyDocument.policy_id == "POL-LOGISTICS-DELAY-V1")
    )

    assert quality_policy is not None
    assert quality_policy.status == "active"
    assert quality_policy.category == "electronics"
    assert quality_policy.aftersales_type == "standard"
    assert len(quality_policy.chunks) == 5

    assert delay_policy is not None
    assert delay_policy.status == "active"
    assert delay_policy.category == "all"
    assert delay_policy.aftersales_type == "all"
    assert len(delay_policy.chunks) == 5


def test_policy_ingestion_without_reset_refuses_existing_data(policy_session: Session) -> None:
    ingest_policies(policy_session, reset=True)

    with pytest.raises(RuntimeError, match="--reset"):
        ingest_policies(policy_session, reset=False)

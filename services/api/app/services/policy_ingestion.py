import hashlib
import json
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import PolicyChunk, PolicyDocument
from app.schemas.policy import PolicyDocumentSource
from app.services.embeddings import (
    EMBEDDING_MODEL,
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_POLICY_DIR = REPO_ROOT / "data" / "policies" / "v1"


@dataclass(frozen=True)
class LoadedPolicyDocument:
    source: PolicyDocumentSource
    source_path: Path
    source_checksum: str


@dataclass(frozen=True)
class PolicyIngestionSummary:
    documents: int
    chunks: int


def load_policy_documents(policy_dir: Path = DEFAULT_POLICY_DIR) -> list[LoadedPolicyDocument]:
    if not policy_dir.exists():
        raise FileNotFoundError(f"Policy directory does not exist: {policy_dir}")

    loaded: list[LoadedPolicyDocument] = []
    seen_policy_ids: set[str] = set()
    for source_path in sorted(policy_dir.glob("*.json")):
        raw = source_path.read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        try:
            source = PolicyDocumentSource.model_validate(json.loads(raw.decode("utf-8")))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(f"Invalid policy document: {source_path}") from exc
        if source.policy_id in seen_policy_ids:
            raise ValueError(f"Duplicate policy_id: {source.policy_id}")
        seen_policy_ids.add(source.policy_id)
        loaded.append(
            LoadedPolicyDocument(
                source=source,
                source_path=source_path,
                source_checksum=checksum,
            )
        )
    return loaded


def reset_policy_tables(session: Session) -> None:
    session.execute(delete(PolicyChunk))
    session.execute(delete(PolicyDocument))
    session.flush()


def count_policy_rows(session: Session) -> PolicyIngestionSummary:
    return PolicyIngestionSummary(
        documents=session.scalar(select(func.count()).select_from(PolicyDocument)) or 0,
        chunks=session.scalar(select(func.count()).select_from(PolicyChunk)) or 0,
    )


def ingest_policies(
    session: Session,
    *,
    policy_dir: Path = DEFAULT_POLICY_DIR,
    reset: bool = False,
    embedding_provider: EmbeddingProvider | None = None,
) -> PolicyIngestionSummary:
    existing_documents = session.scalar(select(func.count()).select_from(PolicyDocument)) or 0
    if existing_documents and not reset:
        raise RuntimeError(
            "Policy data already exists. Re-run with --reset to clear and rebuild it."
        )
    if reset:
        reset_policy_tables(session)

    provider = embedding_provider or DeterministicEmbeddingProvider()
    loaded_documents = load_policy_documents(policy_dir)
    for loaded in loaded_documents:
        source = loaded.source
        document = PolicyDocument(
            policy_id=source.policy_id,
            title=source.title,
            version=source.version,
            status=source.status,
            category=source.category,
            aftersales_type=source.aftersales_type,
            intent=source.intent,
            effective_from=source.effective_from.astimezone(UTC),
            effective_to=source.effective_to.astimezone(UTC) if source.effective_to else None,
            source_path=str(loaded.source_path.relative_to(REPO_ROOT)),
            source_checksum=loaded.source_checksum,
        )
        session.add(document)
        session.flush()

        chunk_texts = [embedding_text(source, section.content) for section in source.sections]
        embeddings = provider.embed(chunk_texts)
        for sequence, (section, embedding) in enumerate(
            zip(source.sections, embeddings, strict=True),
            start=1,
        ):
            chunk = PolicyChunk(
                document_id=document.id,
                chunk_id=f"{source.policy_id}#{sequence:03d}",
                section=section.section,
                sequence=sequence,
                content=section.content,
                content_hash=hashlib.sha256(section.content.encode("utf-8")).hexdigest(),
                embedding=embedding,
                embedding_model=EMBEDDING_MODEL,
                metadata_json=metadata_for(source, section.section),
            )
            session.add(chunk)

    session.commit()
    return count_policy_rows(session)


def embedding_text(source: PolicyDocumentSource, content: str) -> str:
    return " ".join(
        [
            source.policy_id,
            source.title,
            source.category,
            source.aftersales_type,
            source.intent,
            content,
        ]
    )


def metadata_for(source: PolicyDocumentSource, section: str) -> dict[str, Any]:
    return {
        "policy_id": source.policy_id,
        "version": source.version,
        "status": source.status,
        "category": source.category,
        "aftersales_type": source.aftersales_type,
        "intent": source.intent,
        "section": section,
    }

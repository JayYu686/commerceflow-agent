from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.repositories.policy import search_policy_chunks
from app.schemas.policy import PolicySearchHit, PolicySearchResponse
from app.services.embeddings import DeterministicEmbeddingProvider, EmbeddingProvider

DEFAULT_MIN_SCORE = 0.55
DEFAULT_LIMIT = 5
MAX_LIMIT = 10


def search_policies(
    session: Session,
    *,
    query: str,
    intent: str,
    category: str,
    aftersales_type: str,
    as_of: datetime | None = None,
    limit: int = DEFAULT_LIMIT,
    min_score: float = DEFAULT_MIN_SCORE,
    embedding_provider: EmbeddingProvider | None = None,
) -> PolicySearchResponse:
    if not query.strip():
        raise ValueError("query must not be empty")
    if limit < 1 or limit > MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")

    effective_as_of = as_of or datetime.now(UTC)
    if effective_as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")

    provider = embedding_provider or DeterministicEmbeddingProvider()
    query_embedding = provider.embed([query])[0]
    scored_chunks = search_policy_chunks(
        session,
        query_embedding=query_embedding,
        intent=intent,
        category=category,
        aftersales_type=aftersales_type,
        as_of=effective_as_of,
        limit=limit * 4,
    )
    hits = [chunk_to_hit(chunk, score) for chunk, score in scored_chunks if score >= min_score][
        :limit
    ]
    return PolicySearchResponse(query=query, hits=hits)


def chunk_to_hit(chunk, score: float) -> PolicySearchHit:
    document = chunk.document
    return PolicySearchHit(
        policy_id=document.policy_id,
        chunk_id=chunk.chunk_id,
        title=document.title,
        section=chunk.section,
        version=document.version,
        category=document.category,
        aftersales_type=document.aftersales_type,
        intent=document.intent,
        effective_from=document.effective_from,
        effective_to=document.effective_to,
        score=round(score, 4),
        content_excerpt=excerpt(chunk.content),
    )


def excerpt(content: str, max_length: int = 220) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 3]}..."

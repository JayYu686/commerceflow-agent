import math
from datetime import datetime
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import PolicyChunk, PolicyDocument


def build_active_policy_filters(
    *,
    intent: str,
    category: str,
    aftersales_type: str,
    as_of: datetime,
) -> list[Any]:
    return [
        PolicyDocument.status == "active",
        PolicyDocument.intent == intent,
        PolicyDocument.effective_from <= as_of,
        or_(PolicyDocument.effective_to.is_(None), PolicyDocument.effective_to > as_of),
        PolicyDocument.category.in_([category, "all"]),
        PolicyDocument.aftersales_type.in_([aftersales_type, "all"]),
    ]


def search_policy_chunks(
    session: Session,
    *,
    query_embedding: list[float],
    intent: str,
    category: str,
    aftersales_type: str,
    as_of: datetime,
    limit: int,
) -> list[tuple[PolicyChunk, float]]:
    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        return search_policy_chunks_with_pgvector(
            session,
            query_embedding=query_embedding,
            intent=intent,
            category=category,
            aftersales_type=aftersales_type,
            as_of=as_of,
            limit=limit,
        )
    return search_policy_chunks_in_python(
        session,
        query_embedding=query_embedding,
        intent=intent,
        category=category,
        aftersales_type=aftersales_type,
        as_of=as_of,
        limit=limit,
    )


def search_policy_chunks_with_pgvector(
    session: Session,
    *,
    query_embedding: list[float],
    intent: str,
    category: str,
    aftersales_type: str,
    as_of: datetime,
    limit: int,
) -> list[tuple[PolicyChunk, float]]:
    distance = PolicyChunk.embedding.cosine_distance(query_embedding)
    statement = (
        select(PolicyChunk, distance.label("distance"))
        .join(PolicyChunk.document)
        .where(
            *build_active_policy_filters(
                intent=intent,
                category=category,
                aftersales_type=aftersales_type,
                as_of=as_of,
            )
        )
        .options(selectinload(PolicyChunk.document))
        .order_by(distance.asc(), PolicyChunk.sequence.asc())
        .limit(limit)
    )
    rows = session.execute(statement).all()
    return [(chunk, 1.0 - float(distance_value)) for chunk, distance_value in rows]


def search_policy_chunks_in_python(
    session: Session,
    *,
    query_embedding: list[float],
    intent: str,
    category: str,
    aftersales_type: str,
    as_of: datetime,
    limit: int,
) -> list[tuple[PolicyChunk, float]]:
    statement: Select[tuple[PolicyChunk]] = (
        select(PolicyChunk)
        .join(PolicyChunk.document)
        .where(
            *build_active_policy_filters(
                intent=intent,
                category=category,
                aftersales_type=aftersales_type,
                as_of=as_of,
            )
        )
        .options(selectinload(PolicyChunk.document))
    )
    scored = [
        (chunk, cosine_similarity(query_embedding, embedding_to_list(chunk.embedding)))
        for chunk in session.scalars(statement).all()
    ]
    return sorted(scored, key=lambda item: (-item[1], item[0].sequence))[:limit]


def embedding_to_list(value: Any) -> list[float]:
    if isinstance(value, str):
        return [float(part) for part in value.strip("[]").split(",") if part.strip()]
    if hasattr(value, "tolist"):
        return [float(part) for part in value.tolist()]
    return [float(part) for part in value]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = sum(
        left_value * right_value for left_value, right_value in zip(left, right, strict=False)
    )
    return dot / (left_norm * right_norm)

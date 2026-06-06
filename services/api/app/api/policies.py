from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.policy import PolicySearchResponse
from app.services.policy_retrieval import (
    DEFAULT_LIMIT,
    DEFAULT_MIN_SCORE,
    MAX_LIMIT,
    search_policies,
)

router = APIRouter(prefix="/api/policies", tags=["policies"])


@router.get("/search", response_model=PolicySearchResponse)
def search_policy_documents(
    query: Annotated[str, Query(min_length=1)],
    intent: Annotated[str | None, Query(min_length=1)] = None,
    category: Annotated[str | None, Query(min_length=1)] = None,
    aftersales_type: Annotated[str | None, Query(min_length=1)] = None,
    as_of: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    min_score: Annotated[float, Query(ge=0, le=1)] = DEFAULT_MIN_SCORE,
    session: Session = Depends(get_session),
) -> PolicySearchResponse:
    if not query.strip():
        raise validation_error("query must not be empty")
    if as_of is not None and as_of.tzinfo is None:
        raise validation_error("as_of must be timezone-aware")

    try:
        return search_policies(
            session,
            query=query,
            intent=intent,
            category=category,
            aftersales_type=aftersales_type,
            as_of=as_of,
            limit=limit,
            min_score=min_score,
        )
    except ValueError as exc:
        raise validation_error(str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "policy_search_failed",
                "message": "policy search failed",
            },
        ) from exc


def validation_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail=[
            {
                "type": "value_error",
                "loc": ["query"],
                "msg": message,
                "input": None,
            }
        ],
    )

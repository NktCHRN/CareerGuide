"""Recommendations: ranked list, score lookup and readiness status (FR10, FR9).

Every endpoint is scoped to the authenticated caller and ranks the shared
`profession_vectors` against the caller's `user_vectors[user_id]` by cosine
similarity (pgvector). This service only READS `recommendationdb`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.deps import Principal, get_current_user
from app.schemas import (
    Page,
    RecommendationItem,
    ScoresOut,
    ScoresRequest,
    StatusOut,
)
from app.services import cache
from app.services.recommendations import (
    ORDER_OPTIONS,
    SORT_OPTIONS,
    get_user_vector,
    get_user_vector_status,
    rank_professions,
    score_professions,
)

router = APIRouter(prefix="/api", tags=["recommendations"])


# --------------------------------------------------------------------------- #
#  Readiness status (FR10) — has the worker computed the user's vector yet?
# --------------------------------------------------------------------------- #
@router.get("/recommendations/status", response_model=StatusOut)
async def recommendations_status(
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StatusOut:
    ready, updated_at = await get_user_vector_status(session, principal.user_id)
    return StatusOut(ready=ready, updated_at=updated_at)


# --------------------------------------------------------------------------- #
#  Ranked list (FR10)
# --------------------------------------------------------------------------- #
@router.get("/recommendations", response_model=Page[RecommendationItem])
async def list_recommendations(
    sort: str = Query(default="score", description=f"one of {', '.join(SORT_OPTIONS)}"),
    order: str = Query(default="desc", description="desc | asc"),
    education_level: str | None = Query(default=None),
    min_vacancies: int | None = Query(default=None, ge=0),
    min_avg_salary: float | None = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Page[RecommendationItem]:
    sort = sort if sort in SORT_OPTIONS else "score"
    order = order.lower() if order.lower() in ORDER_OPTIONS else "desc"

    # No user vector yet → an empty page (the frontend uses /status to warn).
    user_vec = await get_user_vector(session, principal.user_id)
    if user_vec is None:
        return Page[RecommendationItem](items=[], page=page, page_size=page_size, total=0)

    filters = {
        "sort": sort,
        "order": order,
        "education_level": education_level,
        "min_vacancies": min_vacancies,
        "min_avg_salary": min_avg_salary,
        "page_size": page_size,
    }

    # Cache only the first page (the hot path); deeper pages hit the DB directly.
    cache_key = cache.list_key(principal.user_id, filters) if page == 1 else None
    if cache_key is not None:
        cached = await cache.get_json(cache_key)
        if cached is not None:
            return Page[RecommendationItem].model_validate(cached)

    items, total = await rank_professions(
        session,
        user_vec,
        sort=sort,
        order=order,
        education_level=education_level,
        min_vacancies=min_vacancies,
        min_avg_salary=min_avg_salary,
        page=page,
        page_size=page_size,
    )
    result = Page[RecommendationItem](
        items=[RecommendationItem(**it) for it in items],
        page=page,
        page_size=page_size,
        total=total,
    )

    if cache_key is not None:
        await cache.set_json(
            cache_key, result.model_dump(mode="json"), settings.RECO_CACHE_TTL_SECONDS
        )
    return result


# --------------------------------------------------------------------------- #
#  Score specific professions (FR9 — boost recommended results in search)
# --------------------------------------------------------------------------- #
@router.post("/recommendations/scores", response_model=ScoresOut)
async def score_recommendations(
    payload: ScoresRequest,
    principal: Principal = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ScoresOut:
    user_vec = await get_user_vector(session, principal.user_id)
    if user_vec is None:
        return ScoresOut(ready=False, scores={})

    # De-duplicate and cap the request size.
    ids = list(dict.fromkeys(payload.profession_ids))[: settings.MAX_SCORE_IDS]
    scores = await score_professions(session, user_vec, ids)
    return ScoresOut(ready=True, scores=scores)

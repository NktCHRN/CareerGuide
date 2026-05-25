"""Cosine ranking/scoring over `recommendationdb` (pgvector) — read-only.

All scoring is relative to the caller's stored `user_vectors[user_id]`:
  • the cosine SCORE is `1 - (profession.vector <=> user.vector)` — i.e. the
    cosine similarity of the L2-normalized vectors, clamped to [0, 1];
  • ranking by score orders by the cosine DISTANCE ascending, which lets pgvector
    use the HNSW index built by the worker;
  • sorting by vacancies/salary uses the plain denormalized columns (no vector
    index then — acceptable for the prototype).

The worker denormalizes `preferred_label / education_level / avg_salary /
vacancies_*` into `profession_vectors`, so filtering and sorting need no call to
career-service.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ColumnElement, func, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProfessionVector, UserVector

# Columns the API may sort on, besides the cosine "score".
_SORT_COLUMNS: dict[str, ColumnElement] = {
    "vacancies_local": ProfessionVector.vacancies_local,
    "vacancies_international": ProfessionVector.vacancies_international,
    "avg_salary": ProfessionVector.avg_salary,
}
SORT_OPTIONS = ("score", *_SORT_COLUMNS.keys())
ORDER_OPTIONS = ("desc", "asc")


def _clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else value


# --------------------------------------------------------------------------- #
#  User vector lookups
# --------------------------------------------------------------------------- #
async def get_user_vector(session: AsyncSession, user_id: int):
    """The user's stored 768-d vector (numpy array) or None if not computed yet."""
    res = await session.execute(
        select(UserVector.vector).where(UserVector.user_id == user_id)
    )
    return res.scalar_one_or_none()


async def get_user_vector_status(
    session: AsyncSession, user_id: int
) -> tuple[bool, datetime | None]:
    """(ready, updated_at): ready is True once the worker has stored the vector."""
    res = await session.execute(
        select(UserVector.updated_at).where(UserVector.user_id == user_id)
    )
    updated_at = res.scalar_one_or_none()
    return updated_at is not None, updated_at


# --------------------------------------------------------------------------- #
#  Filtering
# --------------------------------------------------------------------------- #
def _apply_filters(
    stmt,
    *,
    education_level: str | None,
    min_vacancies: int | None,
    min_avg_salary: float | None,
):
    if education_level:
        stmt = stmt.where(
            func.lower(ProfessionVector.education_level) == education_level.strip().lower()
        )
    if min_vacancies is not None:
        # "min_vacancies" filters on the LOCAL job market (rows with NULL are dropped).
        stmt = stmt.where(ProfessionVector.vacancies_local >= min_vacancies)
    if min_avg_salary is not None:
        stmt = stmt.where(ProfessionVector.avg_salary >= min_avg_salary)
    return stmt


# --------------------------------------------------------------------------- #
#  Ranking (GET /recommendations)
# --------------------------------------------------------------------------- #
async def rank_professions(
    session: AsyncSession,
    user_vec,
    *,
    sort: str,
    order: str,
    education_level: str | None,
    min_vacancies: int | None,
    min_avg_salary: float | None,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    """Returns (items, total) for one page of the filtered/sorted ranking."""
    distance = ProfessionVector.vector.cosine_distance(user_vec)
    score = (1 - distance).label("score")
    descending = order.lower() != "asc"

    filter_kw = dict(
        education_level=education_level,
        min_vacancies=min_vacancies,
        min_avg_salary=min_avg_salary,
    )

    total = (
        await session.execute(
            _apply_filters(
                select(func.count()).select_from(ProfessionVector), **filter_kw
            )
        )
    ).scalar_one()

    stmt = _apply_filters(
        select(
            ProfessionVector.profession_id,
            ProfessionVector.preferred_label,
            ProfessionVector.education_level,
            ProfessionVector.avg_salary,
            ProfessionVector.vacancies_local,
            ProfessionVector.vacancies_international,
            score,
        ),
        **filter_kw,
    )

    if sort == "score":
        # Order by the cosine DISTANCE so the worker's HNSW index can be used.
        stmt = stmt.order_by(distance.asc() if descending else distance.desc())
    else:
        col = _SORT_COLUMNS[sort]
        primary = col.desc() if descending else col.asc()
        # NULLs always last; ties broken by best score (distance ascending).
        stmt = stmt.order_by(nulls_last(primary), distance.asc())

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(stmt)).all()

    items = [
        {
            "profession_id": int(r.profession_id),
            "score": _clamp01(float(r.score)),
            "preferred_label": r.preferred_label,
            "education_level": r.education_level,
            "avg_salary": float(r.avg_salary) if r.avg_salary is not None else None,
            "vacancies_local": r.vacancies_local,
            "vacancies_international": r.vacancies_international,
        }
        for r in rows
    ]
    return items, total


# --------------------------------------------------------------------------- #
#  Scoring specific professions (POST /recommendations/scores)
# --------------------------------------------------------------------------- #
async def score_professions(
    session: AsyncSession, user_vec, profession_ids: list[int]
) -> dict[int, float]:
    """Map of profession_id → cosine score for the given ids (missing ids omitted)."""
    if not profession_ids:
        return {}
    distance = ProfessionVector.vector.cosine_distance(user_vec)
    stmt = select(
        ProfessionVector.profession_id,
        (1 - distance).label("score"),
    ).where(ProfessionVector.profession_id.in_(profession_ids))
    rows = (await session.execute(stmt)).all()
    return {int(r.profession_id): _clamp01(float(r.score)) for r in rows}

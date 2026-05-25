"""Idempotent upserts/deletes of the pgvector tables (`recommendationdb`)."""
from __future__ import annotations

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProfessionVector, UserVector

_PROFESSION_UPDATE_COLS = (
    "esco_uri",
    "vector",
    "preferred_label",
    "education_level",
    "avg_salary",
    "vacancies_local",
    "vacancies_international",
)


async def upsert_profession_vectors(session: AsyncSession, rows: list[dict]) -> None:
    """Batch upsert by `profession_id` (idempotent).

    Rows are deduplicated by `profession_id` (last wins) — a single INSERT may not
    touch the same conflict target twice.
    """
    if not rows:
        return
    deduped = {row["profession_id"]: row for row in rows}
    stmt = pg_insert(ProfessionVector).values(list(deduped.values()))
    update_cols = {c: getattr(stmt.excluded, c) for c in _PROFESSION_UPDATE_COLS}
    update_cols["updated_at"] = func.now()
    stmt = stmt.on_conflict_do_update(
        index_elements=[ProfessionVector.profession_id],
        set_=update_cols,
    )
    await session.execute(stmt)


async def delete_profession_vector(session: AsyncSession, profession_id: int) -> None:
    await session.execute(
        delete(ProfessionVector).where(ProfessionVector.profession_id == profession_id)
    )


async def upsert_user_vector(session: AsyncSession, user_id: int, vector: list[float]) -> None:
    stmt = pg_insert(UserVector).values(user_id=user_id, vector=vector)
    stmt = stmt.on_conflict_do_update(
        index_elements=[UserVector.user_id],
        set_={"vector": stmt.excluded.vector, "updated_at": func.now()},
    )
    await session.execute(stmt)


async def delete_user_vector(session: AsyncSession, user_id: int) -> None:
    await session.execute(delete(UserVector).where(UserVector.user_id == user_id))

"""Idempotent upserts/deletes of the local denormalised copies (`chatdb`).

These rows are driven entirely by the Kafka bus, so every operation is an upsert
by primary key (replay-safe). On `user.deleted` we also drop the user's chats —
the conversation owner no longer exists.
"""
from __future__ import annotations

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CachedProfession, CachedUser, Chat


# --------------------------------------------------------------------------- #
#  cached_professions (profession-events)
# --------------------------------------------------------------------------- #
def profession_row(value: dict) -> dict | None:
    prof = value.get("profession") or {}
    pid = value.get("profession_id", prof.get("id"))
    if pid is None:
        return None
    labels = prof.get("knowledge_skill_labels") or []
    return {
        "profession_id": int(pid),
        "esco_uri": prof.get("esco_uri"),
        "preferred_label": prof.get("preferred_label"),
        "description": prof.get("description"),
        "knowledge_skill_labels": [str(x) for x in labels if x],
        "education_level": prof.get("education_level"),
    }


_PROFESSION_UPDATE_COLS = (
    "esco_uri",
    "preferred_label",
    "description",
    "knowledge_skill_labels",
    "education_level",
)


async def upsert_profession(session: AsyncSession, row: dict) -> None:
    stmt = pg_insert(CachedProfession).values(**row)
    update_cols = {c: getattr(stmt.excluded, c) for c in _PROFESSION_UPDATE_COLS}
    update_cols["updated_at"] = func.now()
    stmt = stmt.on_conflict_do_update(
        index_elements=[CachedProfession.profession_id],
        set_=update_cols,
    )
    await session.execute(stmt)


async def delete_profession(session: AsyncSession, profession_id: int) -> None:
    await session.execute(
        delete(CachedProfession).where(CachedProfession.profession_id == profession_id)
    )


# --------------------------------------------------------------------------- #
#  cached_users (user-events)
# --------------------------------------------------------------------------- #
def user_row(user_id: int, profile: dict) -> dict:
    skills = profile.get("skills") or []
    experiences = profile.get("experiences") or []
    return {
        "user_id": user_id,
        # user.profile.updated does not carry `name`; kept best-effort for forward compat.
        "name": profile.get("name"),
        "summary": profile.get("summary"),
        "skills": [str(s) for s in skills if s],
        "experiences": [e for e in experiences if isinstance(e, dict)],
    }


_USER_UPDATE_COLS = ("name", "summary", "skills", "experiences")


async def upsert_user(session: AsyncSession, row: dict) -> None:
    stmt = pg_insert(CachedUser).values(**row)
    update_cols = {c: getattr(stmt.excluded, c) for c in _USER_UPDATE_COLS}
    update_cols["updated_at"] = func.now()
    stmt = stmt.on_conflict_do_update(
        index_elements=[CachedUser.user_id],
        set_=update_cols,
    )
    await session.execute(stmt)


async def delete_user(session: AsyncSession, user_id: int) -> None:
    """Drop the cached profile AND the user's chats (cascade removes messages)."""
    await session.execute(delete(CachedUser).where(CachedUser.user_id == user_id))
    await session.execute(delete(Chat).where(Chat.user_id == user_id))

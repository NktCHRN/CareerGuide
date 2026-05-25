"""Helpers for publishing events from the router (after the transaction commit)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.events import schemas as ev
from app.events.producer import producer
from app.services.professions import build_upsert_payload, load_knowledge_skills, load_profession


async def publish_profession_upserted(session: AsyncSession, profession_id: int) -> None:
    """Re-reads the profession (+ knowledge skills) and publishes `profession.upserted`."""
    profession = await load_profession(session, profession_id)
    if profession is None:
        return
    knowledge_skills = await load_knowledge_skills(session, profession_id)
    payload = build_upsert_payload(profession, knowledge_skills)
    await producer.send(
        ev.TOPIC_PROFESSION_EVENTS,
        ev.profession_upserted_event(profession_id, payload),
        key=profession_id,
    )


async def publish_profession_deleted(profession_id: int) -> None:
    await producer.send(
        ev.TOPIC_PROFESSION_EVENTS,
        ev.profession_deleted_event(profession_id),
        key=profession_id,
    )

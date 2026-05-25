"""Backfill: publishes `profession.upserted` for every profession.

Run once after the first `alembic upgrade head` (which seeds ESCO), so the
worker and chat-service receive the full catalogue over the bus and never read
the ESCO CSVs themselves. The payload carries both `knowledge_skill_uris` and
`knowledge_skill_labels`.

    python -m app.events.backfill_professions
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from sqlalchemy import select

from app.db import SessionFactory, engine
from app.events import schemas as ev
from app.events.producer import producer
from app.models import Profession, ProfessionSkill, Skill
from app.services.professions import build_upsert_payload

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("career-service.backfill")

# Essential before optional in the published lists.
_RELATION_RANK = {"essential": 0, "optional": 1}


async def main() -> None:
    await producer.start()
    sent = 0
    try:
        async with SessionFactory() as session:
            # All knowledge skills in one query → {profession_id: [(uri, label, relation_type), ...]}.
            skills_by_profession: dict[int, list[tuple[str, str, str]]] = defaultdict(list)
            skill_rows = await session.execute(
                select(
                    ProfessionSkill.profession_id,
                    ProfessionSkill.skill_uri,
                    Skill.label,
                    ProfessionSkill.relation_type,
                ).join(Skill, Skill.skill_uri == ProfessionSkill.skill_uri)
            )
            for pid, uri, label, rel in skill_rows.all():
                skills_by_profession[pid].append((uri, label, rel))
            for items in skills_by_profession.values():
                items.sort(key=lambda t: (_RELATION_RANK.get(t[2], 9), t[1].lower()))

            result = await session.execute(select(Profession).order_by(Profession.id.asc()))
            for profession in result.scalars().all():
                knowledge_skills = skills_by_profession.get(profession.id, [])
                payload = build_upsert_payload(profession, knowledge_skills)
                await producer.send(
                    ev.TOPIC_PROFESSION_EVENTS,
                    ev.profession_upserted_event(profession.id, payload),
                    key=profession.id,
                )
                sent += 1
                if sent % 500 == 0:
                    logger.info("… published %d events", sent)
    finally:
        await producer.stop()
        await engine.dispose()
    logger.info("Backfill finished: published %d profession.upserted events", sent)


if __name__ == "__main__":
    asyncio.run(main())

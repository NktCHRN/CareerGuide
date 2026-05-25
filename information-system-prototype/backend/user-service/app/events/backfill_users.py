"""Backfill: публікує `user.profile.updated` для всіх профілів.

Запускати після першого підняття системи, щоб worker порахував вектори й
змапив навички для вже наявних користувачів (зокрема сіду).

    python -m app.events.backfill_users
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import SessionFactory, engine
from app.events import schemas as ev
from app.events.producer import producer
from app.models import Profile
from app.services.profiles import build_profile_event_payload

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("user-service.backfill")


async def main() -> None:
    await producer.start()
    sent = 0
    try:
        async with SessionFactory() as session:
            result = await session.execute(
                select(Profile).options(selectinload(Profile.experiences))
            )
            profiles = result.scalars().all()
            for profile in profiles:
                payload = build_profile_event_payload(profile)
                await producer.send(
                    ev.TOPIC_USER_EVENTS,
                    ev.profile_updated_event(profile.user_id, payload),
                    key=profile.user_id,
                )
                sent += 1
    finally:
        await producer.stop()
        await engine.dispose()
    logger.info("Backfill завершено: опубліковано %d подій user.profile.updated", sent)


if __name__ == "__main__":
    asyncio.run(main())

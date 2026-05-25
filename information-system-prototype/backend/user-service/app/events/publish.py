"""Хелпери публікації подій із роутерів (після коміту транзакції)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.events import schemas as ev
from app.events.producer import producer
from app.services.profiles import build_profile_event_payload, load_full_profile


async def publish_profile_updated(session: AsyncSession, user_id: int) -> None:
    """Перечитує профіль і публікує `user.profile.updated` у топік user-events."""
    profile = await load_full_profile(session, user_id)
    if profile is None:
        return
    payload = build_profile_event_payload(profile)
    await producer.send(
        ev.TOPIC_USER_EVENTS,
        ev.profile_updated_event(user_id, payload),
        key=user_id,
    )


async def publish_resume_uploaded(user_id: int, s3_key: str) -> None:
    await producer.send(
        ev.TOPIC_USER_EVENTS,
        ev.resume_uploaded_event(user_id, s3_key),
        key=user_id,
    )


async def publish_user_deleted(user_id: int) -> None:
    await producer.send(
        ev.TOPIC_USER_EVENTS,
        ev.user_deleted_event(user_id),
        key=user_id,
    )

"""Kafka consumers (aiokafka). Two independent consumer groups, one per topic.

profession-events (group `chat-prof`):
    profession.upserted → upsert cached_professions (knowledge_skill_labels are
                          taken straight from the payload — no ESCO CSV);
    profession.deleted  → delete the local copy.

user-events (group `chat-user`):
    user.profile.updated → upsert cached_users (summary / skills / experiences);
    user.resume.uploaded → ignored (it is the worker's job);
    user.deleted         → delete the cached profile and the user's chats.

Processing is idempotent (upsert by primary key) and tolerant of a single poison
message. On first run both consumers use auto_offset_reset="earliest" so a
backfill replay from career-service / user-service is picked up.
"""
from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from app.config import settings
from app.db import SessionFactory
from app.events import schemas as ev
from app.services import local_copies as copies

logger = logging.getLogger("chat-service.consumer")


async def _start_with_retry(consumer: AIOKafkaConsumer, label: str) -> bool:
    for attempt in range(1, 11):
        try:
            await consumer.start()
            return True
        except Exception:  # noqa: BLE001
            logger.warning("%s consumer: start attempt %d failed, retrying in 3s", label, attempt)
            await asyncio.sleep(3)
    logger.error("%s consumer: could not connect to Kafka — consumption disabled", label)
    return False


# ---------------------------------------------------------------------------
# profession-events
# ---------------------------------------------------------------------------
async def _handle_profession_event(value: dict) -> None:
    event = value.get("event")
    if event == ev.EVENT_PROFESSION_UPSERTED:
        row = copies.profession_row(value)
        if row is None:
            logger.warning("profession.upserted without an id — skipped")
            return
        async with SessionFactory() as session:
            await copies.upsert_profession(session, row)
            await session.commit()
        logger.info("cached_professions upserted: profession_id=%s", row["profession_id"])
    elif event == ev.EVENT_PROFESSION_DELETED:
        pid = value.get("profession_id")
        if pid is None:
            return
        async with SessionFactory() as session:
            await copies.delete_profession(session, int(pid))
            await session.commit()
        logger.info("cached_professions deleted: profession_id=%s", pid)
    else:
        logger.debug("profession-events: ignoring event %r", event)


async def run_profession_consumer() -> None:
    consumer = AIOKafkaConsumer(
        ev.TOPIC_PROFESSION_EVENTS,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_GROUP_PROFESSIONS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
    if not await _start_with_retry(consumer, "profession"):
        return
    logger.info("Consumer started: topic=%s group=%s", ev.TOPIC_PROFESSION_EVENTS, settings.KAFKA_GROUP_PROFESSIONS)
    try:
        async for msg in consumer:
            try:
                await _handle_profession_event(msg.value)
            except Exception:  # noqa: BLE001 — a single poison message must not kill the consumer
                logger.exception("Error handling profession event")
    except asyncio.CancelledError:
        logger.info("profession consumer stopping…")
        raise
    finally:
        await consumer.stop()
        logger.info("profession consumer stopped")


# ---------------------------------------------------------------------------
# user-events
# ---------------------------------------------------------------------------
async def _handle_user_event(value: dict) -> None:
    event = value.get("event")
    raw_user_id = value.get("user_id")
    if raw_user_id is None:
        logger.warning("user-events: event %s without user_id", event)
        return
    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError):
        logger.warning("user-events: invalid user_id %r in %s", raw_user_id, event)
        return

    if event == ev.EVENT_PROFILE_UPDATED:
        row = copies.user_row(user_id, value.get("profile") or {})
        async with SessionFactory() as session:
            await copies.upsert_user(session, row)
            await session.commit()
        logger.info("cached_users upserted: user_id=%s", user_id)
    elif event == ev.EVENT_USER_DELETED:
        async with SessionFactory() as session:
            await copies.delete_user(session, user_id)
            await session.commit()
        logger.info("cached_users + chats deleted: user_id=%s", user_id)
    else:
        # user.resume.uploaded and anything else is not our concern.
        logger.debug("user-events: ignoring event %r", event)


async def run_user_consumer() -> None:
    consumer = AIOKafkaConsumer(
        ev.TOPIC_USER_EVENTS,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_GROUP_USERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
    if not await _start_with_retry(consumer, "user"):
        return
    logger.info("Consumer started: topic=%s group=%s", ev.TOPIC_USER_EVENTS, settings.KAFKA_GROUP_USERS)
    try:
        async for msg in consumer:
            try:
                await _handle_user_event(msg.value)
            except Exception:  # noqa: BLE001 — a single poison message must not kill the consumer
                logger.exception("Error handling user event")
    except asyncio.CancelledError:
        logger.info("user consumer stopping…")
        raise
    finally:
        await consumer.stop()
        logger.info("user consumer stopped")

"""Kafka-консюмер топіка `resume-results` (зворотний канал worker → user-service).

Дві події:
  • user.profile.parsed   — мердж розпарсеного резюме у профіль, збереження й
                            публікація user.profile.updated (запускає у worker
                            обчислення вектора та мапінг навичок);
  • user.esco_skills.mapped — збереження змапованих ESCO-навичок у поле
                            esco_skills; user.profile.updated НЕ публікується
                            (інакше — нескінченний цикл).

Consumer-група `user-resume-results`. Обробка ідемпотентна.
"""
from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import SessionFactory
from app.events import schemas as ev
from app.events.producer import producer
from app.models import EscoSkill, Profile
from app.services import cache
from app.services.profiles import build_profile_event_payload, merge_parsed_profile

logger = logging.getLogger("user-service.consumer")

CONSUMER_GROUP = "user-resume-results"


async def _load_profile(session, user_id: int) -> Profile | None:
    result = await session.execute(
        select(Profile)
        .where(Profile.user_id == user_id)
        .options(selectinload(Profile.experiences), selectinload(Profile.esco_skills))
    )
    return result.scalar_one_or_none()


async def _handle_profile_parsed(user_id: int, parsed: dict) -> None:
    async with SessionFactory() as session:
        profile = await _load_profile(session, user_id)
        if profile is None:
            logger.warning("profile.parsed: профіль user_id=%s не знайдено — пропуск", user_id)
            return
        merge_parsed_profile(profile, parsed or {})
        payload = build_profile_event_payload(profile)
        await session.commit()

    await cache.delete(cache.profile_key(user_id))
    # Після мерджу — анонсуємо оновлення профілю (вектор + мапінг навичок у worker).
    await producer.send(ev.TOPIC_USER_EVENTS, ev.profile_updated_event(user_id, payload), key=user_id)
    logger.info("profile.parsed застосовано для user_id=%s", user_id)


async def _handle_esco_mapped(user_id: int, esco_skills: list[dict]) -> None:
    async with SessionFactory() as session:
        profile = await _load_profile(session, user_id)
        if profile is None:
            logger.warning("esco_skills.mapped: профіль user_id=%s не знайдено — пропуск", user_id)
            return
        # Ідемпотентно: повна заміна набору змапованих навичок.
        await session.execute(delete(EscoSkill).where(EscoSkill.user_id == user_id))
        for item in esco_skills or []:
            uri = (item.get("skill_uri") or "").strip()
            label = (item.get("label") or "").strip()
            if uri and label:
                session.add(EscoSkill(user_id=user_id, skill_uri=uri, label=label))
        await session.commit()

    await cache.delete(cache.profile_key(user_id))
    # НЕ публікуємо user.profile.updated (щоб не зациклити мапінг).
    logger.info("esco_skills.mapped застосовано для user_id=%s (%d навичок)", user_id, len(esco_skills or []))


async def _handle(value: dict) -> None:
    event = value.get("event")
    user_id = value.get("user_id")
    if user_id is None:
        logger.warning("Подія без user_id: %s", event)
        return
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        logger.warning("Некоректний user_id у події %s: %r", event, user_id)
        return

    if event == ev.EVENT_PROFILE_PARSED:
        await _handle_profile_parsed(user_id, value.get("profile") or {})
    elif event == ev.EVENT_ESCO_SKILLS_MAPPED:
        await _handle_esco_mapped(user_id, value.get("esco_skills") or [])
    else:
        logger.debug("Пропуск події %r у %s", event, ev.TOPIC_RESUME_RESULTS)


async def run_consumer() -> None:
    """Фонова задача: споживає resume-results до скасування."""
    consumer = AIOKafkaConsumer(
        ev.TOPIC_RESUME_RESULTS,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=CONSUMER_GROUP,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
    # Брокер може ще підніматися — кілька спроб старту.
    for attempt in range(1, 11):
        try:
            await consumer.start()
            break
        except Exception:  # noqa: BLE001
            logger.warning("Consumer: спроба старту %d не вдалася, повтор за 3с", attempt)
            await asyncio.sleep(3)
    else:
        logger.error("Consumer: не вдалося під'єднатися до Kafka — споживання вимкнено")
        return

    logger.info("Consumer запущено: топік=%s група=%s", ev.TOPIC_RESUME_RESULTS, CONSUMER_GROUP)
    try:
        async for msg in consumer:
            try:
                await _handle(msg.value)
            except Exception:  # noqa: BLE001 — одне «отруйне» повідомлення не валить консюмер
                logger.exception("Помилка обробки повідомлення з %s", ev.TOPIC_RESUME_RESULTS)
    except asyncio.CancelledError:
        logger.info("Consumer зупиняється…")
        raise
    finally:
        await consumer.stop()
        logger.info("Consumer зупинено")

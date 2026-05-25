"""Kafka consumers (aiokafka). Two independent consumer groups, one per topic.

profession-events (group `reco-worker-professions`):
    profession.upserted → career-SBERT vector → upsert profession_vectors;
    profession.deleted  → delete the row.
    Drained in batches via getmany() so the SBERT encode is batched.

user-events (group `reco-worker-users`):
    user.profile.updated → CareerRNN user vector (upsert) + ESCO skill mapping
                           (publish user.esco_skills.mapped);
    user.resume.uploaded → download PDF, extract text, OpenAI parse
                           (publish user.profile.parsed);
    user.deleted         → delete user_vectors row.

Heavy CPU/GPU work (SBERT, CareerRNN, EmbeddingGemma, pypdf) runs in a thread so
it never blocks the event loop or the other consumer. Processing is idempotent
(upsert by primary key) and tolerant of a single poison message.

On first run, both consumers use auto_offset_reset="earliest" so a backfill
replay from career-service/user-service is picked up.
"""
from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer

from app.config import settings
from app.db import SessionFactory
from app.events import schemas as ev
from app.events.producer import producer
from app.model.runtime import profession_text
from app.services import s3
from app.services.pdf import extract_text
from app.services.state import state
from app.services.vectors import (
    delete_profession_vector,
    delete_user_vector,
    upsert_profession_vectors,
    upsert_user_vector,
)

logger = logging.getLogger("recommendation-worker.consumer")


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

def _profession_row(value: dict, vector: list[float]) -> dict | None:
    prof = value.get("profession") or {}
    pid = value.get("profession_id", prof.get("id"))
    if pid is None:
        return None
    return {
        "profession_id": int(pid),
        "esco_uri": prof.get("esco_uri"),
        "vector": vector,
        "preferred_label": prof.get("preferred_label"),
        "education_level": prof.get("education_level"),
        "avg_salary": prof.get("avg_salary"),
        "vacancies_local": prof.get("vacancies_local"),
        "vacancies_international": prof.get("vacancies_international"),
    }


async def _process_profession_batch(messages: list) -> None:
    runtime = state.runtime
    assert runtime is not None

    # One batched SBERT encode for all upserts in the drain window.
    texts: list[str] = []
    text_pos: dict[int, int] = {}
    for i, msg in enumerate(messages):
        if (msg.value or {}).get("event") == ev.EVENT_PROFESSION_UPSERTED:
            text_pos[i] = len(texts)
            texts.append(profession_text(msg.value.get("profession") or {}))
    if texts:
        async with state.inference_lock:
            vectors = await asyncio.to_thread(runtime.embed_profession_texts, texts)
    else:
        vectors = []

    # Apply in message order; batch consecutive upserts, flush before each delete.
    upserts = 0
    deletes = 0
    async with SessionFactory() as session:
        buffer: list[dict] = []

        async def flush() -> None:
            if buffer:
                await upsert_profession_vectors(session, buffer)
                buffer.clear()

        for i, msg in enumerate(messages):
            value = msg.value or {}
            event = value.get("event")
            if event == ev.EVENT_PROFESSION_UPSERTED:
                row = _profession_row(value, vectors[text_pos[i]])
                if row is not None:
                    buffer.append(row)
                    upserts += 1
            elif event == ev.EVENT_PROFESSION_DELETED:
                await flush()
                pid = value.get("profession_id")
                if pid is not None:
                    await delete_profession_vector(session, int(pid))
                    deletes += 1
        await flush()
        await session.commit()

    if upserts or deletes:
        logger.info("profession-events: %d upserted, %d deleted", upserts, deletes)


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
        while True:
            batches = await consumer.getmany(
                timeout_ms=settings.PROFESSION_BATCH_TIMEOUT_MS,
                max_records=settings.PROFESSION_BATCH_MAX,
            )
            messages = [m for _tp, batch in batches.items() for m in batch]
            if not messages:
                continue
            try:
                await _process_profession_batch(messages)
            except Exception:  # noqa: BLE001 — a bad batch must not kill the consumer
                logger.exception("Error processing profession batch")
    except asyncio.CancelledError:
        logger.info("profession consumer stopping…")
        raise
    finally:
        await consumer.stop()
        logger.info("profession consumer stopped")


# ---------------------------------------------------------------------------
# user-events
# ---------------------------------------------------------------------------

async def _on_profile_updated(user_id: int, profile: dict) -> None:
    runtime = state.runtime
    mapper = state.mapper
    assert runtime is not None and mapper is not None

    # Obligation #2 — user vector (skipped when there is no experience).
    async with state.inference_lock:
        vector = await asyncio.to_thread(runtime.build_user_vector, profile)
    if vector is not None:
        async with SessionFactory() as session:
            await upsert_user_vector(session, user_id, vector)
            await session.commit()
        logger.info("user.profile.updated: user_vector upserted for user_id=%s", user_id)
    else:
        logger.info("user.profile.updated: no experiences for user_id=%s — vector skipped", user_id)

    # Obligation #3 — map free-text skills to ESCO and publish (UI gap analysis).
    async with state.inference_lock:
        esco_skills = await asyncio.to_thread(mapper.map_user_skills, profile)
    await producer.send(
        ev.TOPIC_RESUME_RESULTS,
        ev.esco_skills_mapped_event(user_id, esco_skills),
        key=user_id,
    )
    logger.info("user.profile.updated: %d ESCO skills mapped for user_id=%s", len(esco_skills), user_id)


async def _on_resume_uploaded(user_id: int, s3_key: str | None) -> None:
    parser = state.parser
    assert parser is not None
    if not s3_key:
        logger.warning("user.resume.uploaded: missing s3_key for user_id=%s", user_id)
        return
    data = await s3.download_bytes(s3_key)
    text = await asyncio.to_thread(extract_text, data)
    profile = await parser.parse(text)
    if profile is None:
        logger.error("user.resume.uploaded: parsing failed for user_id=%s (%s)", user_id, s3_key)
        return
    await producer.send(
        ev.TOPIC_RESUME_RESULTS,
        ev.profile_parsed_event(user_id, profile),
        key=user_id,
    )
    logger.info("user.resume.uploaded: profile parsed and published for user_id=%s", user_id)


async def _on_user_deleted(user_id: int) -> None:
    async with SessionFactory() as session:
        await delete_user_vector(session, user_id)
        await session.commit()
    logger.info("user.deleted: user_vector removed for user_id=%s", user_id)


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
        await _on_profile_updated(user_id, value.get("profile") or {})
    elif event == ev.EVENT_RESUME_UPLOADED:
        await _on_resume_uploaded(user_id, value.get("s3_key"))
    elif event == ev.EVENT_USER_DELETED:
        await _on_user_deleted(user_id)
    else:
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
                logger.exception("Error handling user event from %s", ev.TOPIC_USER_EVENTS)
    except asyncio.CancelledError:
        logger.info("user consumer stopping…")
        raise
    finally:
        await consumer.stop()
        logger.info("user consumer stopped")

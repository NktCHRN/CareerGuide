"""Kafka producer (aiokafka). Publishes user-events / (nothing in return).

An event is published AFTER the DB transaction commit (called from the router after
`await session.commit()`), so as not to announce unsaved state.
"""
from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaProducer

from app.config import settings

logger = logging.getLogger("user-service.producer")


class EventProducer:
    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        if self._producer is not None:
            return
        producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: str(k).encode("utf-8") if k is not None else None,
            enable_idempotence=True,
            acks="all",
        )
        # The broker may still be starting up — a few attempts, then graceful degradation
        # (send() only warns, it does not break the request).
        for attempt in range(1, 6):
            try:
                await producer.start()
                self._producer = producer
                logger.info("Kafka producer запущено (%s)", settings.KAFKA_BOOTSTRAP_SERVERS)
                return
            except Exception:  # noqa: BLE001
                logger.warning("Producer: спроба старту %d не вдалася, повтор за 3с", attempt)
                await asyncio.sleep(3)
        logger.error("Producer: не вдалося під'єднатися до Kafka — публікація вимкнена")

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
            logger.info("Kafka producer зупинено")

    async def send(self, topic: str, value: dict, key: str | int | None = None) -> None:
        if self._producer is None:
            logger.warning("Producer не запущено — подію %s пропущено", value.get("event"))
            return
        await self._producer.send_and_wait(topic, value=value, key=key)
        logger.info("→ %s [%s] key=%s", value.get("event"), topic, key)


# Global instance, managed in the application lifespan.
producer = EventProducer()

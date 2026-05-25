"""Kafka producer (aiokafka). Publishes to `resume-results`.

The worker's feedback channel to user-service: `user.profile.parsed` (after
resume parsing) and `user.esco_skills.mapped` (after skill mapping). Started in
the application lifespan.
"""
from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaProducer

from app.config import settings

logger = logging.getLogger("recommendation-worker.producer")


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
        for attempt in range(1, 6):
            try:
                await producer.start()
                self._producer = producer
                logger.info("Kafka producer started (%s)", settings.KAFKA_BOOTSTRAP_SERVERS)
                return
            except Exception:  # noqa: BLE001
                logger.warning("Producer: start attempt %d failed, retrying in 3s", attempt)
                await asyncio.sleep(3)
        logger.error("Producer: could not connect to Kafka — publishing disabled")

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
            logger.info("Kafka producer stopped")

    async def send(self, topic: str, value: dict, key: str | int | None = None) -> None:
        if self._producer is None:
            logger.warning("Producer not started — event %s skipped", value.get("event"))
            return
        await self._producer.send_and_wait(topic, value=value, key=key)
        logger.info("→ %s [%s] key=%s", value.get("event"), topic, key)


# Global instance, managed in the application lifespan.
producer = EventProducer()

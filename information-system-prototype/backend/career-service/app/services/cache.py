"""Redis-backed cache (in-memory, TTL). Best-effort: a Redis failure does not break the request.

We cache the assembled profession details (`GET /api/professions/{id}`) and drop
the key on any update/delete. The cache TTL (~10 min) is shorter than the photo
presign TTL (~1 h), so a cached `photo_url` stays valid for the cache lifetime.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("career-service.cache")

_redis: aioredis.Redis | None = None


async def connect() -> None:
    global _redis
    try:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await _redis.ping()
        logger.info("Redis connected: %s", settings.REDIS_URL)
    except Exception:  # noqa: BLE001
        logger.warning("Redis unavailable — cache disabled", exc_info=True)
        _redis = None


async def close() -> None:
    global _redis
    if _redis is not None:
        try:
            await _redis.aclose()
        except Exception:  # noqa: BLE001
            pass
        _redis = None


def profession_key(profession_id: int) -> str:
    return f"career:profession:{profession_id}"


async def get_json(key: str) -> Any | None:
    if _redis is None:
        return None
    try:
        raw = await _redis.get(key)
        return json.loads(raw) if raw else None
    except Exception:  # noqa: BLE001
        return None


async def set_json(key: str, value: Any, ttl: int) -> None:
    if _redis is None:
        return
    try:
        await _redis.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:  # noqa: BLE001
        pass


async def delete(key: str) -> None:
    if _redis is None:
        return
    try:
        await _redis.delete(key)
    except Exception:  # noqa: BLE001
        pass

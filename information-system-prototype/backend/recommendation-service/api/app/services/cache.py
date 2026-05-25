"""Redis-backed cache (in-memory, TTL). Best-effort: a Redis failure never breaks a request.

We cache the FIRST page of a user's recommendation list, keyed by the user and a
hash of the filters/sort. Invalidation is by TTL (~5 min) — simple and good
enough for the prototype (a freshly recomputed user vector becomes visible after
at most one TTL window).
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("recommendation-api.cache")

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


def list_key(user_id: int, filters: dict[str, Any]) -> str:
    """Stable key for the first recommendation page under a given filter/sort set."""
    blob = json.dumps(filters, sort_keys=True, default=str)
    digest = hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]
    return f"reco:list:{user_id}:{digest}"


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

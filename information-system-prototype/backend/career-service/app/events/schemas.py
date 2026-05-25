"""Topic/event names and payload constructors (shared Kafka conventions).

career-service is the source of truth for professions: it PUBLISHES
`profession.upserted` / `profession.deleted` to `profession-events` and does not
consume anything.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# --- Topics ---
TOPIC_PROFESSION_EVENTS = "profession-events"

# --- Events PUBLISHED by career-service ---
EVENT_PROFESSION_UPSERTED = "profession.upserted"
EVENT_PROFESSION_DELETED = "profession.deleted"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def profession_upserted_event(profession_id: int, profession_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": EVENT_PROFESSION_UPSERTED,
        "profession_id": profession_id,
        "occurred_at": _now_iso(),
        "profession": profession_payload,
    }


def profession_deleted_event(profession_id: int) -> dict[str, Any]:
    return {
        "event": EVENT_PROFESSION_DELETED,
        "profession_id": profession_id,
        "occurred_at": _now_iso(),
    }

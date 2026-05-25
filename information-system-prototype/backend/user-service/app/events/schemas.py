"""Назви топіків/подій та конструктори payload-ів (спільні конвенції Kafka)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# --- Топіки ---
TOPIC_USER_EVENTS = "user-events"
TOPIC_RESUME_RESULTS = "resume-results"

# --- Події, які ПУБЛІКУЄ user-service (топік user-events) ---
EVENT_PROFILE_UPDATED = "user.profile.updated"
EVENT_RESUME_UPLOADED = "user.resume.uploaded"
EVENT_USER_DELETED = "user.deleted"

# --- Події, які СПОЖИВАЄ user-service (топік resume-results) ---
EVENT_PROFILE_PARSED = "user.profile.parsed"
EVENT_ESCO_SKILLS_MAPPED = "user.esco_skills.mapped"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def profile_updated_event(user_id: int, profile_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": EVENT_PROFILE_UPDATED,
        "user_id": user_id,
        "occurred_at": _now_iso(),
        "profile": profile_payload,
    }


def resume_uploaded_event(user_id: int, s3_key: str) -> dict[str, Any]:
    return {
        "event": EVENT_RESUME_UPLOADED,
        "user_id": user_id,
        "occurred_at": _now_iso(),
        "s3_key": s3_key,
    }


def user_deleted_event(user_id: int) -> dict[str, Any]:
    return {
        "event": EVENT_USER_DELETED,
        "user_id": user_id,
        "occurred_at": _now_iso(),
    }

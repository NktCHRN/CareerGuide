"""Topic/event names and payload constructors (shared Kafka conventions).

The worker CONSUMES:
  • profession-events — profession.upserted / profession.deleted;
  • user-events       — user.profile.updated / user.resume.uploaded / user.deleted.

The worker PUBLISHES to resume-results (the worker → user-service feedback channel):
  • user.profile.parsed     — resume parsing result (obligation #4);
  • user.esco_skills.mapped — free-text skills mapped to ESCO (obligation #3).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# --- Topics ---
TOPIC_PROFESSION_EVENTS = "profession-events"
TOPIC_USER_EVENTS = "user-events"
TOPIC_RESUME_RESULTS = "resume-results"

# --- Events CONSUMED (profession-events) ---
EVENT_PROFESSION_UPSERTED = "profession.upserted"
EVENT_PROFESSION_DELETED = "profession.deleted"

# --- Events CONSUMED (user-events) ---
EVENT_PROFILE_UPDATED = "user.profile.updated"
EVENT_RESUME_UPLOADED = "user.resume.uploaded"
EVENT_USER_DELETED = "user.deleted"

# --- Events PUBLISHED (resume-results) ---
EVENT_PROFILE_PARSED = "user.profile.parsed"
EVENT_ESCO_SKILLS_MAPPED = "user.esco_skills.mapped"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def profile_parsed_event(user_id: int, profile_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": EVENT_PROFILE_PARSED,
        "user_id": user_id,
        "occurred_at": _now_iso(),
        "profile": profile_payload,
    }


def esco_skills_mapped_event(user_id: int, esco_skills: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "event": EVENT_ESCO_SKILLS_MAPPED,
        "user_id": user_id,
        "occurred_at": _now_iso(),
        "esco_skills": esco_skills,
    }

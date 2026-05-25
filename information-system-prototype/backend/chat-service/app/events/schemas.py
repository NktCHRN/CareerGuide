"""Topic/event names (shared Kafka conventions).

chat-service is a pure CONSUMER: it keeps local denormalised copies in sync from
`profession-events` (career-service) and `user-events` (user-service). It does
not publish anything.
"""
from __future__ import annotations

# --- Topics consumed ---
TOPIC_PROFESSION_EVENTS = "profession-events"
TOPIC_USER_EVENTS = "user-events"

# --- profession-events ---
EVENT_PROFESSION_UPSERTED = "profession.upserted"
EVENT_PROFESSION_DELETED = "profession.deleted"

# --- user-events ---
EVENT_PROFILE_UPDATED = "user.profile.updated"
EVENT_RESUME_UPLOADED = "user.resume.uploaded"  # ignored here — it is for the worker
EVENT_USER_DELETED = "user.deleted"

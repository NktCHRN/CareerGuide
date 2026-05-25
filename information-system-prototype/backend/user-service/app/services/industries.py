"""Industry reference data — keys of the recommender's `industry_to_id` mapping.

Each experience's `industry` value is published exactly in this UPPERCASE form,
because that is what the model in recommendation-worker expects (industry_to_id.json).
Here we keep the set of valid keys and human-readable labels for the frontend.
"""
from __future__ import annotations

# Keys (UPPERCASE) → human-readable label. Source: models/industry_to_id.json
# of the recommender (without the service entry "<unk>": 0).
INDUSTRY_LABELS: dict[str, str] = {
    "ACCOUNTANT": "Accounting",
    "ADVOCATE": "Legal / Advocacy",
    "AGRICULTURE": "Agriculture",
    "APPAREL": "Apparel & Fashion",
    "ARMY": "Military / Defense",
    "ARTS": "Arts",
    "AUTOMOBILE": "Automotive",
    "AVIATION": "Aviation",
    "BANKING": "Banking",
    "BPO": "Business Process Outsourcing",
    "BUSINESS-DEVELOPMENT": "Business Development",
    "CHEF": "Culinary / Chef",
    "CONSTRUCTION": "Construction",
    "CONSULTANT": "Consulting",
    "DESIGNER": "Design",
    "DIGITAL-MEDIA": "Digital Media",
    "ENGINEERING": "Engineering",
    "FINANCE": "Finance",
    "FITNESS": "Fitness & Wellness",
    "HEALTHCARE": "Healthcare",
    "HR": "Human Resources",
    "INFORMATION-TECHNOLOGY": "Information Technology",
    "PUBLIC-RELATIONS": "Public Relations",
    "SALES": "Sales",
    "TEACHER": "Education / Teaching",
}

INDUSTRY_KEYS: frozenset[str] = frozenset(INDUSTRY_LABELS)


def is_valid_industry(value: str | None) -> bool:
    return value is None or value in INDUSTRY_KEYS


def industries_for_ui() -> list[dict[str, str]]:
    """List of `{key, label}` for the frontend dropdown."""
    return [{"key": k, "label": v} for k, v in INDUSTRY_LABELS.items()]

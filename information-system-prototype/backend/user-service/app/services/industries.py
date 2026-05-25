"""Довідник галузей (industry) — ключі словника `industry_to_id` рекомендатора.

Значення `industry` кожного досвіду публікується саме у цій UPPERCASE-формі,
бо так його очікує модель у recommendation-worker (industry_to_id.json).
Тут зберігаємо набір валідних ключів і людинозрозумілі підписи для фронта.
"""
from __future__ import annotations

# Ключі (UPPERCASE) → людинозрозумілий підпис. Джерело: models/industry_to_id.json
# рекомендатора (без службового "<unk>": 0).
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
    """Список `{key, label}` для випадаючого списку на фронті."""
    return [{"key": k, "label": v} for k, v in INDUSTRY_LABELS.items()]

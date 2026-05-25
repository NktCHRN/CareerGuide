"""Довідкові дані для фронта (не вимагають автентифікації)."""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas import RecommendationCriterion
from app.services.industries import industries_for_ui

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/industries")
async def list_industries() -> dict:
    """Ключі `industry_to_id` із людинозрозумілими підписами (для випадаючого списку)."""
    return {"items": industries_for_ui()}


@router.get("/recommendation-criteria")
async def list_recommendation_criteria() -> dict:
    """Доступні критерії рекомендацій (ФВ8). У прототипі реально працює `experience`."""
    return {"items": [c.value for c in RecommendationCriterion]}

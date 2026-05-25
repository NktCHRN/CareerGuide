"""Reference data for the frontend (does not require authentication)."""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas import RecommendationCriterion
from app.services.industries import industries_for_ui

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/industries")
async def list_industries() -> dict:
    """`industry_to_id` keys with human-readable labels (for the dropdown)."""
    return {"items": industries_for_ui()}


@router.get("/recommendation-criteria")
async def list_recommendation_criteria() -> dict:
    """Available recommendation criteria (FR8). In the prototype only `experience` actually works."""
    return {"items": [c.value for c in RecommendationCriterion]}

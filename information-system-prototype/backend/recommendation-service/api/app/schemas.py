"""Pydantic v2 DTOs for recommendation-api."""
from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# --------------------------------------------------------------------------- #
#  Shared
# --------------------------------------------------------------------------- #
class Page(BaseModel, Generic[T]):
    """Paginated response: {items, page, page_size, total}."""

    items: list[T]
    page: int
    page_size: int
    total: int


# --------------------------------------------------------------------------- #
#  Recommendations
# --------------------------------------------------------------------------- #
class RecommendationItem(BaseModel):
    """One ranked profession. Details/photo are fetched from career-service by id."""

    profession_id: int
    score: float = Field(description="Cosine similarity in [0, 1] (1 = closest)")
    preferred_label: str | None = None
    education_level: str | None = None
    avg_salary: float | None = None
    vacancies_local: int | None = None
    vacancies_international: int | None = None


class StatusOut(BaseModel):
    """Whether the user's recommendation vector has been computed by the worker."""

    ready: bool
    updated_at: datetime | None = None


class ScoresRequest(BaseModel):
    profession_ids: list[int] = Field(default_factory=list)


class ScoresOut(BaseModel):
    """Map profession_id → cosine score for the current user (FR9 search boosting).

    `ready` is False when the user has no vector yet; `scores` is then empty.
    Profession ids without a stored vector are simply omitted from `scores`.
    """

    ready: bool
    scores: dict[int, float]

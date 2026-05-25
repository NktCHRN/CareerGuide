"""Pydantic v2 DTOs for career-service."""
from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


# --------------------------------------------------------------------------- #
#  Shared
# --------------------------------------------------------------------------- #
class MessageResponse(BaseModel):
    detail: str


class Page(BaseModel, Generic[T]):
    """Paginated response: {items, page, page_size, total}."""

    items: list[T]
    page: int
    page_size: int
    total: int


# --------------------------------------------------------------------------- #
#  Skills (nested)
# --------------------------------------------------------------------------- #
class KnowledgeSkillOut(BaseModel):
    skill_uri: str
    label: str
    relation_type: str  # essential | optional


# --------------------------------------------------------------------------- #
#  Profession — output
# --------------------------------------------------------------------------- #
class ProfessionListItem(BaseModel):
    """Lightweight item for search / browse listings (no S3 lookup per row)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    esco_uri: str | None = None
    esco_code: str | None = None
    isco_group: int | None = None
    preferred_label: str
    alt_labels: list[str] = []
    description: str | None = None


class ProfessionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    esco_uri: str | None = None
    esco_code: str | None = None
    isco_group: int | None = None
    preferred_label: str
    description: str | None = None
    alt_labels: list[str] = []
    riasec_type: str | None = None
    professional_values: list[str] | None = None
    work_style: str | None = None
    education_level: str | None = None
    avg_salary: float | None = None
    vacancies_local: int | None = None
    vacancies_international: int | None = None
    responsibilities: list[str] | None = None
    photo_url: str | None = None
    knowledge_skills: list[KnowledgeSkillOut] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --------------------------------------------------------------------------- #
#  Profession — admin input
# --------------------------------------------------------------------------- #
class ProfessionCreate(BaseModel):
    """Admin-created profession. Only `preferred_label` is mandatory; the rest
    (including the ESCO identifiers) are optional, so a custom, non-ESCO
    profession can be added too."""

    preferred_label: str = Field(min_length=1, max_length=512)
    esco_uri: str | None = Field(default=None, max_length=512)
    esco_code: str | None = Field(default=None, max_length=64)
    isco_group: int | None = None
    description: str | None = None
    alt_labels: list[str] = []
    riasec_type: str | None = Field(default=None, max_length=16)
    professional_values: list[str] | None = None
    work_style: str | None = Field(default=None, max_length=255)
    education_level: str | None = Field(default=None, max_length=255)
    avg_salary: float | None = Field(default=None, ge=0)
    vacancies_local: int | None = Field(default=None, ge=0)
    vacancies_international: int | None = Field(default=None, ge=0)
    responsibilities: list[str] | None = None


class ProfessionUpdate(BaseModel):
    """Partial update: a field left unset is not touched."""

    preferred_label: str | None = Field(default=None, min_length=1, max_length=512)
    esco_uri: str | None = Field(default=None, max_length=512)
    esco_code: str | None = Field(default=None, max_length=64)
    isco_group: int | None = None
    description: str | None = None
    alt_labels: list[str] | None = None
    riasec_type: str | None = Field(default=None, max_length=16)
    professional_values: list[str] | None = None
    work_style: str | None = Field(default=None, max_length=255)
    education_level: str | None = Field(default=None, max_length=255)
    avg_salary: float | None = Field(default=None, ge=0)
    vacancies_local: int | None = Field(default=None, ge=0)
    vacancies_international: int | None = Field(default=None, ge=0)
    responsibilities: list[str] | None = None


# --------------------------------------------------------------------------- #
#  Photo upload
# --------------------------------------------------------------------------- #
class PhotoUploadUrlOut(BaseModel):
    """Presigned PUT URL for uploading a profession photo to S3/MinIO."""

    url: str
    key: str
    method: str = "PUT"
    content_type: str
    esco_code: str | None = None
    expires_in: int

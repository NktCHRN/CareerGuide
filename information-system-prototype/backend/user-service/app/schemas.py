"""Pydantic v2 DTOs for user-service."""
from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.industries import is_valid_industry
from app.utils import CURRENT, is_valid_month_year

# Lightweight email check (not EmailStr): we allow the `.local` domains of the
# seed/defaults, which email-validator rejects as a reserved TLD.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str) -> str:
    value = (value or "").strip().lower()
    if not _EMAIL_RE.match(value):
        raise ValueError("некоректний email")
    return value


# --------------------------------------------------------------------------- #
#  Shared
# --------------------------------------------------------------------------- #
class MessageResponse(BaseModel):
    detail: str


class RecommendationCriterion(str, Enum):
    experience = "experience"
    psychological = "psychological"
    hobbies = "hobbies"
    competencies = "competencies"


def _validate_month_year(value: str | None, *, allow_current: bool) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if allow_current and value.lower() == CURRENT:
        return CURRENT
    if not is_valid_month_year(value):
        raise ValueError('очікується формат "M/YYYY"' + (' або "current"' if allow_current else ""))
    return value


# --------------------------------------------------------------------------- #
#  Profile — nested structures
# --------------------------------------------------------------------------- #
class Education(BaseModel):
    level: str | None = None
    field: str | None = None
    years: str | None = None
    university: str | None = None


class ExperienceIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    industry: str | None = None  # industry_to_id key (UPPERCASE) or null
    start: str | None = None  # "M/YYYY"
    end: str | None = None  # "M/YYYY" | "current"
    months_of_experience: int | None = Field(default=None, ge=0)

    @field_validator("industry")
    @classmethod
    def _check_industry(cls, v: str | None) -> str | None:
        if not is_valid_industry(v):
            raise ValueError("невідомий ключ industry (очікується ключ industry_to_id або null)")
        return v

    @field_validator("start")
    @classmethod
    def _check_start(cls, v: str | None) -> str | None:
        return _validate_month_year(v, allow_current=False)

    @field_validator("end")
    @classmethod
    def _check_end(cls, v: str | None) -> str | None:
        return _validate_month_year(v, allow_current=True)


class ExperienceOut(ExperienceIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int


class EscoSkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill_uri: str
    label: str


# --------------------------------------------------------------------------- #
#  Profile — input / output
# --------------------------------------------------------------------------- #
class ProfileUpdate(BaseModel):
    """Profile fields the user can set (registration / PUT profile)."""

    name: str | None = None
    summary: str | None = None
    skills: list[str] | None = None
    hobbies: list[str] | None = None
    education: Education | None = None
    riasec_result: dict[str, Any] | None = None
    professional_values: list[str] | None = None
    work_style: str | None = None
    experiences: list[ExperienceIn] | None = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str
    email_verified: bool
    role: str
    name: str | None = None
    summary: str | None = None
    skills: list[str] = []
    hobbies: list[str] = []
    education: Education | None = None
    riasec_result: dict[str, Any] | None = None
    professional_values: list[str] | None = None
    work_style: str | None = None
    recommendation_criteria: list[RecommendationCriterion] = [RecommendationCriterion.experience]
    experiences: list[ExperienceOut] = []
    esco_skills: list[EscoSkillOut] = []
    updated_at: datetime | None = None


class CriteriaUpdate(BaseModel):
    recommendation_criteria: list[RecommendationCriterion] = Field(min_length=1)

    @field_validator("recommendation_criteria")
    @classmethod
    def _dedupe(cls, v: list[RecommendationCriterion]) -> list[RecommendationCriterion]:
        seen: list[RecommendationCriterion] = []
        for item in v:
            if item not in seen:
                seen.append(item)
        return seen


# --------------------------------------------------------------------------- #
#  Authentication
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    profile: ProfileUpdate | None = None

    _norm_email = field_validator("email")(normalize_email)


class LoginRequest(BaseModel):
    email: str
    password: str

    _norm_email = field_validator("email")(normalize_email)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access-token lifetime in seconds


class RegisterResponse(TokenPair):
    user_id: int
    # In dev mode (APP_ENV=dev, FEATURE_EMAIL_ENABLED=false) we return the email
    # verification token, because no email is sent.
    email_verification_token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class RequestPasswordReset(BaseModel):
    email: str

    _norm_email = field_validator("email")(normalize_email)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class DevTokenResponse(MessageResponse):
    """Response for endpoints that send emails; in dev it carries the token."""

    dev_token: str | None = None


# --------------------------------------------------------------------------- #
#  Resume
# --------------------------------------------------------------------------- #
class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    s3_key: str
    uploaded_at: datetime
    download_url: str | None = None

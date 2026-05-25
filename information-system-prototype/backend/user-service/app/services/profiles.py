"""Бізнес-логіка профілю: застосування змін, мердж розпарсеного резюме,
побудова payload події `user.profile.updated`.

Винесено окремо, бо потрібно і роутерам, і Kafka-консюмеру, і backfill-скрипту.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Profile, ProfileExperience, User
from app.schemas import (
    EscoSkillOut,
    ExperienceOut,
    ProfileOut,
    ProfileUpdate,
)
from app.services.industries import is_valid_industry
from app.utils import compute_months_of_experience

# Поля профілю, зміна яких впливає на рекомендації → публікувати user.profile.updated.
RECO_FIELDS = ("summary", "skills", "experiences")


def _norm_skills(skills: list[str] | None) -> list[str]:
    """Прибирає порожні/дублікати (case-insensitive), зберігаючи порядок."""
    out: list[str] = []
    seen: set[str] = set()
    for s in skills or []:
        s = (s or "").strip()
        if not s:
            continue
        key = s.lower()
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def _make_experience(user_id: int, data: dict[str, Any], position: int) -> ProfileExperience:
    industry = data.get("industry")
    if not is_valid_industry(industry):
        industry = None
    start = data.get("start")
    end = data.get("end")
    months = data.get("months_of_experience")
    if months is None:
        months = compute_months_of_experience(start, end)
    return ProfileExperience(
        user_id=user_id,
        title=(data.get("title") or "").strip(),
        description=data.get("description"),
        industry=industry,
        start=start,
        end=end,
        months_of_experience=months,
        position=position,
    )


def apply_profile_update(profile: Profile, update: ProfileUpdate) -> bool:
    """Застосовує часткове оновлення (None = поле не чіпати).

    Повертає True, якщо змінилося хоч одне reco-поле (summary/skills/experiences).
    """
    data = update.model_dump(exclude_unset=True)
    reco_changed = False

    if "name" in data:
        profile.name = data["name"]
    if "summary" in data:
        profile.summary = data["summary"]
        reco_changed = True
    if "skills" in data:
        profile.skills = _norm_skills(data["skills"])
        reco_changed = True
    if "hobbies" in data:
        profile.hobbies = [h.strip() for h in (data["hobbies"] or []) if h and h.strip()]
    if "education" in data:
        profile.education = data["education"]
    if "riasec_result" in data:
        profile.riasec_result = data["riasec_result"]
    if "professional_values" in data:
        profile.professional_values = data["professional_values"]
    if "work_style" in data:
        profile.work_style = data["work_style"]
    if "experiences" in data:
        new_items = [
            _make_experience(profile.user_id, exp, idx)
            for idx, exp in enumerate(data["experiences"] or [])
        ]
        profile.experiences = new_items
        reco_changed = True

    return reco_changed


def merge_parsed_profile(profile: Profile, parsed: dict[str, Any]) -> None:
    """Мердж результату парсингу резюме (worker) у профіль.

    Скаляри заповнюються лише якщо порожні (не затирає правки користувача),
    навички об'єднуються, нові досвіди додаються (дедуп за title+start) —
    тож обробка ідемпотентна.
    """
    name = (parsed.get("name") or "").strip()
    if name and not (profile.name or "").strip():
        profile.name = name

    summary = (parsed.get("summary") or "").strip()
    if summary and not (profile.summary or "").strip():
        profile.summary = summary

    profile.skills = _norm_skills(list(profile.skills or []) + list(parsed.get("skills") or []))

    existing_keys = {
        ((e.title or "").strip().lower(), (e.start or "")) for e in profile.experiences
    }
    next_pos = len(profile.experiences)
    for exp in parsed.get("experiences") or []:
        key = ((exp.get("title") or "").strip().lower(), (exp.get("start") or ""))
        if not key[0] or key in existing_keys:
            continue
        existing_keys.add(key)
        profile.experiences.append(_make_experience(profile.user_id, exp, next_pos))
        next_pos += 1


async def load_full_profile(session: AsyncSession, user_id: int) -> Profile | None:
    """Завантажує профіль із досвідами та ESCO-навичками."""
    result = await session.execute(
        select(Profile)
        .where(Profile.user_id == user_id)
        .options(selectinload(Profile.experiences), selectinload(Profile.esco_skills))
    )
    return result.scalar_one_or_none()


def build_profile_out(user: User, profile: Profile) -> ProfileOut:
    """Збирає DTO профілю для віддачі клієнту."""
    return ProfileOut(
        user_id=user.id,
        email=user.email,
        email_verified=user.email_verified,
        role=user.role,
        name=profile.name,
        summary=profile.summary,
        skills=list(profile.skills or []),
        hobbies=list(profile.hobbies or []),
        education=profile.education,
        riasec_result=profile.riasec_result,
        professional_values=profile.professional_values,
        work_style=profile.work_style,
        recommendation_criteria=list(profile.recommendation_criteria or ["experience"]),
        experiences=[
            ExperienceOut.model_validate(e)
            for e in sorted(profile.experiences, key=lambda x: x.position)
        ],
        esco_skills=[EscoSkillOut.model_validate(s) for s in profile.esco_skills],
        updated_at=profile.updated_at,
    )


def build_profile_event_payload(profile: Profile) -> dict[str, Any]:
    """Payload поля `profile` події `user.profile.updated` (для worker/chat)."""
    return {
        "summary": profile.summary,
        "skills": list(profile.skills or []),
        "experiences": [
            {
                "title": e.title,
                "description": e.description,
                "industry": e.industry,
                "start": e.start,
                "end": e.end,
                "months_of_experience": e.months_of_experience,
            }
            for e in sorted(profile.experiences, key=lambda x: x.position)
        ],
    }

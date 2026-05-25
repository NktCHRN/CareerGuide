"""Профіль користувача (ФВ4, ФВ5, ФВ8)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.deps import get_current_user
from app.events.publish import publish_profile_updated
from app.models import Profile, User
from app.schemas import CriteriaUpdate, ProfileOut, ProfileUpdate
from app.services import cache
from app.services.profiles import apply_profile_update, build_profile_out, load_full_profile

router = APIRouter(prefix="/api/profile", tags=["profile"])


async def _get_or_create_profile(session: AsyncSession, user_id: int) -> Profile:
    profile = await load_full_profile(session, user_id)
    if profile is None:
        profile = Profile(
            user_id=user_id,
            skills=[],
            hobbies=[],
            recommendation_criteria=["experience"],
            experiences=[],
            esco_skills=[],
        )
        session.add(profile)
        await session.commit()
        profile = await load_full_profile(session, user_id)
    return profile


@router.get("/me", response_model=ProfileOut)
async def get_my_profile(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProfileOut | dict:
    cached = await cache.get_json(cache.profile_key(user.id))
    if cached is not None:
        return cached

    profile = await _get_or_create_profile(session, user.id)
    out = build_profile_out(user, profile)
    await cache.set_json(cache.profile_key(user.id), out.model_dump(mode="json"), settings.PROFILE_CACHE_TTL_SECONDS)
    return out


@router.put("/me", response_model=ProfileOut)
async def update_my_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProfileOut:
    profile = await _get_or_create_profile(session, user.id)
    reco_changed = apply_profile_update(profile, payload)
    await session.commit()
    await cache.delete(cache.profile_key(user.id))

    if reco_changed:
        await publish_profile_updated(session, user.id)

    profile = await load_full_profile(session, user.id)
    return build_profile_out(user, profile)


@router.patch("/me/criteria", response_model=ProfileOut)
async def update_criteria(
    payload: CriteriaUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProfileOut:
    profile = await _get_or_create_profile(session, user.id)
    profile.recommendation_criteria = [c.value for c in payload.recommendation_criteria]
    await session.commit()
    await cache.delete(cache.profile_key(user.id))

    # Зміна критеріїв теж тягне user.profile.updated (спільні конвенції).
    await publish_profile_updated(session, user.id)

    profile = await load_full_profile(session, user.id)
    return build_profile_out(user, profile)

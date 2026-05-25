"""Professions: public search/list/details + admin CRUD + photo upload URL (FR9–FR15)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.deps import require_admin
from app.events.publish import publish_profession_deleted, publish_profession_upserted
from app.schemas import (
    MessageResponse,
    Page,
    PhotoUploadUrlOut,
    ProfessionCreate,
    ProfessionDetail,
    ProfessionListItem,
    ProfessionUpdate,
)
from app.services import cache, s3
from app.services.professions import (
    apply_update,
    build_detail,
    create_profession,
    load_knowledge_skills,
    load_profession,
    search_professions,
)

router = APIRouter(prefix="/api", tags=["professions"])

_ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


async def _detail_for(session: AsyncSession, profession) -> ProfessionDetail:
    knowledge_skills = await load_knowledge_skills(session, profession.id)
    photo_url = await s3.photo_url(profession.id, profession.photo_key)
    return build_detail(profession, knowledge_skills, photo_url)


async def _load_or_404(session: AsyncSession, profession_id: int):
    profession = await load_profession(session, profession_id)
    if profession is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profession not found")
    return profession


# --------------------------------------------------------------------------- #
#  Public: search / list (FR9, FR10)
# --------------------------------------------------------------------------- #
@router.get("/professions", response_model=Page[ProfessionListItem])
async def list_professions(
    query: str | None = Query(default=None, description="Search by preferred_label / alt_labels"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> Page[ProfessionListItem]:
    rows, total = await search_professions(session, query, page, page_size)
    return Page[ProfessionListItem](
        items=[ProfessionListItem.model_validate(r) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


# --------------------------------------------------------------------------- #
#  Public: details (FR11)
# --------------------------------------------------------------------------- #
@router.get("/professions/{profession_id}", response_model=ProfessionDetail)
async def get_profession(
    profession_id: int,
    session: AsyncSession = Depends(get_session),
) -> ProfessionDetail | dict:
    cached = await cache.get_json(cache.profession_key(profession_id))
    if cached is not None:
        return cached

    profession = await _load_or_404(session, profession_id)
    detail = await _detail_for(session, profession)
    await cache.set_json(
        cache.profession_key(profession_id),
        detail.model_dump(mode="json"),
        settings.PROFESSION_CACHE_TTL_SECONDS,
    )
    return detail


# --------------------------------------------------------------------------- #
#  Admin: create / update / delete (FR13–FR15)
# --------------------------------------------------------------------------- #
@router.post("/professions", response_model=ProfessionDetail, status_code=status.HTTP_201_CREATED)
async def create_profession_endpoint(
    payload: ProfessionCreate,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> ProfessionDetail:
    profession = create_profession(payload)
    session.add(profession)
    await session.commit()
    await session.refresh(profession)

    await publish_profession_upserted(session, profession.id)
    return await _detail_for(session, profession)


@router.put("/professions/{profession_id}", response_model=ProfessionDetail)
async def update_profession_endpoint(
    profession_id: int,
    payload: ProfessionUpdate,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> ProfessionDetail:
    profession = await _load_or_404(session, profession_id)
    apply_update(profession, payload)
    await session.commit()
    await session.refresh(profession)
    await cache.delete(cache.profession_key(profession_id))

    await publish_profession_upserted(session, profession_id)
    return await _detail_for(session, profession)


@router.delete("/professions/{profession_id}", response_model=MessageResponse)
async def delete_profession_endpoint(
    profession_id: int,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> MessageResponse:
    profession = await _load_or_404(session, profession_id)
    await session.delete(profession)
    await session.commit()
    await cache.delete(cache.profession_key(profession_id))

    await publish_profession_deleted(profession_id)
    return MessageResponse(detail="Profession deleted")


# --------------------------------------------------------------------------- #
#  Admin: presigned PUT URL for the profession photo
# --------------------------------------------------------------------------- #
@router.get("/admin/professions/{profession_id}/photo-upload-url", response_model=PhotoUploadUrlOut)
async def photo_upload_url(
    profession_id: int,
    content_type: str = Query(default="image/jpeg", description="image/jpeg | image/png | image/webp"),
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
) -> PhotoUploadUrlOut:
    profession = await _load_or_404(session, profession_id)
    ctype = content_type.strip().lower()
    if ctype not in _ALLOWED_PHOTO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported content_type (allowed: image/jpeg, image/png, image/webp)",
        )

    url, key = await s3.presigned_put_url(profession_id, ctype)
    # Dropping the cached details makes a freshly uploaded photo appear sooner.
    await cache.delete(cache.profession_key(profession_id))
    return PhotoUploadUrlOut(
        url=url,
        key=key,
        content_type=ctype,
        esco_code=profession.esco_code,
        expires_in=settings.PHOTO_PRESIGN_TTL_SECONDS,
    )

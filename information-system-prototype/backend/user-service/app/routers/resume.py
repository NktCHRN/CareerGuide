"""Resumes (FR1, FR5) — upload to S3 and emit an event, WITHOUT parsing.

Parsing is done by the recommendation-worker: it consumes `user.resume.uploaded`,
downloads the PDF from S3, parses it via the LLM and returns the profile in the
`user.profile.parsed` event on the `resume-results` topic.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.events.publish import publish_resume_uploaded
from app.models import Resume, User
from app.schemas import ResumeOut
from app.services import s3

router = APIRouter(prefix="/api/profile/me", tags=["resume"])

MAX_RESUME_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/resume", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ResumeOut:
    body = await file.read()
    if not body:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Порожній файл")
    if len(body) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Файл завеликий (макс. 10 МБ)")

    is_pdf = (file.content_type == "application/pdf") or (file.filename or "").lower().endswith(".pdf")
    if not is_pdf or not body.startswith(b"%PDF"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Очікується PDF-файл")

    s3_key = await s3.upload_resume(user.id, body)
    resume = Resume(user_id=user.id, s3_key=s3_key)
    session.add(resume)
    await session.commit()
    await session.refresh(resume)

    # Announce the upload → the worker will pick it up and parse it.
    await publish_resume_uploaded(user.id, s3_key)

    download_url = await s3.presigned_get_url(s3_key)
    out = ResumeOut.model_validate(resume)
    out.download_url = download_url
    return out


@router.get("/resumes", response_model=list[ResumeOut])
async def list_resumes(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ResumeOut]:
    rows = (
        await session.scalars(
            select(Resume).where(Resume.user_id == user.id).order_by(Resume.uploaded_at.desc())
        )
    ).all()
    items: list[ResumeOut] = []
    for r in rows:
        out = ResumeOut.model_validate(r)
        out.download_url = await s3.presigned_get_url(r.s3_key)
        items.append(out)
    return items

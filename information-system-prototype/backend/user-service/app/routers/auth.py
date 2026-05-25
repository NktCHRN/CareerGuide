"""Authentication and password management (FR1–FR3, FR7)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.deps import get_current_user
from app.events.publish import publish_profile_updated
from app.models import EmailToken, Profile, User
from app.schemas import (
    ChangePasswordRequest,
    DevTokenResponse,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    RequestPasswordReset,
    ResetPasswordRequest,
    TokenPair,
)
from app.security import (
    REFRESH,
    JWTError,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_email_token,
    hash_password,
    verify_password,
)
from app.services import cache
from app.services.email import reset_password_html, send_email, verify_email_html
from app.services.profiles import apply_profile_update

router = APIRouter(prefix="/api/auth", tags=["auth"])


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def _token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id, user.role, user.email),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def _new_email_token(session: AsyncSession, user_id: int, kind: str, ttl_hours: int) -> str:
    token = generate_email_token()
    session.add(
        EmailToken(
            user_id=user_id,
            kind=kind,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
            used=False,
        )
    )
    return token


def _maybe_dev_token(sent: bool, token: str) -> str | None:
    """In dev (the email was not sent) we return the token in the response; in prod — never."""
    if sent:
        return None
    return token if settings.is_dev else None


# --------------------------------------------------------------------------- #
#  Registration / login / refresh
# --------------------------------------------------------------------------- #
@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_session)) -> RegisterResponse:
    email = payload.email.lower()
    exists = await session.scalar(select(User.id).where(User.email == email))
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email вже зареєстровано")

    user = User(email=email, password_hash=hash_password(payload.password), role="user", email_verified=False)
    session.add(user)
    await session.flush()  # obtain user.id

    profile = Profile(user_id=user.id, skills=[], hobbies=[], recommendation_criteria=["experience"], experiences=[], esco_skills=[])
    reco_changed = False
    if payload.profile is not None:
        reco_changed = apply_profile_update(profile, payload.profile)
    session.add(profile)

    token = await _new_email_token(session, user.id, "verify", settings.VERIFY_TOKEN_TTL_HOURS)
    await session.commit()

    sent = await send_email(user.email, *verify_email_html(token), dev_context="verify-email")
    if reco_changed:
        await publish_profile_updated(session, user.id)

    pair = _token_pair(user)
    return RegisterResponse(
        **pair.model_dump(),
        user_id=user.id,
        email_verification_token=_maybe_dev_token(sent, token),
    )


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenPair:
    user = await session.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невірний email або пароль")
    return _token_pair(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, session: AsyncSession = Depends(get_session)) -> TokenPair:
    try:
        claims = decode_token(payload.refresh_token)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недійсний refresh-токен") from exc
    if claims.get("type") != REFRESH:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Очікується refresh-токен")
    user = await session.get(User, int(claims["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Користувача не знайдено")
    return _token_pair(user)


# --------------------------------------------------------------------------- #
#  Email confirmation (FR7)
# --------------------------------------------------------------------------- #
@router.get("/verify-email", response_model=MessageResponse)
async def verify_email(token: str = Query(...), session: AsyncSession = Depends(get_session)) -> MessageResponse:
    record = await session.scalar(
        select(EmailToken).where(EmailToken.token == token, EmailToken.kind == "verify")
    )
    if record is None or record.used or record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Недійсний або прострочений токен")
    user = await session.get(User, record.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Користувача не знайдено")
    user.email_verified = True
    record.used = True
    await session.commit()
    await cache.delete(cache.profile_key(user.id))
    return MessageResponse(detail="Пошту підтверджено")


# --------------------------------------------------------------------------- #
#  Password reset / change (FR3)
# --------------------------------------------------------------------------- #
@router.post("/request-password-reset", response_model=DevTokenResponse)
async def request_password_reset(
    payload: RequestPasswordReset, session: AsyncSession = Depends(get_session)
) -> DevTokenResponse:
    user = await session.scalar(select(User).where(User.email == payload.email.lower()))
    # Do not reveal whether the account exists — the response is the same.
    if user is None:
        return DevTokenResponse(detail="Якщо такий акаунт існує, лист надіслано")

    token = await _new_email_token(session, user.id, "reset", settings.RESET_TOKEN_TTL_HOURS)
    await session.commit()
    sent = await send_email(user.email, *reset_password_html(token), dev_context="reset-password")
    return DevTokenResponse(detail="Якщо такий акаунт існує, лист надіслано", dev_token=_maybe_dev_token(sent, token))


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, session: AsyncSession = Depends(get_session)) -> MessageResponse:
    record = await session.scalar(
        select(EmailToken).where(EmailToken.token == payload.token, EmailToken.kind == "reset")
    )
    if record is None or record.used or record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Недійсний або прострочений токен")
    user = await session.get(User, record.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Користувача не знайдено")
    user.password_hash = hash_password(payload.new_password)
    record.used = True
    await session.commit()
    return MessageResponse(detail="Пароль змінено")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Поточний пароль невірний")
    user.password_hash = hash_password(payload.new_password)
    session.add(user)
    await session.commit()
    return MessageResponse(detail="Пароль змінено")

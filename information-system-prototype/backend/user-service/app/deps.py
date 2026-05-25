"""FastAPI dependencies: DB session, current user, admin check.

Supports two authentication modes (`AUTH_MODE`):
  • gateway — trust the `X-User-Id` / `X-User-Role` headers from the API Gateway;
  • local   — validate the JWT with the same secret (isolated service dev).
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import User
from app.security import ACCESS, JWTError, decode_token

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Не автентифіковано",
    headers={"WWW-Authenticate": "Bearer"},
)


def _user_id_from_gateway(request: Request) -> int:
    raw = request.headers.get("X-User-Id")
    if not raw:
        raise _UNAUTHORIZED
    try:
        return int(raw)
    except ValueError as exc:
        raise _UNAUTHORIZED from exc


def _user_id_from_jwt(authorization: str | None) -> int:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _UNAUTHORIZED
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise _UNAUTHORIZED from exc
    if payload.get("type") != ACCESS:
        raise _UNAUTHORIZED
    sub = payload.get("sub")
    if sub is None:
        raise _UNAUTHORIZED
    try:
        return int(sub)
    except (TypeError, ValueError) as exc:
        raise _UNAUTHORIZED from exc


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> User:
    if settings.AUTH_MODE.lower() == "gateway":
        user_id = _user_id_from_gateway(request)
    else:
        user_id = _user_id_from_jwt(authorization)

    user = await session.get(User, user_id)
    if user is None:
        raise _UNAUTHORIZED
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Потрібні права адміністратора")
    return user

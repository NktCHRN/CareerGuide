"""FastAPI dependencies: the current principal and the admin check.

career-service has no users table — it only needs the caller's id and role.
Supports two authentication modes (`AUTH_MODE`):
  • gateway — trust the `X-User-Id` / `X-User-Role` headers from the API Gateway;
  • local   — validate the JWT with the shared secret (isolated service dev).

The public read endpoints (search / list / details) do not require these
dependencies; only the admin CRUD endpoints do.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status

from app.config import settings
from app.security import ACCESS, JWTError, decode_token

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass(frozen=True)
class Principal:
    user_id: int
    role: str


def _principal_from_gateway(request: Request) -> Principal:
    raw_id = request.headers.get("X-User-Id")
    if not raw_id:
        raise _UNAUTHORIZED
    try:
        user_id = int(raw_id)
    except ValueError as exc:
        raise _UNAUTHORIZED from exc
    role = (request.headers.get("X-User-Role") or "user").strip().lower()
    return Principal(user_id=user_id, role=role)


def _principal_from_jwt(authorization: str | None) -> Principal:
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
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise _UNAUTHORIZED from exc
    role = (payload.get("role") or "user").strip().lower()
    return Principal(user_id=user_id, role=role)


async def get_principal(
    request: Request,
    authorization: str | None = Header(default=None),
) -> Principal:
    if settings.AUTH_MODE.lower() == "gateway":
        return _principal_from_gateway(request)
    return _principal_from_jwt(authorization)


async def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    if principal.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return principal

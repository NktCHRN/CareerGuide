"""Authentication: extract the caller's principal from the access token.

The gateway is the single place that validates the JWT. The validated
`Principal` is forwarded downstream as `X-User-Id` / `X-User-Role`, so the
services run in `AUTH_MODE=gateway` and trust those headers instead of
re-validating the token.

`parse_principal` is best-effort: it returns `None` for a missing/malformed/
expired token rather than raising, so the catch-all handler can decide per route
whether authentication is actually required (public routes tolerate `None`).
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status

from app.config import settings
from app.security import ACCESS, JWTError, decode_token


@dataclass(frozen=True)
class Principal:
    user_id: int
    role: str


def parse_principal(authorization: str | None) -> Principal | None:
    """Decode and validate a `Bearer <token>` header. Returns `None` on any failure."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except JWTError:
        return None
    if payload.get("type") != ACCESS:
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        return None
    role = (payload.get("role") or "user").strip().lower()
    return Principal(user_id=user_id, role=role)


async def verify_with_user_service(
    client: httpx.AsyncClient,
    authorization: str | None,
    principal: Principal,
) -> None:
    """Optional extra check (`GATEWAY_VERIFY_VIA_USER_SERVICE`): confirm the user
    still exists / is active by querying user-service. Raises 401 if not, 503 if
    user-service is unreachable.
    """
    url = settings.USER_SERVICE_URL.rstrip("/") + "/api/profile/me"
    headers = {
        "X-User-Id": str(principal.user_id),
        "X-User-Role": principal.role,
    }
    if authorization:
        headers["Authorization"] = authorization
    try:
        resp = await client.get(
            url,
            headers=headers,
            timeout=httpx.Timeout(10.0, connect=5.0),
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication backend unavailable",
        ) from exc
    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

"""JWT validation (HS256).

api-gateway does NOT issue tokens (only user-service does). It validates the
access token with the shared `JWT_SECRET` on every protected route and forwards
the resulting principal to downstream services as `X-User-Id` / `X-User-Role`.
There are no passwords here — hence no password hashing.
"""
from __future__ import annotations

from typing import Any

from jose import JWTError, jwt

from app.config import settings

ACCESS = "access"


def decode_token(token: str) -> dict[str, Any]:
    """Decodes and validates the signature/expiry. Raises `JWTError` on failure."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])


__all__ = ["ACCESS", "JWTError", "decode_token"]

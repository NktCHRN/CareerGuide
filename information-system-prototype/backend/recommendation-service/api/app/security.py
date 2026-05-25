"""JWT validation (HS256).

recommendation-api does NOT issue tokens (only user-service does). In `local`
AUTH_MODE it validates the access token with the shared `JWT_SECRET`; in
`gateway` mode it trusts the headers from the API Gateway and this module is
unused. There are no passwords here — hence no password hashing.
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

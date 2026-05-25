"""JWT (HS256) і хешування паролів.

user-service — єдиний емітент токенів у системі. Access: ~30 хв, refresh —
довгий. Payload access: {sub, role, email, exp, type}.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS = "access"
REFRESH = "refresh"


# --------------------------------------------------------------------------- #
#  Паролі
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(password, password_hash)
    except ValueError:
        return False


# --------------------------------------------------------------------------- #
#  JWT
# --------------------------------------------------------------------------- #
def _encode(claims: dict[str, Any], expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {**claims, "iat": now, "exp": now + expires_delta}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def create_access_token(user_id: int, role: str, email: str) -> str:
    return _encode(
        {"sub": str(user_id), "role": role, "email": email, "type": ACCESS},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: int) -> str:
    return _encode(
        {"sub": str(user_id), "type": REFRESH},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Декодує і валідує підпис/термін. Кидає `JWTError` при помилці."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])


# --------------------------------------------------------------------------- #
#  Токени для листів (verify / reset)
# --------------------------------------------------------------------------- #
def generate_email_token() -> str:
    return secrets.token_urlsafe(32)


__all__ = [
    "ACCESS",
    "REFRESH",
    "JWTError",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "generate_email_token",
]

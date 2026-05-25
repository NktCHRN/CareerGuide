"""Routing table and access policy.

The public API namespaces every service under `/api/<service-key>/...`. Each
downstream service, however, exposes its endpoints under its own `/api/...`
prefix (e.g. user-service has `/api/auth/login`, not `/api/users/auth/login`).
The gateway therefore REWRITES the path:

    /api/users/auth/login   → USER_SERVICE_URL   /api/auth/login
    /api/career/professions → CAREER_SERVICE_URL /api/professions
    /api/reco/recommendations → RECO_API_URL     /api/recommendations
    /api/chat/chats         → CHAT_SERVICE_URL   /api/chats

i.e. strip the leading service key, keep the rest under `/api/`.

`full_path` everywhere in this module is the part AFTER the gateway's `/api/`
prefix (the `{full_path:path}` captured by the catch-all route), e.g.
`users/auth/login`.
"""
from __future__ import annotations

from app.config import settings

# Public path prefix → downstream base URL.
SERVICE_ROUTES: dict[str, str] = {
    "users": settings.USER_SERVICE_URL,
    "career": settings.CAREER_SERVICE_URL,
    "reco": settings.RECO_API_URL,
    "chat": settings.CHAT_SERVICE_URL,
}

# Human-readable names for the aggregated health check.
SERVICE_NAMES: dict[str, str] = {
    "users": "user-service",
    "career": "career-service",
    "reco": "recommendation-api",
    "chat": "chat-service",
}


def resolve_target(full_path: str) -> tuple[str, str] | None:
    """Map `<service-key>/<rest>` to `(base_url, downstream_path)`.

    Returns `None` if the first segment is not a known service.
    """
    segment, _, remainder = full_path.partition("/")
    base = SERVICE_ROUTES.get(segment)
    if base is None:
        return None
    downstream_path = f"/api/{remainder}" if remainder else "/api"
    return base.rstrip("/"), downstream_path


# --------------------------------------------------------------------------- #
#  Access policy (expressed on the gateway-facing `full_path`)
# --------------------------------------------------------------------------- #

# Public routes (no token required): registration / login / refresh, email
# verification, password reset request & perform, and reference data needed by
# the registration & profile forms before the user is logged in.
_PUBLIC_EXACT: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", "users/auth/register"),
        ("POST", "users/auth/login"),
        ("POST", "users/auth/refresh"),
        ("GET", "users/auth/verify-email"),
        ("POST", "users/auth/request-password-reset"),
        ("POST", "users/auth/reset-password"),
        ("GET", "users/industries"),
        ("GET", "users/recommendation-criteria"),
    }
)

# Public GET prefixes: anonymous browsing of the profession catalogue (FR9–FR11).
_PUBLIC_GET_PREFIXES: tuple[str, ...] = ("career/professions",)


def _matches_prefix(full_path: str, prefix: str) -> bool:
    return full_path == prefix or full_path.startswith(prefix + "/")


def is_public(method: str, full_path: str) -> bool:
    """True if the route may be reached without authentication."""
    if method == "OPTIONS":  # CORS pre-flight / probing
        return True
    if (method, full_path) in _PUBLIC_EXACT:
        return True
    if method == "GET" and any(_matches_prefix(full_path, p) for p in _PUBLIC_GET_PREFIXES):
        return True
    return False


def requires_admin(method: str, full_path: str) -> bool:
    """True if the route requires `role=admin` (in addition to authentication).

    Covers the career-service admin area: the dedicated `/admin/*` paths and any
    mutation (POST/PUT/PATCH/DELETE) of the profession catalogue.
    """
    if _matches_prefix(full_path, "career/admin"):
        return True
    if method in {"POST", "PUT", "PATCH", "DELETE"} and _matches_prefix(full_path, "career/professions"):
        return True
    return False

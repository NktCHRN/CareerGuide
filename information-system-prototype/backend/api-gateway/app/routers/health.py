"""Health checks: the gateway itself and an aggregated downstream probe."""
from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter

from app.proxy import proxy
from app.routing import SERVICE_NAMES, SERVICE_ROUTES

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "api-gateway"}


@router.get("/health/all")
async def health_all() -> dict:
    """Ping every downstream `/api/health` concurrently (status is `degraded` if any fails)."""
    results: dict[str, str] = {}

    async def ping(key: str, base_url: str) -> None:
        name = SERVICE_NAMES.get(key, key)
        try:
            resp = await proxy.client.get(
                base_url.rstrip("/") + "/api/health",
                timeout=httpx.Timeout(5.0, connect=3.0),
            )
            results[name] = "ok" if resp.is_success else f"error:{resp.status_code}"
        except httpx.RequestError:
            results[name] = "unreachable"

    await asyncio.gather(*(ping(key, url) for key, url in SERVICE_ROUTES.items()))
    overall = "ok" if all(v == "ok" for v in results.values()) else "degraded"
    return {"status": overall, "service": "api-gateway", "downstream": results}

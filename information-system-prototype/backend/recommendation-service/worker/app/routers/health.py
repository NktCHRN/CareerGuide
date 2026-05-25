"""Health endpoint — the worker's only public HTTP surface."""
from __future__ import annotations

from fastapi import APIRouter

from app.services.state import state

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict:
    """`ready` is False while the models/index are still loading on startup."""
    return {"status": "ok", "ready": state.ready}

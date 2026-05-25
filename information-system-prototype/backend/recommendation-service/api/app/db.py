"""Async SQLAlchemy 2.x engine, session factory and declarative Base.

The worker owns the `recommendationdb` schema (pgvector). recommendation-api
connects to the SAME logical DB read-only — it never runs migrations and only
issues SELECTs. Sessions are therefore opened without autoflush.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Shared declarative base class for the (read-only) models."""


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one read-only session per request."""
    async with SessionFactory() as session:
        yield session

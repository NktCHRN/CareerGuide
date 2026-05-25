"""Async-двигун SQLAlchemy 2.x, фабрика сесій і декларативний Base."""
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
    """Спільний декларативний базовий клас для моделей."""


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI-залежність: одна сесія на запит."""
    async with SessionFactory() as session:
        yield session

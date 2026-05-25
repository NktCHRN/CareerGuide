"""CareerService FastAPI application — detailed profession information (C4, table 4.2).

Source of truth for professions: seeds the full ESCO catalogue (Alembic) and
publishes `profession.upserted` / `profession.deleted` to `profession-events`.
Lifespan brings up the Kafka producer and the Redis cache; on shutdown it stops
them gracefully and releases the DB connection pool.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import engine
from app.events.producer import producer
from app.routers import health, professions
from app.services import cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("career-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("CareerService starting (APP_ENV=%s, AUTH_MODE=%s)", settings.APP_ENV, settings.AUTH_MODE)
    await producer.start()
    await cache.connect()
    try:
        yield
    finally:
        await producer.stop()
        await cache.close()
        await engine.dispose()
        logger.info("CareerService stopped")


app = FastAPI(
    title="CareerGuide — CareerService",
    description="Detailed profession information: search, browse, details, admin CRUD.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(professions.router)

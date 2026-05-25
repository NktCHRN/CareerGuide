"""RecommendationServiceAPI — synchronous profession recommendations (C4, table 4.2).

Read-only over the shared `recommendationdb` (pgvector): it ranks the worker's
precomputed `profession_vectors` against `user_vectors[user_id]` by cosine
similarity and returns paginated, filterable recommendations (port 8003). It owns
no schema/migrations and publishes nothing — the worker computes the vectors.
Lifespan brings up the Redis cache and releases the DB pool on shutdown.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import engine
from app.routers import health, recommendations
from app.services import cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("recommendation-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("RecommendationServiceAPI starting (APP_ENV=%s, AUTH_MODE=%s)", settings.APP_ENV, settings.AUTH_MODE)
    await cache.connect()
    try:
        yield
    finally:
        await cache.close()
        await engine.dispose()
        logger.info("RecommendationServiceAPI stopped")


app = FastAPI(
    title="CareerGuide — RecommendationServiceAPI",
    description="Synchronous, cosine-ranked profession recommendations over precomputed pgvector embeddings.",
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
app.include_router(recommendations.router)

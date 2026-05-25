"""UserService FastAPI application.

Lifespan brings up the Kafka producer (publishing user-events), the Kafka
consumer of the `resume-results` topic and the Redis cache; on shutdown it
stops them gracefully and releases the DB connection pool.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import engine
from app.events.consumer import run_consumer
from app.events.producer import producer
from app.routers import auth, health, meta, profile, resume
from app.services import cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("user-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("UserService старт (APP_ENV=%s, AUTH_MODE=%s)", settings.APP_ENV, settings.AUTH_MODE)
    await producer.start()
    await cache.connect()
    consumer_task = asyncio.create_task(run_consumer(), name="resume-results-consumer")
    try:
        yield
    finally:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        await producer.stop()
        await cache.close()
        await engine.dispose()
        logger.info("UserService зупинено")


app = FastAPI(
    title="CareerGuide — UserService",
    description="Керування акаунтом користувача: автентифікація, профіль, резюме.",
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
app.include_router(meta.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(resume.router)

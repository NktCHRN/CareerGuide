"""ChatService FastAPI application — the embedded profession chatbot (C4, table 4.2).

Owns `chatdb` (chats + messages) and keeps two denormalised local copies in sync
from the bus: professions (`profession-events`) and user profiles (`user-events`),
so the assistant grounds its replies in ESCO data without any synchronous call to
career-service / user-service. Replies are generated via the OpenAI API.

Lifespan: build the OpenAI client, start the two Kafka consumers as background
tasks; on shutdown cancel them, close the client and release the DB pool.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import engine
from app.events.consumer import run_profession_consumer, run_user_consumer
from app.routers import chats, health
from app.services.llm import llm

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("chat-service")

_tasks: list[asyncio.Task] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ChatService starting (APP_ENV=%s, AUTH_MODE=%s)", settings.APP_ENV, settings.AUTH_MODE)
    llm.start()
    _tasks.append(asyncio.create_task(run_profession_consumer()))
    _tasks.append(asyncio.create_task(run_user_consumer()))
    try:
        yield
    finally:
        for task in list(_tasks):
            task.cancel()
        await asyncio.gather(*_tasks, return_exceptions=True)
        await llm.close()
        await engine.dispose()
        logger.info("ChatService stopped")


app = FastAPI(
    title="CareerGuide — ChatService",
    description="Embedded profession chatbot: chats, messages and an ESCO-grounded LLM assistant.",
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
app.include_router(chats.router)

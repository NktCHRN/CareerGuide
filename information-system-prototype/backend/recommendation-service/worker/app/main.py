"""RecommendationServiceWorker — FastAPI health surface + background consumers.

The worker has no public REST API beyond `GET /api/health` (port 8005). The
heavy artifacts are loaded in a background bootstrap task so the HTTP server
binds immediately (health reports `ready=false` until loading finishes):
  • career-SBERT + CareerRNN checkpoint + industry vocab (ModelRuntime);
  • EmbeddingGemma + the ESCO skill index (EscoSkillMapper) — the slow step;
  • OpenAI resume parser (ResumeParser).
Once ready, the two Kafka consumers (profession-events, user-events) start and
the producer publishes results to resume-results.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import engine
from app.events.consumer import run_profession_consumer, run_user_consumer
from app.events.producer import producer
from app.model.runtime import ModelRuntime
from app.routers import health
from app.services.llm import ResumeParser
from app.services.state import state
from app.skill_mapping.mapper import EscoSkillMapper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("recommendation-worker")

_tasks: list[asyncio.Task] = []


async def _bootstrap() -> None:
    """Load the heavy artifacts, then start the Kafka consumers."""
    try:
        logger.info("Bootstrap: loading career-SBERT + CareerRNN checkpoint…")
        state.runtime = await asyncio.to_thread(ModelRuntime.load)
        state.parser = ResumeParser.build(state.runtime.industry_to_id)
        logger.info("Bootstrap: building EmbeddingGemma ESCO skill index (heavy)…")
        state.mapper = await asyncio.to_thread(EscoSkillMapper.build)
        logger.info("Bootstrap complete — worker is ready; starting consumers")
        _tasks.append(asyncio.create_task(run_profession_consumer()))
        _tasks.append(asyncio.create_task(run_user_consumer()))
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001
        logger.exception("Bootstrap failed — the worker will stay not-ready and consume nothing")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("RecommendationServiceWorker starting (APP_ENV=%s, device=%s)", settings.APP_ENV, settings.DEVICE)
    await producer.start()
    _tasks.append(asyncio.create_task(_bootstrap()))
    try:
        yield
    finally:
        for task in list(_tasks):
            task.cancel()
        await asyncio.gather(*_tasks, return_exceptions=True)
        await producer.stop()
        await engine.dispose()
        logger.info("RecommendationServiceWorker stopped")


app = FastAPI(
    title="CareerGuide — RecommendationServiceWorker",
    description="Background worker: profession/user semantic vectors, ESCO skill mapping, resume parsing.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health.router)

"""Process-wide singletons loaded once on startup and shared by the consumers.

Holds the heavy, long-lived objects:
  • ModelRuntime    — career-SBERT + CareerRNN checkpoint + industry vocab;
  • EscoSkillMapper — EmbeddingGemma + the prebuilt ESCO skill index;
  • ResumeParser    — OpenAI client + the industry-key hint prompt.
"""
from __future__ import annotations

import asyncio

from app.model.runtime import ModelRuntime
from app.services.llm import ResumeParser
from app.skill_mapping.mapper import EscoSkillMapper


class AppState:
    def __init__(self) -> None:
        self.runtime: ModelRuntime | None = None
        self.mapper: EscoSkillMapper | None = None
        self.parser: ResumeParser | None = None
        # Serializes heavy PyTorch/SBERT/EmbeddingGemma forward passes — the two
        # consumers run in one event loop and share these (non-thread-safe) modules,
        # so model inference must not overlap across their worker threads.
        self.inference_lock = asyncio.Lock()

    @property
    def ready(self) -> bool:
        return self.runtime is not None and self.mapper is not None and self.parser is not None


state = AppState()

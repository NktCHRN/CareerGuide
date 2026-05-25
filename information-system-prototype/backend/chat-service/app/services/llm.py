"""OpenAI wrapper for the chat assistant.

A single AsyncOpenAI client is built at startup (see the app lifespan) and reused
for every reply. The assistant is grounded in the ESCO context that
`services.chats` assembles into the system prompt; this module only forwards the
message list and returns the text. When `OPENAI_API_KEY` is missing the client
stays unavailable and `complete()` returns a friendly fallback so the rest of the
service (and the tests) still work without a key.

Streaming is intentionally omitted — for the prototype a single completion call
per message is enough (the conventions allow this).
"""
from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger("chat-service.llm")

_FALLBACK = (
    "The assistant is not configured yet (no OpenAI API key). "
    "Set OPENAI_API_KEY to enable AI replies."
)


class ChatLLM:
    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None
        self.model = settings.OPENAI_MODEL

    def start(self) -> None:
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY is empty — assistant replies are disabled (fallback only)")
            return
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info("OpenAI client ready (model=%s)", self.model)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    async def complete(self, messages: list[dict[str, str]]) -> str:
        """Generate one assistant reply for the given OpenAI-format message list."""
        if self._client is None:
            return _FALLBACK
        resp = await self._client.chat.completions.create(
            model=self.model,
            temperature=settings.OPENAI_TEMPERATURE,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            messages=messages,
        )
        return (resp.choices[0].message.content or "").strip()


# Global instance, managed in the application lifespan.
llm = ChatLLM()

"""Resume parsing via OpenAI (worker obligation #4).

Takes the plain text of a resume PDF and returns a structured profile matching
the shape user-service expects in `user.profile.parsed`:

    {name, summary, skills: [...],
     experiences: [{title, description, industry, start "M/YYYY", end "M/YYYY"|"current"}]}

`industry` is constrained to the keys of `industry_to_id` (UPPERCASE forms such
as INFORMATION-TECHNOLOGY, FINANCE) or null — these are the only values the
CareerRNN industry embedding understands. The allowed keys, enriched with their
human-readable `processed` descriptions from livecareer_resume_categories.csv,
are passed to the model as a hint, but the model must return the UPPERCASE key.
Invalid JSON is retried once; out-of-vocabulary industries are coerced to null.
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger("recommendation-worker.llm")

MAX_RESUME_CHARS = 16000  # keep prompt size bounded


class ParsedExperience(BaseModel):
    title: str = ""
    description: str | None = None
    industry: str | None = None
    start: str | None = None
    end: str | None = None


class ParsedProfile(BaseModel):
    name: str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experiences: list[ParsedExperience] = Field(default_factory=list)


def _load_industry_hints(industry_to_id: dict[str, int], categories_csv: Path) -> str:
    """Render the allowed industry keys with their `processed` descriptions as a
    hint block. Keys come from industry_to_id (authoritative); descriptions are a
    best-effort lookup from the LiveCareer categories CSV."""
    descriptions: dict[str, str] = {}
    try:
        with open(categories_csv, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                original = (row.get("original") or "").strip()
                processed = (row.get("processed") or "").strip()
                if original:
                    descriptions[original] = processed
    except FileNotFoundError:
        logger.warning("LiveCareer categories CSV not found at %s — hints will be keys only", categories_csv)

    lines: list[str] = []
    for key in industry_to_id:
        if key == "<unk>":
            continue
        desc = descriptions.get(key)
        lines.append(f"- {key} ({desc})" if desc else f"- {key}")
    return "\n".join(lines)


_SYSTEM_PROMPT = """You are a resume parser. Extract a structured professional \
profile from the resume text and return STRICT JSON only, with this exact shape:

{
  "name": string | null,
  "summary": string | null,
  "skills": string[],
  "experiences": [
    {
      "title": string,
      "description": string | null,
      "industry": string | null,
      "start": string | null,   // "M/YYYY", e.g. "5/2019"
      "end": string | null      // "M/YYYY" or "current"
    }
  ]
}

Rules:
- "skills" are short free-text skill names (e.g. "python", "project management").
- For each experience, "industry" MUST be exactly one of the allowed UPPERCASE \
keys below, or null if none fits. Never invent a key; never return the \
description text — return the KEY.
- Dates use the "M/YYYY" format. Use "current" for an ongoing role's end.
- Return JSON only, no prose, no markdown fences.

Allowed industry keys (key (description)):
{industry_hints}"""


class ResumeParser:
    def __init__(self, client: AsyncOpenAI, model: str, allowed: set[str], system_prompt: str) -> None:
        self.client = client
        self.model = model
        self.allowed = allowed
        self.system_prompt = system_prompt

    @classmethod
    def build(cls, industry_to_id: dict[str, int]) -> "ResumeParser":
        hints = _load_industry_hints(industry_to_id, Path(settings.LIVECAREER_CATEGORIES_PATH))
        allowed = {k for k in industry_to_id if k != "<unk>"}
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        system_prompt = _SYSTEM_PROMPT.replace("{industry_hints}", hints)
        return cls(client, settings.OPENAI_MODEL, allowed, system_prompt)

    def _coerce(self, raw: dict) -> dict:
        profile = ParsedProfile.model_validate(raw)
        out = profile.model_dump()
        for exp in out["experiences"]:
            ind = exp.get("industry")
            if ind is not None:
                ind = str(ind).strip().upper()
                exp["industry"] = ind if ind in self.allowed else None
        out["skills"] = [s.strip() for s in out["skills"] if isinstance(s, str) and s.strip()]
        return out

    async def _call(self, text: str, *, strict_retry: bool) -> dict:
        user_content = text[:MAX_RESUME_CHARS]
        if strict_retry:
            user_content = "Return ONLY valid JSON in the required shape.\n\n" + user_content
        resp = await self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)

    async def parse(self, text: str) -> dict | None:
        """Parse resume text into a profile dict, or None if parsing fails twice."""
        if not text.strip():
            logger.warning("Empty resume text — nothing to parse")
            return None
        for strict_retry in (False, True):
            try:
                raw = await self._call(text, strict_retry=strict_retry)
                return self._coerce(raw)
            except Exception:  # noqa: BLE001 — invalid JSON / schema / API error
                logger.warning("Resume parse attempt failed (strict_retry=%s)", strict_retry)
        logger.error("Resume parsing failed after retry")
        return None

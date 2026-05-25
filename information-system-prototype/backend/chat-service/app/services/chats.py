"""Chat business logic: load the local context and assemble the LLM prompt.

The assistant is a RAG bot limited to ESCO: its system prompt is built from the
local denormalised copies — the bound profession (`cached_professions`, filled
from `profession.upserted`) and the caller's profile (`cached_users`, filled from
`user.profile.updated`). The model is instructed to answer strictly from this
context and never to invent professions outside ESCO.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import CachedProfession, CachedUser, Message

_BASE_SYSTEM_PROMPT = """You are CareerGuide's assistant, a helpful career-guidance \
chatbot that talks about professions. You help the user with four kinds of tasks:
  1. explaining the details of a chosen profession;
  2. recommending ESCO professions that fit the user's profile;
  3. building a learning plan to grow into a chosen profession;
  4. drafting a resume tailored to a chosen profession.

Grounding rules:
- Base your answers on the ESCO data provided in the context below. Do NOT invent \
professions, occupations or skills that are not part of ESCO; if you are unsure, \
say so and suggest the user browse the catalogue.
- When profession context is provided, ground profession details, learning plans \
and resumes in its description and ESCO knowledge skills.
- When user-profile context is provided, personalise your answers (skills gaps, \
relevant experience, tailored resume).
- Be concise, practical and encouraging. Reply in the language the user writes in.\
"""

_NO_PROFESSION = "No specific profession is attached to this chat."
_NO_USER = "No user profile is available yet."


def _format_profession(p: CachedProfession) -> str:
    lines = [f"Profession (ESCO): {p.preferred_label or 'unknown'}"]
    if p.esco_uri:
        lines.append(f"ESCO URI: {p.esco_uri}")
    if p.education_level:
        lines.append(f"Typical education level: {p.education_level}")
    if p.description:
        lines.append(f"Description: {p.description}")
    labels = list(p.knowledge_skill_labels or [])
    if labels:
        lines.append("ESCO knowledge skills: " + ", ".join(labels))
    return "\n".join(lines)


def _format_user(u: CachedUser) -> str:
    lines = ["User profile:"]
    if u.name:
        lines.append(f"Name: {u.name}")
    if u.summary:
        lines.append(f"Summary: {u.summary}")
    skills = list(u.skills or [])
    if skills:
        lines.append("Skills: " + ", ".join(str(s) for s in skills))
    experiences = list(u.experiences or [])
    if experiences:
        lines.append("Experience:")
        for exp in experiences:
            if not isinstance(exp, dict):
                continue
            title = exp.get("title") or "role"
            industry = exp.get("industry")
            start = exp.get("start")
            end = exp.get("end")
            period = f" ({start}–{end})" if start or end else ""
            ind = f" [{industry}]" if industry else ""
            head = f"- {title}{ind}{period}"
            desc = exp.get("description")
            lines.append(f"{head}: {desc}" if desc else head)
    return "\n".join(lines)


def build_system_prompt(
    profession: CachedProfession | None, user: CachedUser | None
) -> str:
    profession_block = _format_profession(profession) if profession else _NO_PROFESSION
    user_block = _format_user(user) if user else _NO_USER
    return (
        f"{_BASE_SYSTEM_PROMPT}\n\n"
        f"=== Profession context ===\n{profession_block}\n\n"
        f"=== User context ===\n{user_block}"
    )


def to_openai_messages(
    system_prompt: str,
    history: list[Message],
    new_user_content: str,
) -> list[dict[str, str]]:
    """[system] + the last CHAT_HISTORY_LIMIT stored messages + the new user turn."""
    recent = history[-settings.CHAT_HISTORY_LIMIT :] if settings.CHAT_HISTORY_LIMIT else history
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for m in recent:
        # Stored messages are only `user` / `assistant`; system context is rebuilt each turn.
        if m.role in ("user", "assistant"):
            messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": new_user_content})
    return messages


async def get_cached_profession(
    session: AsyncSession, profession_id: int | None
) -> CachedProfession | None:
    if profession_id is None:
        return None
    return await session.get(CachedProfession, profession_id)


async def get_cached_user(session: AsyncSession, user_id: int) -> CachedUser | None:
    return await session.get(CachedUser, user_id)


async def profession_label(session: AsyncSession, profession_id: int) -> str | None:
    row = await session.execute(
        select(CachedProfession.preferred_label).where(
            CachedProfession.profession_id == profession_id
        )
    )
    return row.scalar_one_or_none()

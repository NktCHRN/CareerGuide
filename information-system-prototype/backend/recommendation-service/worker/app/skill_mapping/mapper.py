"""Online ESCO skill mapper (worker obligation #3).

Wraps the reusable v3 pipeline (`app.skill_mapping.pipeline`) for a single user
profile instead of a wide CSV batch:

  • the EmbeddingGemma index over the full ESCO skill catalogue is built ONCE on
    startup (`EscoSkillMapper.build`) and kept in memory for the service lifetime;
  • `map_user_skills(profile)` takes one profile, drops adjective fragments,
    short-circuits known inputs, embeds the rest in a single batched call, runs
    `map_skill` per skill, then dedupes and resolves labels.

Only the INPUT changed — the retrieval / hybrid-weight / domain-filter /
short-circuit / threshold logic is reused unchanged from the original script.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from sentence_transformers import SentenceTransformer

from app.config import settings
from app.model.runtime import resolve_device
from app.skill_mapping import pipeline as pl

logger = logging.getLogger("recommendation-worker.skill-mapping")


def build_profile_context(profile: dict, current_skill: str, all_skills: list[str]) -> str:
    """Profile-shaped analogue of the script's `build_context` (same field
    priority and char budget): summary → experiences (title: description) →
    other skills. Used as the disambiguating context for the domain filter."""
    parts: list[str] = []

    summary = (profile.get("summary") or "").strip()
    if summary:
        parts.append(f"Summary: {summary[:pl.SUMMARY_CHARS]}")

    experiences: list[str] = []
    for exp in profile.get("experiences") or []:
        title = (exp.get("title") or "").strip()
        if not title:
            continue
        entry = title
        desc = (exp.get("description") or "").strip()
        if desc:
            entry += f": {desc[:pl.DESC_CHARS_EACH]}"
        experiences.append(entry)
    if experiences:
        parts.append("Experience: " + " | ".join(experiences[:pl.MAX_EXPERIENCES]))

    others = [s for s in all_skills if s != current_skill]
    if others:
        parts.append(f"Other skills: {', '.join(others[:pl.MAX_OTHER_SKILLS])}")

    return ". ".join(parts)[:pl.CONTEXT_CHARS]


class EscoSkillMapper:
    """ESCO skill catalogue + EmbeddingGemma index, built once on startup."""

    def __init__(self, model: SentenceTransformer, index: pl.EscoIndex) -> None:
        self.model = model
        self.index = index

    @classmethod
    def build(cls) -> "EscoSkillMapper":
        # EmbeddingGemma is gated — SentenceTransformer / huggingface_hub read the
        # token from these env vars when downloading the weights.
        if settings.HF_TOKEN:
            os.environ.setdefault("HF_TOKEN", settings.HF_TOKEN)
            os.environ.setdefault("HUGGING_FACE_HUB_TOKEN", settings.HF_TOKEN)

        csv_path = Path(settings.ESCO_SKILLS_CSV)
        logger.info("Loading ESCO skill catalogue from %s …", csv_path)
        catalog = pl.load_esco_catalog(csv_path)
        logger.info(
            "ESCO catalogue: %d concepts, %d label entries, %d concat docs",
            len(catalog.unique_uris), len(catalog.label_texts), len(catalog.concat_texts),
        )

        device = str(resolve_device(settings.DEVICE))
        logger.info("Loading skill-embedding model '%s' on %s …", settings.ESCO_SKILL_EMBED_MODEL, device)
        model = SentenceTransformer(settings.ESCO_SKILL_EMBED_MODEL, device=device)

        logger.info("Embedding ESCO label corpus (multi-vector) — this is the heavy startup step …")
        label_emb = pl.embed_corpus(catalog.label_texts, model, batch_size=settings.ESCO_EMBED_BATCH_SIZE)
        logger.info("Embedding ESCO concat corpus (one doc per URI) …")
        concat_emb = pl.embed_corpus(catalog.concat_texts, model, batch_size=settings.ESCO_EMBED_BATCH_SIZE)

        blacklist = pl.resolve_blacklist_indices(catalog.unique_uris, pl.HARD_BLACKLIST)
        index = pl.EscoIndex(
            catalog=catalog,
            label_emb=label_emb,
            concat_emb=concat_emb,
            blacklist_uri_indices=blacklist,
        )
        logger.info("ESCO skill index ready (label_emb=%s, concat_emb=%s)", label_emb.shape, concat_emb.shape)
        return cls(model, index)

    def map_user_skills(self, profile: dict) -> list[dict]:
        """Map the user's free-text skills to ESCO. Returns a deduplicated list of
        `{"skill_uri": ..., "label": ...}` (the payload shape for
        `user.esco_skills.mapped`)."""
        raw = profile.get("skills") or []
        unique = list(dict.fromkeys(s.strip() for s in raw if s and s.strip()))
        if not unique:
            return []

        # One batched query encode for every skill that is neither an adjective
        # fragment nor short-circuited (mirrors the per-chunk encode in the script).
        to_embed: list[str] = []
        embed_pos: dict[str, int] = {}
        for skill in unique:
            if pl.is_adjective_fragment(skill):
                continue
            if pl.short_circuit_uri(skill) is not None:
                continue
            if skill not in embed_pos:
                embed_pos[skill] = len(to_embed)
                to_embed.append(skill)
        query_embs = pl.encode_queries(to_embed, self.model, settings.ESCO_EMBED_BATCH_SIZE) if to_embed else None

        uri_to_label = self.index.catalog.uri_to_label
        mapped: list[dict] = []
        seen: set[str] = set()
        for skill in unique:
            if pl.is_adjective_fragment(skill):
                continue
            override = pl.short_circuit_uri(skill)
            if override is not None:
                uri = override
            else:
                assert query_embs is not None
                context = build_profile_context(profile, skill, unique)
                uri = pl.map_skill(
                    skill,
                    context,
                    query_embs[embed_pos[skill]],
                    self.index,
                    pl.DEFAULT_TOP_K,
                    threshold=settings.COSINE_THRESHOLD,
                    domain_filter_enabled=True,
                    identifier=None,
                    log_file=None,
                )
            if uri is None or uri in seen:
                continue
            seen.add(uri)
            mapped.append({"skill_uri": uri, "label": uri_to_label.get(uri, "")})
        return mapped

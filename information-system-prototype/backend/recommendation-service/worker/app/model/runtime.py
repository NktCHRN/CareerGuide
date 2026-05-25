"""CareerRNN + career-SBERT runtime: profession and user vector computation.

Reproduces the notebook preprocessing exactly:
  • role text      : "role: {title} \\n description: {description}"
  • profession text: "esco role: {label} \\n alt labels: {alts} \\n description: {desc}"
                     (alt-labels line dropped when there are none)
  • skill text     : "skill: {label}"
  • months feature : log1p(months_of_experience); raw months recovered with
                     expm1 inside the model. "current" → start + 1 year, capped
                     at (2021, 8), matching DATE_CAP from the notebook.
  • industry       : industry_to_id.get(<UPPERCASE key>, industry_to_id["<unk>"])
  • skill vector   : simple mean of SBERT("skill: …") over the user's RAW skills
                     (NO normalization); zero vector when the user has no skills.

SBERT embeddings fed to the model are NOT normalized (matches `model.encode(...)`
in the notebook). Only the final CareerRNN output and the profession vectors are
L2-normalized (matches the F.normalize at retrieval/index time).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.model.architecture import CareerRNN

logger = logging.getLogger("recommendation-worker.model")

DATE_CAP = (2021, 8)  # from the notebook (LiveCareer/Decorte data horizon)


def resolve_device(pref: str) -> torch.device:
    if pref == "cpu":
        return torch.device("cpu")
    if pref == "cuda":
        return torch.device("cuda")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _parse_month_year(value: str | None) -> tuple[int, int] | None:
    """Parse a "M/YYYY" string into (year, month). Returns None if unparseable."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if not value or value.lower() == "current":
        return None
    try:
        m, y = value.split("/")
        return (int(y), int(m))
    except (ValueError, TypeError):
        return None


def compute_months(start: str | None, end: str | None, given: Any = None) -> float:
    """Months of experience, preferring the precomputed value from the event."""
    if isinstance(given, (int, float)) and given is not None:
        return float(given)
    sy_m = _parse_month_year(start)
    if sy_m is None:
        return 0.0
    sy, sm = sy_m
    if end and isinstance(end, str) and end.strip().lower() == "current":
        ey, em = sy + 1, sm
        if (ey, em) > DATE_CAP:
            ey, em = DATE_CAP
    else:
        ey_m = _parse_month_year(end)
        if ey_m is None:
            return 0.0
        ey, em = ey_m
    return float((ey - sy) * 12 + (em - sm))


def _sort_experiences(experiences: list[dict]) -> list[dict]:
    """Chronological by `start`; experiences without a parseable date keep their
    original relative order and follow the dated ones (stable sort)."""
    def key(item: tuple[int, dict]):
        idx, exp = item
        d = _parse_month_year(exp.get("start"))
        if d is None:
            return (1, 0, 0, idx)
        return (0, d[0], d[1], idx)

    return [exp for _, exp in sorted(enumerate(experiences), key=key)]


def profession_text(payload: dict) -> str:
    """Build the `ESCO_experience` text used as the profession's semantic target."""
    label = (payload.get("preferred_label") or "").strip()
    description = (payload.get("description") or "").strip()
    alts = [a.strip() for a in (payload.get("alt_labels") or []) if a and a.strip()]
    if alts:
        return (
            f"esco role: {label} \n"
            f" alt labels: {', '.join(alts)} \n"
            f" description: {description}"
        )
    return f"esco role: {label} \n description: {description}"


class ModelRuntime:
    """Holds the loaded career-SBERT model, CareerRNN checkpoint and vocab."""

    def __init__(
        self,
        sbert: SentenceTransformer,
        model: CareerRNN,
        industry_to_id: dict[str, int],
        device: torch.device,
    ) -> None:
        self.sbert = sbert
        self.model = model
        self.industry_to_id = industry_to_id
        self.unk_industry = industry_to_id["<unk>"]
        self.device = device

    # --- loading -----------------------------------------------------------

    @classmethod
    def load(cls) -> "ModelRuntime":
        device = resolve_device(settings.DEVICE)
        logger.info("Loading career-SBERT '%s' on %s …", settings.SBERT_MODEL, device)
        sbert = SentenceTransformer(settings.SBERT_MODEL, device=str(device))

        vocab_path = Path(settings.INDUSTRY_VOCAB_PATH)
        with open(vocab_path, encoding="utf-8") as f:
            industry_to_id: dict[str, int] = json.load(f)
        if "<unk>" not in industry_to_id:
            raise ValueError(
                f"'<unk>' sentinel missing from {vocab_path} — the industry_emb "
                "layer size would not match the checkpoint."
            )
        n_industries = len(industry_to_id)
        logger.info("industry_to_id loaded: n_industries=%d", n_industries)

        model = CareerRNN(
            input_dim=settings.EMBEDDING_DIM,
            hidden_dim=settings.HIDDEN,
            output_dim=settings.EMBEDDING_DIM,
            dropout=settings.DROPOUT,
            months_dim=settings.MONTHS_DIM,
            n_industries=n_industries,
            industry_dim=settings.INDUSTRY_DIM,
            skill_input_dim=settings.SKILLS_DIM_IN,
            skill_dim=settings.SKILL_DIM,
        ).to(device)
        state = torch.load(settings.MODEL_CKPT_PATH, map_location=device, weights_only=True)
        model.load_state_dict(state)
        model.eval()
        logger.info("CareerRNN checkpoint loaded from %s", settings.MODEL_CKPT_PATH)
        return cls(sbert, model, industry_to_id, device)

    # --- SBERT helpers -----------------------------------------------------

    def _encode(self, texts: list[str]) -> torch.Tensor:
        """career-SBERT encode WITHOUT normalization, on the model device."""
        return self.sbert.encode(
            texts,
            convert_to_tensor=True,
            normalize_embeddings=False,
            show_progress_bar=False,
            device=str(self.device),
        ).to(self.device)

    def embed_profession_texts(self, texts: list[str]) -> list[list[float]]:
        """L2-normalized career-SBERT vectors for a batch of profession texts."""
        if not texts:
            return []
        with torch.no_grad():
            embs = self._encode(texts)
            embs = F.normalize(embs, dim=-1)
        return embs.cpu().tolist()

    # --- user vector -------------------------------------------------------

    def _industry_id(self, industry: str | None) -> int:
        if not industry:
            return self.unk_industry
        if industry in self.industry_to_id:
            return self.industry_to_id[industry]
        return self.industry_to_id.get(industry.upper(), self.unk_industry)

    def _skill_vector(self, skills: list[str]) -> torch.Tensor:
        """Simple mean of SBERT('skill: …') over RAW user skills (no normalization);
        zero vector when there are no skills (matches ZERO_SKILL_EMB)."""
        clean = [s.strip() for s in (skills or []) if s and s.strip()]
        if not clean:
            return torch.zeros(settings.SKILLS_DIM_IN, device=self.device)
        with torch.no_grad():
            embs = self._encode([f"skill: {s}" for s in clean])
        return embs.mean(dim=0)

    @torch.no_grad()
    def build_user_vector(self, profile: dict) -> list[float] | None:
        """Run the CareerRNN over the user's career history → normalized 768-vector.
        Returns None when the user has fewer than one experience."""
        experiences = _sort_experiences(list(profile.get("experiences") or []))
        if len(experiences) < 1:
            return None

        role_texts = [
            f"role: {(e.get('title') or '').strip()} \n description: {(e.get('description') or '').strip()}"
            for e in experiences
        ]
        role_embs = self._encode(role_texts)  # [L, D]

        months = torch.tensor(
            [
                torch.log1p(torch.tensor(
                    compute_months(e.get("start"), e.get("end"), e.get("months_of_experience"))
                )).item()
                for e in experiences
            ],
            dtype=torch.float32,
            device=self.device,
        )
        inds = torch.tensor(
            [self._industry_id(e.get("industry")) for e in experiences],
            dtype=torch.long,
            device=self.device,
        )
        skills = self._skill_vector(profile.get("skills") or [])
        summary_emb = self._encode([(profile.get("summary") or "")])[0]  # [D]

        padded = role_embs.unsqueeze(0)            # [1, L, D]
        months_b = months.unsqueeze(0)             # [1, L]
        inds_b = inds.unsqueeze(0)                 # [1, L]
        skills_b = skills.unsqueeze(0)             # [1, D]
        summary_b = summary_emb.unsqueeze(0)       # [1, D]
        lengths = torch.tensor([len(experiences)], dtype=torch.long, device=self.device)

        out = self.model(padded, months_b, inds_b, skills_b, summary_b, lengths)
        out = F.normalize(out, dim=-1)
        return out[0].cpu().tolist()

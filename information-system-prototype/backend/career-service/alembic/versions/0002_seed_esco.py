"""seed ESCO catalogue (occupations, skills, knowledge relations)

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-25

Reads the ESCO CSVs from `settings.ESCO_DATA_DIR` (default ./data/esco, mounted
to /app/data/esco in Docker):
  • occupations_en.csv               → professions (status == 'released'); non-ESCO fields stay NULL
  • skills_en.csv                    → skills (full reference dictionary)
  • occupationSkillRelations_en.csv  → profession_skills (skillType == 'knowledge' only)

Idempotent: if `professions` already has rows the seeding is skipped. Large CSVs
are inserted in batches.
"""
from __future__ import annotations

import csv
import logging
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.config import settings

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.seed_esco")

# Some ESCO description/label fields are long — raise the CSV field limit.
csv.field_size_limit(10_000_000)

# Lightweight table definitions for op.bulk_insert (typed so JSONB serializes).
_professions_tbl = sa.table(
    "professions",
    sa.column("esco_uri", sa.String),
    sa.column("esco_code", sa.String),
    sa.column("isco_group", sa.Integer),
    sa.column("preferred_label", sa.String),
    sa.column("description", sa.Text),
    sa.column("alt_labels", postgresql.JSONB),
)
_skills_tbl = sa.table(
    "skills",
    sa.column("skill_uri", sa.String),
    sa.column("label", sa.String),
    sa.column("description", sa.Text),
    sa.column("skill_type", sa.String),
    sa.column("reuse_level", sa.String),
)
_profession_skills_tbl = sa.table(
    "profession_skills",
    sa.column("profession_id", sa.BigInteger),
    sa.column("skill_uri", sa.String),
    sa.column("relation_type", sa.String),
)


def _path(name: str) -> str:
    return os.path.join(settings.ESCO_DATA_DIR, name)


def _trunc(value: str | None, length: int) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return value[:length]


def _split_alt_labels(raw: str | None) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    for line in raw.split("\n"):
        line = line.strip()
        if line:
            out.append(line[:512])
    return out


def _to_int(value: str | None) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _bulk_insert(table, rows: list[dict], batch: int = 2000) -> int:
    total = 0
    for i in range(0, len(rows), batch):
        op.bulk_insert(table, rows[i : i + batch])
        total += len(rows[i : i + batch])
    return total


def _seed_professions() -> None:
    rows: list[dict] = []
    seen: set[str] = set()  # ESCO data may repeat a conceptUri — keep the first
    with open(_path("occupations_en.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("status") or "").strip() != "released":
                continue
            uri = _trunc(row.get("conceptUri"), 512)
            label = _trunc(row.get("preferredLabel"), 512)
            if not uri or not label or uri in seen:
                continue
            seen.add(uri)
            rows.append(
                {
                    "esco_uri": uri,
                    "esco_code": _trunc(row.get("code"), 64),
                    "isco_group": _to_int(row.get("iscoGroup")),
                    "preferred_label": label,
                    "description": (row.get("description") or "").strip() or None,
                    "alt_labels": _split_alt_labels(row.get("altLabels")),
                }
            )
    inserted = _bulk_insert(_professions_tbl, rows, batch=1000)
    logger.info("seeded professions: %d", inserted)


def _seed_skills() -> None:
    rows: list[dict] = []
    seen: set[str] = set()  # skills_en.csv contains duplicate conceptUri rows — keep the first
    with open(_path("skills_en.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            uri = _trunc(row.get("conceptUri"), 512)
            label = _trunc(row.get("preferredLabel"), 512)
            if not uri or not label or uri in seen:
                continue
            seen.add(uri)
            rows.append(
                {
                    "skill_uri": uri,
                    "label": label,
                    "description": (row.get("description") or "").strip() or None,
                    "skill_type": _trunc(row.get("skillType"), 64),
                    "reuse_level": _trunc(row.get("reuseLevel"), 64),
                }
            )
    inserted = _bulk_insert(_skills_tbl, rows, batch=2000)
    logger.info("seeded skills: %d", inserted)


def _seed_profession_skills(bind) -> None:
    # Map ESCO occupation URI → profession id.
    uri_to_id = {
        uri: pid
        for pid, uri in bind.execute(sa.text("SELECT id, esco_uri FROM professions")).all()
    }
    seen: set[tuple[int, str]] = set()
    rows: list[dict] = []
    with open(_path("occupationSkillRelations_en.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("skillType") or "").strip() != "knowledge":
                continue
            pid = uri_to_id.get((row.get("occupationUri") or "").strip())
            skill_uri = _trunc(row.get("skillUri"), 512)
            if pid is None or not skill_uri:
                continue
            key = (pid, skill_uri)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "profession_id": pid,
                    "skill_uri": skill_uri,
                    "relation_type": (row.get("relationType") or "essential").strip() or "essential",
                }
            )
    inserted = _bulk_insert(_profession_skills_tbl, rows, batch=5000)
    logger.info("seeded profession_skills (knowledge): %d", inserted)


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(sa.text("SELECT count(*) FROM professions")).scalar()
    if existing and int(existing) > 0:
        logger.info("professions already populated (%s rows) — skipping ESCO seeding", existing)
        return

    _seed_professions()
    _seed_skills()
    _seed_profession_skills(bind)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM profession_skills"))
    bind.execute(sa.text("DELETE FROM skills"))
    bind.execute(sa.text("DELETE FROM professions"))

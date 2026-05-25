"""initial schema (careerdb)

Revision ID: 0001
Revises:
Create Date: 2026-05-25
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Trigram extension for fast ILIKE search on preferred_label.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "professions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("esco_uri", sa.String(length=512), nullable=True),
        sa.Column("esco_code", sa.String(length=64), nullable=True),
        sa.Column("isco_group", sa.Integer(), nullable=True),
        sa.Column("preferred_label", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("alt_labels", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("riasec_type", sa.String(length=16), nullable=True),
        sa.Column("professional_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("work_style", sa.String(length=255), nullable=True),
        sa.Column("education_level", sa.String(length=255), nullable=True),
        sa.Column("avg_salary", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("vacancies_local", sa.Integer(), nullable=True),
        sa.Column("vacancies_international", sa.Integer(), nullable=True),
        sa.Column("responsibilities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("photo_key", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("esco_uri", name="uq_professions_esco_uri"),
    )
    op.create_index("ix_professions_esco_code", "professions", ["esco_code"])
    op.create_index("ix_professions_isco_group", "professions", ["isco_group"])
    op.create_index("ix_professions_preferred_label", "professions", ["preferred_label"])
    op.create_index(
        "ix_professions_preferred_label_trgm",
        "professions",
        ["preferred_label"],
        postgresql_using="gin",
        postgresql_ops={"preferred_label": "gin_trgm_ops"},
    )

    op.create_table(
        "skills",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("skill_uri", sa.String(length=512), nullable=False),
        sa.Column("label", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("skill_type", sa.String(length=64), nullable=True),
        sa.Column("reuse_level", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_uri", name="uq_skills_skill_uri"),
    )
    op.create_index("ix_skills_skill_uri", "skills", ["skill_uri"])

    op.create_table(
        "profession_skills",
        sa.Column("profession_id", sa.BigInteger(), nullable=False),
        sa.Column("skill_uri", sa.String(length=512), nullable=False),
        sa.Column("relation_type", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["profession_id"], ["professions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("profession_id", "skill_uri"),
    )
    op.create_index("ix_profession_skills_skill_uri", "profession_skills", ["skill_uri"])


def downgrade() -> None:
    op.drop_index("ix_profession_skills_skill_uri", table_name="profession_skills")
    op.drop_table("profession_skills")
    op.drop_index("ix_skills_skill_uri", table_name="skills")
    op.drop_table("skills")
    op.drop_index("ix_professions_preferred_label_trgm", table_name="professions")
    op.drop_index("ix_professions_preferred_label", table_name="professions")
    op.drop_index("ix_professions_isco_group", table_name="professions")
    op.drop_index("ix_professions_esco_code", table_name="professions")
    op.drop_table("professions")

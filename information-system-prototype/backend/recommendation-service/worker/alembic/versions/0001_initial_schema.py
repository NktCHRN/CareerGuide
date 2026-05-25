"""initial schema (recommendationdb, pgvector)

Revision ID: 0001
Revises:
Create Date: 2026-05-25
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VECTOR_DIM = 768


def upgrade() -> None:
    # The shared infra init script already enables pgvector in recommendationdb;
    # this keeps the migration self-contained / idempotent.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "profession_vectors",
        sa.Column("profession_id", sa.BigInteger(), nullable=False),
        sa.Column("esco_uri", sa.String(length=512), nullable=True),
        sa.Column("vector", Vector(VECTOR_DIM), nullable=False),
        sa.Column("preferred_label", sa.String(length=512), nullable=True),
        sa.Column("education_level", sa.String(length=255), nullable=True),
        sa.Column("avg_salary", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("vacancies_local", sa.Integer(), nullable=True),
        sa.Column("vacancies_international", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("profession_id"),
        sa.UniqueConstraint("esco_uri", name="uq_profession_vectors_esco_uri"),
    )

    op.create_table(
        "user_vectors",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("vector", Vector(VECTOR_DIM), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # Approximate nearest-neighbour indexes for cosine similarity search
    # (recommendation-api ranks professions for a user by cosine distance).
    op.execute(
        "CREATE INDEX ix_profession_vectors_vector_hnsw "
        "ON profession_vectors USING hnsw (vector vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_user_vectors_vector_hnsw "
        "ON user_vectors USING hnsw (vector vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_vectors_vector_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_profession_vectors_vector_hnsw")
    op.drop_table("user_vectors")
    op.drop_table("profession_vectors")

"""READ-ONLY SQLAlchemy models for `recommendationdb` (pgvector).

These mirror the tables the recommendation-WORKER owns and migrates; this
service only SELECTs from them and never creates/alters them (no Alembic here).
Keep the columns in sync with `worker/app/models.py`.

Two semantic-vector tables, both 768-dimensional and L2-normalized:
  • profession_vectors — career-SBERT embedding of the profession text, plus
    denormalized fields recommendation-api filters/sorts on;
  • user_vectors — the CareerRNN output for the user's career history.
"""
from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

VECTOR_DIM = 768


class ProfessionVector(Base):
    __tablename__ = "profession_vectors"

    profession_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    esco_uri: Mapped[str | None] = mapped_column(String(512), unique=True, nullable=True)
    vector: Mapped[list[float]] = mapped_column(Vector(VECTOR_DIM), nullable=False)

    # Denormalized fields for recommendation-api filters/sorting (no career-service call).
    preferred_label: Mapped[str | None] = mapped_column(String(512), nullable=True)
    education_level: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avg_salary: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    vacancies_local: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vacancies_international: Mapped[int | None] = mapped_column(Integer, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )


class UserVector(Base):
    __tablename__ = "user_vectors"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vector: Mapped[list[float]] = mapped_column(Vector(VECTOR_DIM), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

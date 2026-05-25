"""SQLAlchemy models for the `careerdb` database.

The professions catalogue is seeded from the ESCO dataset (Alembic data
migration). Fields outside ESCO (`riasec_type`, `professional_values`,
`work_style`, `education_level`, `avg_salary`, `vacancies_*`,
`responsibilities`) are nullable and stay `NULL` after seeding — an admin fills
them in later. Only `skillType == 'knowledge'` relations are stored in
`profession_skills`.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Profession(Base):
    __tablename__ = "professions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # ESCO fields (filled in on seeding).
    esco_uri: Mapped[str | None] = mapped_column(String(512), unique=True, nullable=True)
    esco_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    isco_group: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    preferred_label: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    alt_labels: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Non-ESCO fields — nullable; NULL after seeding (an admin fills them later).
    riasec_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    professional_values: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    work_style: Mapped[str | None] = mapped_column(String(255), nullable=True)
    education_level: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avg_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    vacancies_local: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vacancies_international: Mapped[int | None] = mapped_column(Integer, nullable=True)
    responsibilities: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Explicit photo key (optional); when NULL the photo is resolved by id in S3.
    photo_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    skills: Mapped[list["ProfessionSkill"]] = relationship(
        back_populates="profession",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Skill(Base):
    """ESCO skills reference (the full `skills_en.csv` dictionary)."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    skill_uri: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reuse_level: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ProfessionSkill(Base):
    """Knowledge-type ESCO relations only (`essential` | `optional`)."""

    __tablename__ = "profession_skills"

    profession_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("professions.id", ondelete="CASCADE"), primary_key=True
    )
    skill_uri: Mapped[str] = mapped_column(String(512), primary_key=True, index=True)
    relation_type: Mapped[str] = mapped_column(String(16), nullable=False)  # essential | optional

    profession: Mapped[Profession] = relationship(back_populates="skills")

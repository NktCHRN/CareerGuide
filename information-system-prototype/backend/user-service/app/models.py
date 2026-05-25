"""SQLAlchemy models for the `userdb` database."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    profile: Mapped["Profile"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    hobbies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    education: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    riasec_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    professional_values: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    work_style: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recommendation_criteria: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=lambda: ["experience"]
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="profile")
    experiences: Mapped[list["ProfileExperience"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="ProfileExperience.position",
    )
    esco_skills: Mapped[list["EscoSkill"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class ProfileExperience(Base):
    __tablename__ = "profile_experiences"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("profiles.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # industry_to_id key in UPPERCASE form (e.g. INFORMATION-TECHNOLOGY) or NULL.
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start: Mapped[str | None] = mapped_column(String(16), nullable=True)  # "M/YYYY"
    end: Mapped[str | None] = mapped_column(  # "M/YYYY" | "current"
        "end", String(16), nullable=True
    )
    months_of_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    profile: Mapped[Profile] = relationship(back_populates="experiences")


class EscoSkill(Base):
    """User skills mapped to ESCO (populated by the worker via an event)."""

    __tablename__ = "esco_skills"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("profiles.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)

    profile: Mapped[Profile] = relationship(back_populates="esco_skills")


class EmailToken(Base):
    __tablename__ = "email_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # verify | reset
    token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

"""seed admin + demo user (idempotent, from .env)

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-25
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.config import settings
from app.security import hash_password
from app.utils import compute_months_of_experience

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Demo profile for SEED_USER — so there is input data for recommendations right away.
DEMO_SUMMARY = (
    "Backend-розробник із 5+ роками досвіду побудови RESTful-сервісів на Python. "
    "Проєктую мікросервісну архітектуру, працюю з PostgreSQL, Kafka та хмарною "
    "інфраструктурою. Цікавлять ролі з більшою технічною відповідальністю."
)
DEMO_SKILLS = ["Python", "FastAPI", "SQL", "PostgreSQL", "Docker", "Kafka", "REST API"]
DEMO_HOBBIES = ["open-source", "шахи", "велоспорт"]
DEMO_EXPERIENCES = [
    {
        "title": "Backend Developer",
        "description": "Розробка та підтримка REST API на FastAPI, інтеграції з PostgreSQL і Redis.",
        "industry": "INFORMATION-TECHNOLOGY",
        "start": "5/2019",
        "end": "8/2021",
    },
    {
        "title": "Senior Backend Engineer",
        "description": "Проєктування мікросервісів, подієва взаємодія через Kafka, менторство.",
        "industry": "INFORMATION-TECHNOLOGY",
        "start": "9/2021",
        "end": "current",
    },
]


def _account_exists(bind, email: str) -> int | None:
    return bind.execute(sa.text("SELECT id FROM users WHERE email = :email"), {"email": email}).scalar()


def _insert_user(bind, *, email: str, password: str, role: str, email_verified: bool) -> int:
    return bind.execute(
        sa.text(
            "INSERT INTO users (email, password_hash, role, email_verified) "
            "VALUES (:email, :ph, :role, :ev) RETURNING id"
        ),
        {"email": email, "ph": hash_password(password), "role": role, "ev": email_verified},
    ).scalar()


def _insert_profile(bind, *, user_id: int, name: str, summary: str | None, skills, hobbies) -> None:
    bind.execute(
        sa.text(
            "INSERT INTO profiles "
            "(user_id, name, summary, skills, hobbies, recommendation_criteria) "
            "VALUES (:uid, :name, :summary, CAST(:skills AS JSONB), CAST(:hobbies AS JSONB), "
            "CAST(:rc AS JSONB))"
        ),
        {
            "uid": user_id,
            "name": name,
            "summary": summary,
            "skills": json.dumps(skills),
            "hobbies": json.dumps(hobbies),
            "rc": json.dumps(["experience"]),
        },
    )


def _insert_experience(bind, *, user_id: int, exp: dict, position: int) -> None:
    bind.execute(
        sa.text(
            'INSERT INTO profile_experiences '
            '(user_id, title, description, industry, start, "end", months_of_experience, position) '
            "VALUES (:uid, :title, :desc, :industry, :start, :end, :months, :pos)"
        ),
        {
            "uid": user_id,
            "title": exp["title"],
            "desc": exp.get("description"),
            "industry": exp.get("industry"),
            "start": exp.get("start"),
            "end": exp.get("end"),
            "months": compute_months_of_experience(exp.get("start"), exp.get("end")),
            "pos": position,
        },
    )


def upgrade() -> None:
    bind = op.get_bind()

    # --- Admin ---
    if _account_exists(bind, settings.SEED_ADMIN_EMAIL) is None:
        admin_id = _insert_user(
            bind,
            email=settings.SEED_ADMIN_EMAIL,
            password=settings.SEED_ADMIN_PASSWORD,
            role="admin",
            email_verified=True,
        )
        _insert_profile(
            bind, user_id=admin_id, name=settings.SEED_ADMIN_NAME, summary=None, skills=[], hobbies=[]
        )

    # --- Demo user ---
    if _account_exists(bind, settings.SEED_USER_EMAIL) is None:
        user_id = _insert_user(
            bind,
            email=settings.SEED_USER_EMAIL,
            password=settings.SEED_USER_PASSWORD,
            role="user",
            email_verified=True,
        )
        _insert_profile(
            bind,
            user_id=user_id,
            name=settings.SEED_USER_NAME,
            summary=DEMO_SUMMARY,
            skills=DEMO_SKILLS,
            hobbies=DEMO_HOBBIES,
        )
        for pos, exp in enumerate(DEMO_EXPERIENCES):
            _insert_experience(bind, user_id=user_id, exp=exp, position=pos)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM users WHERE email IN (:a, :u)"),
        {"a": settings.SEED_ADMIN_EMAIL, "u": settings.SEED_USER_EMAIL},
    )

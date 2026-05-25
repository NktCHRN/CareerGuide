"""Profession business logic: search, detail assembly, applying admin changes,
and building the `profession.upserted` event payload.

Extracted separately because it is needed by the router, the publish helpers
and the backfill script alike.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profession, ProfessionSkill, Skill
from app.schemas import KnowledgeSkillOut, ProfessionCreate, ProfessionDetail, ProfessionUpdate

# Essential knowledge skills are listed before optional ones.
_RELATION_ORDER = case((ProfessionSkill.relation_type == "essential", 0), else_=1)


# --------------------------------------------------------------------------- #
#  Loading
# --------------------------------------------------------------------------- #
async def load_profession(session: AsyncSession, profession_id: int) -> Profession | None:
    return await session.get(Profession, profession_id)


async def load_knowledge_skills(
    session: AsyncSession, profession_id: int
) -> list[tuple[str, str, str]]:
    """Returns (skill_uri, label, relation_type) for the profession's knowledge skills."""
    result = await session.execute(
        select(ProfessionSkill.skill_uri, Skill.label, ProfessionSkill.relation_type)
        .join(Skill, Skill.skill_uri == ProfessionSkill.skill_uri)
        .where(ProfessionSkill.profession_id == profession_id)
        .order_by(_RELATION_ORDER, Skill.label.asc())
    )
    return [(row[0], row[1], row[2]) for row in result.all()]


def _search_condition(stmt: Select, query: str):
    pattern = f"%{query.strip()}%"
    alt = func.jsonb_array_elements_text(Profession.alt_labels).column_valued("alt")
    alt_exists = select(alt).where(alt.ilike(pattern)).exists()
    return stmt.where(or_(Profession.preferred_label.ilike(pattern), alt_exists)), pattern


async def search_professions(
    session: AsyncSession, query: str | None, page: int, page_size: int
) -> tuple[list[Profession], int]:
    """Searches by `preferred_label` + `alt_labels` (ILIKE). Returns (rows, total)."""
    base = select(Profession)
    count_base = select(func.count()).select_from(Profession)
    pattern: str | None = None

    if query and query.strip():
        base, pattern = _search_condition(base, query)
        count_base, _ = _search_condition(count_base, query)

    total = (await session.execute(count_base)).scalar_one()

    if pattern is not None:
        # Exact-ish matches in preferred_label rank above alt-label-only matches.
        base = base.order_by(
            case((Profession.preferred_label.ilike(pattern), 0), else_=1),
            Profession.preferred_label.asc(),
        )
    else:
        base = base.order_by(Profession.preferred_label.asc())

    base = base.limit(page_size).offset((page - 1) * page_size)
    rows = (await session.execute(base)).scalars().all()
    return list(rows), int(total)


# --------------------------------------------------------------------------- #
#  Admin create / update
# --------------------------------------------------------------------------- #
def create_profession(data: ProfessionCreate) -> Profession:
    return Profession(
        preferred_label=data.preferred_label.strip(),
        esco_uri=data.esco_uri,
        esco_code=data.esco_code,
        isco_group=data.isco_group,
        description=data.description,
        alt_labels=list(data.alt_labels or []),
        riasec_type=data.riasec_type,
        professional_values=data.professional_values,
        work_style=data.work_style,
        education_level=data.education_level,
        avg_salary=data.avg_salary,
        vacancies_local=data.vacancies_local,
        vacancies_international=data.vacancies_international,
        responsibilities=data.responsibilities,
    )


def apply_update(profession: Profession, update: ProfessionUpdate) -> None:
    """Applies a partial update (a field left unset is not touched)."""
    data = update.model_dump(exclude_unset=True)
    for field in (
        "preferred_label",
        "esco_uri",
        "esco_code",
        "isco_group",
        "description",
        "alt_labels",
        "riasec_type",
        "professional_values",
        "work_style",
        "education_level",
        "avg_salary",
        "vacancies_local",
        "vacancies_international",
        "responsibilities",
    ):
        if field in data:
            setattr(profession, field, data[field])


# --------------------------------------------------------------------------- #
#  DTO / event payload builders
# --------------------------------------------------------------------------- #
def build_detail(
    profession: Profession,
    knowledge_skills: list[tuple[str, str, str]],
    photo_url: str,
) -> ProfessionDetail:
    return ProfessionDetail(
        id=profession.id,
        esco_uri=profession.esco_uri,
        esco_code=profession.esco_code,
        isco_group=profession.isco_group,
        preferred_label=profession.preferred_label,
        description=profession.description,
        alt_labels=list(profession.alt_labels or []),
        riasec_type=profession.riasec_type,
        professional_values=profession.professional_values,
        work_style=profession.work_style,
        education_level=profession.education_level,
        avg_salary=float(profession.avg_salary) if profession.avg_salary is not None else None,
        vacancies_local=profession.vacancies_local,
        vacancies_international=profession.vacancies_international,
        responsibilities=profession.responsibilities,
        photo_url=photo_url,
        knowledge_skills=[
            KnowledgeSkillOut(skill_uri=uri, label=label, relation_type=rel)
            for uri, label, rel in knowledge_skills
        ],
        created_at=profession.created_at,
        updated_at=profession.updated_at,
    )


def build_upsert_payload(
    profession: Profession, knowledge_skills: list[tuple[str, str, str]]
) -> dict[str, Any]:
    """`profession` field of the `profession.upserted` event (shared conventions).

    `knowledge_skill_labels` is included on purpose so the worker and chat-service
    build everything from the event and never read the ESCO CSVs.
    """
    return {
        "id": profession.id,
        "esco_uri": profession.esco_uri,
        "esco_code": profession.esco_code,
        "isco_group": profession.isco_group,
        "preferred_label": profession.preferred_label,
        "alt_labels": list(profession.alt_labels or []),
        "description": profession.description,
        "education_level": profession.education_level,
        "avg_salary": float(profession.avg_salary) if profession.avg_salary is not None else None,
        "vacancies_local": profession.vacancies_local,
        "vacancies_international": profession.vacancies_international,
        "knowledge_skill_uris": [uri for uri, _label, _rel in knowledge_skills],
        "knowledge_skill_labels": [label for _uri, label, _rel in knowledge_skills],
    }

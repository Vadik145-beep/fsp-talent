"""Потребности работодателя, рекомендованные категории и подборка с объяснением (БД).

- `NeedService` — CRUD потребностей, категории (T6.2), подборка (T6.3, T6.4).
- `MatchingService.parse` — разбор текста правилами; на него ссылается `app.nlp.need_parser`
  (трек 3c), поэтому класс и сигнатура сохраняются.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.service import to_card
from app.catalog.repository import CatalogDb
from app.common.enums import GradeCode, NeedStatus, WorkFormat
from app.common.fixtures import Record
from app.core.errors import AppError, not_found
from app.matching.models import Need
from app.matching.parser import parse_need_text
from app.matching.repository import (
    CandidatePool,
    NeedDb,
    category_labels,
    need_record,
    skill_labels,
)
from app.matching.schemas import NeedCreate, NeedUpdate
from app.matching.scoring import NeedLike, score_candidate, weights_from

GRADES = [g.value for g in GradeCode]
# Смежные специализации (как в прототипе рекрутера)
ADJACENT: dict[str, list[str]] = {
    "backend": ["devops", "data_ml"],
    "frontend": ["mobile", "backend"],
    "mobile": ["frontend"],
    "data_ml": ["backend"],
    "qa": ["backend", "frontend"],
    "devops": ["backend"],
}


class MatchingService:
    """Разбор свободного текста потребности правилами (без LLM)."""

    def parse(self, text: str) -> dict[str, Any]:
        return parse_need_text(text)


def _clean_skills(codes: list[str]) -> list[str]:
    return list(dict.fromkeys(c.strip().lower() for c in codes if c.strip()))


def card_view(cand: Record) -> dict[str, Any]:
    """Обезличенная карточка (без ФИО, контактов, минимальной зарплаты, ФСП ID)."""
    return to_card(cand)


class NeedService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.needs = NeedDb(session)
        self.pool = CandidatePool(session)
        self.catalog = CatalogDb(session)

    # ---------- потребности ----------

    async def _records(self, needs: list[Need]) -> list[dict[str, Any]]:
        categories = list(dict.fromkeys(n.category for n in needs))
        counts = await self.pool.counts(categories)
        labels = await category_labels(self.session, categories)
        return [
            need_record(n, labels.get(n.category, n.category), counts[n.category]) for n in needs
        ]

    async def list_needs(self, company_id: int) -> list[dict[str, Any]]:
        return await self._records(await self.needs.by_company(company_id))

    async def _own(self, need_id: int, company_id: int) -> Need:
        need = await self.needs.get(need_id)
        if need is None or need.company_id != company_id:
            raise not_found("need", need_id)
        return need

    async def get_need(self, need_id: int, company_id: int) -> dict[str, Any]:
        return (await self._records([await self._own(need_id, company_id)]))[0]

    async def _check_skills(self, codes: list[str]) -> None:
        known = await self.catalog.existing_skill_codes(codes)
        unknown = [c for c in codes if c not in known]
        if unknown:
            raise AppError(
                422,
                "unknown_skills",
                "Технологий нет в справочнике стека — выберите из списка",
                {"skills": unknown},
            )

    async def _apply(self, need: Need, body: NeedCreate) -> None:
        required = _clean_skills(body.skills_required)
        desired = [s for s in _clean_skills(body.skills_desired) if s not in required]
        await self._check_skills(required + desired)
        need.title = body.title.strip()
        need.raw_text = (body.raw_text or "").strip() or None
        need.specialization = str(body.specialization)
        need.grade = str(body.grade)
        need.category = f"{body.specialization}:{body.grade}"
        need.skills_required = required
        need.skills_desired = desired
        need.team_description = body.team_description
        need.work_format = str(body.work_format)
        need.city = (body.city or "").strip() or None
        need.salary_from = body.salary_from
        need.salary_to = body.salary_to

    async def create_need(
        self, body: NeedCreate, company_id: int, recruiter_id: int
    ) -> dict[str, Any]:
        need = Need(
            company_id=company_id,
            recruiter_id=recruiter_id,
            status=NeedStatus.active.value,
            saved_filters={},
        )
        await self._apply(need, body)
        self.session.add(need)
        await self.session.commit()
        await self.session.refresh(need)
        return await self.get_need(need.id, company_id)

    async def update_need(self, need_id: int, company_id: int, body: NeedUpdate) -> dict[str, Any]:
        need = await self._own(need_id, company_id)
        await self._apply(need, body)
        need.status = str(body.status)
        await self.session.commit()
        await self.session.refresh(need)
        return await self.get_need(need_id, company_id)

    async def delete_need(self, need_id: int, company_id: int) -> None:
        need = await self._own(need_id, company_id)
        await self.session.delete(need)
        await self.session.commit()

    # ---------- категории (T6.2) ----------

    async def recommended_categories(self, need: dict[str, Any]) -> list[dict[str, Any]]:
        spec, grade = need["specialization"], need["grade"]
        gi = GRADES.index(grade)
        pairs: list[tuple[str, str]] = [(f"{spec}:{grade}", "primary")]
        if gi > 0:
            pairs.append((f"{spec}:{GRADES[gi - 1]}", "grade_lower"))
        if gi < len(GRADES) - 1:
            pairs.append((f"{spec}:{GRADES[gi + 1]}", "grade_higher"))
        pairs += [(f"{adj}:{grade}", "adjacent_specialization") for adj in ADJACENT.get(spec, [])]
        codes = [c for c, _ in pairs]
        labels = await category_labels(self.session, codes)
        counts = await self.pool.counts(codes)
        return [
            {
                "category": code,
                "label": labels.get(code, code),
                "relation": relation,
                "candidates_count": counts[code],
            }
            for code, relation in pairs
            if code in labels
        ]

    # ---------- подборка (T6.3, T6.4) ----------

    async def matches(
        self,
        need: dict[str, Any],
        company_id: int,
        category: str | None,
        skills: list[str],
        has_fsp: bool | None,
        work_format: WorkFormat | None,
        city: str | None,
    ) -> dict[str, Any]:
        category = category or need["category"]
        labels = await category_labels(self.session, [category])
        if category not in labels:
            raise AppError(
                422,
                "validation_error",
                "Неизвестная категория",
                {"fields": {"category": "Неизвестная категория"}},
            )
        ids = await self.pool.searchable_ids(category)
        records = await self.pool.records(ids)
        statuses = await self.pool.last_invitation_status(company_id, ids)
        weights = weights_from(await self.catalog.settings())
        skill_names = await skill_labels(self.session)
        target = NeedLike(
            skills_required=need["skills_required"],
            skills_desired=need["skills_desired"],
            salary_from=need["salary_from"],
            salary_to=need["salary_to"],
            work_format=need["work_format"],
        )
        ranked = []
        for cid in ids:
            cand = records.get(cid)
            if cand is None:
                continue
            scored = score_candidate(
                cand,
                target,
                weights,
                lambda code: skill_names.get(code, code),
                fsp_reason=cand.get("fsp_reason"),
            )
            ranked.append(
                {
                    "candidate": card_view(cand),
                    **scored,
                    "invitation_status": statuses.get(cid),
                }
            )
        ranked.sort(key=lambda m: (-m["score"], m["candidate"]["id"]))

        wanted = _clean_skills(skills)
        city_q = (city or "").strip().lower()

        def keep(m: dict[str, Any]) -> bool:
            c = m["candidate"]
            if wanted and not set(wanted) <= set(c["stack"]):
                return False
            if has_fsp is not None and bool(c["has_fsp"]) != has_fsp:
                return False
            if work_format and str(work_format) not in c["work_formats"]:
                return False
            # город — только если кандидат его показывает (иначе в карточке null)
            return not city_q or (c.get("city") or "").lower() == city_q

        items = [m for m in ranked if keep(m)]
        return {
            "need_id": need["id"],
            "category": category,
            "category_label": labels[category],
            "total_before_filters": len(ranked),
            "total": len(items),
            "filters": {
                "skills": wanted,
                "has_fsp": has_fsp,
                "work_format": work_format,
                "city": city,
            },
            "items": items,
        }

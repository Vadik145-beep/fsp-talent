"""Потребности, рекомендованные категории и ранжирование с объяснением — упрощённая версия
для контракта v0. Полная формула (эмбеддинги, ФСП-скор, свежесть) — волна 3b (T6.3)."""

import re
from datetime import datetime
from typing import Any

from app.candidates.service import CandidateService, is_searchable, to_card
from app.catalog.repository import CatalogRepository
from app.common.enums import GradeCode, NeedStatus, WorkFormat
from app.common.fixtures import Record
from app.core.errors import not_found
from app.matching.repository import NeedRepository
from app.matching.schemas import NeedCreate

GRADES = [g.value for g in GradeCode]
ADJACENT: dict[str, list[str]] = {
    "backend": ["devops", "data_ml"],
    "frontend": ["mobile"],
    "mobile": ["frontend"],
    "data_ml": ["backend"],
    "qa": ["backend"],
    "devops": ["backend"],
}
FACTOR_LABELS = {
    "stack": "Совпадение стека",
    "theta": "Результат теста",
    "fsp": "Достижения ФСП",
    "freshness": "Свежесть профиля",
    "salary": "Зарплатные ожидания",
    "work_format": "Формат работы",
}
GRADE_WORDS = {
    "senior": ("сеньор", "синьор", "senior", "ведущ"),
    "middle": ("мидл", "middle", "миддл"),
    "junior": ("джун", "junior", "младш"),
    "intern": ("стаж", "intern", "практик"),
}
SPEC_WORDS = {
    "backend": ("backend", "бэкенд", "бекенд", "go", "golang", "python", "java", "сервер"),
    "frontend": ("frontend", "фронтенд", "фронт", "react", "vue", "верст"),
    "mobile": ("mobile", "мобил", "android", "ios", "flutter"),
    "data_ml": ("data", "ml", "дата", "машинн", "аналитик данных", "ds"),
    "qa": ("qa", "тестиров", "автотест"),
    "devops": ("devops", "девопс", "k8s", "kubernetes", "sre", "инфраструкт"),
}
FORMAT_WORDS = {
    "remote": ("удален", "удалён", "remote"),
    "hybrid": ("гибрид",),
    "office": ("офис",),
}


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


class MatchingService:
    def __init__(
        self,
        repo: NeedRepository | None = None,
        candidates: CandidateService | None = None,
        catalog: CatalogRepository | None = None,
    ) -> None:
        self.repo = repo or NeedRepository()
        self.candidates = candidates or CandidateService()
        self.catalog = catalog or CatalogRepository()

    # ---------- потребности ----------

    def list_needs(self, company_id: int) -> list[Record]:
        return sorted(self.repo.by_company(company_id), key=lambda n: n["created_at"], reverse=True)

    def get_need(self, need_id: int, company_id: int) -> Record:
        need = self.repo.get(need_id)
        if need is None or need["company_id"] != company_id:
            raise not_found("need", need_id)
        return need

    def _count(self, category: str) -> int:
        return sum(
            1 for c in self.candidates.repo.all() if is_searchable(c) and c["category"] == category
        )

    def create_need(self, body: NeedCreate, company_id: int, recruiter_id: int) -> dict[str, Any]:
        category = f"{body.specialization}:{body.grade}"
        cat = self.catalog.category(category) or {"label": category}
        return {
            **body.model_dump(),
            "id": self.repo.next_id(),
            "company_id": company_id,
            "recruiter_id": recruiter_id,
            "category": category,
            "category_label": cat["label"],
            "status": NeedStatus.active,
            "candidates_count": self._count(category),
            "created_at": datetime.now().astimezone().isoformat(),
        }

    def parse(self, text: str) -> dict[str, Any]:
        """Разбор свободного текста правилами (LLM — волна 3c)."""
        low = text.lower()
        words = set(re.findall(r"[a-zа-яё0-9+#.]+", low))
        draft: dict[str, Any] = {"skills_required": [], "skills_desired": []}
        recognized: list[str] = []
        for grade, keys in GRADE_WORDS.items():
            if any(k in low for k in keys):
                draft["grade"] = grade
                recognized.append("grade")
                break
        for spec, keys in SPEC_WORDS.items():
            if any((k in words) if len(k) <= 3 else (k in low) for k in keys):
                draft["specialization"] = spec
                recognized.append("specialization")
                break
        for skill in self.repo.skills():
            label = skill["label"].lower()
            if skill["id"] in words or label in words or (len(label) > 3 and label in low):
                draft["skills_required"].append(skill["id"])
        if draft["skills_required"]:
            recognized.append("skills_required")
        for fmt, keys in FORMAT_WORDS.items():
            if any(k in low for k in keys):
                draft["work_format"] = fmt
                recognized.append("work_format")
                break
        money = re.search(r"(\d{2,3})\s*[–—-]\s*(\d{2,3})\s*(к|k|тыс)", low)
        if money:
            draft["salary_from"] = int(money.group(1)) * 1000
            draft["salary_to"] = int(money.group(2)) * 1000
            recognized += ["salary_from", "salary_to"]
        if draft.get("specialization") and draft.get("grade"):
            draft["title"] = f"{draft['grade'].capitalize()} {draft['specialization']}"
        return {
            "draft": draft,
            "parser": "rules",
            "recognized_fields": recognized,
            "unrecognized": [],
        }

    # ---------- категории и подборка ----------

    def recommended_categories(self, need: Record) -> list[dict[str, Any]]:
        spec, grade = need["specialization"], need["grade"]
        gi = GRADES.index(grade)
        pairs: list[tuple[str, str, str]] = [(spec, grade, "primary")]
        if gi > 0:
            pairs.append((spec, GRADES[gi - 1], "grade_lower"))
        if gi < len(GRADES) - 1:
            pairs.append((spec, GRADES[gi + 1], "grade_higher"))
        pairs += [(adj, grade, "adjacent_specialization") for adj in ADJACENT.get(spec, [])]
        result = []
        for s, g, relation in pairs:
            category = f"{s}:{g}"
            cat = self.catalog.category(category) or {"label": category}
            result.append(
                {
                    "category": category,
                    "label": cat["label"],
                    "relation": relation,
                    "candidates_count": self._count(category),
                }
            )
        return result

    def _score(self, need: Record, cand: Record) -> dict[str, Any]:
        weights: dict[str, float] = self.catalog.platform_settings().get("ranking_weights") or {
            k: 1.0 for k in FACTOR_LABELS
        }
        stack = set(cand["stack"])
        req, des = set(need["skills_required"]), set(need["skills_desired"])
        denom = len(req) + 0.5 * len(des)
        values = {
            "stack": (len(req & stack) + 0.5 * len(des & stack)) / denom if denom else 1.0,
            "theta": _clip(((cand.get("theta") or 0) + 2.5) / 5),
            "fsp": (cand.get("fsp_score") or 0) / 100,
            "freshness": cand["freshness"],
            "salary": 1.0 if (cand.get("min_salary") or 0) <= need["salary_to"] else 0.0,
            "work_format": 1.0 if need["work_format"] in cand["work_formats"] else 0.0,
        }
        total_w = sum(weights.values()) or 1.0
        breakdown: list[dict[str, Any]] = [
            {
                "factor": f,
                "label": FACTOR_LABELS[f],
                "value": round(_clip(v), 3),
                "weight": weights.get(f, 0.0),
                "contribution": round(_clip(v) * weights.get(f, 0.0) / total_w, 3),
            }
            for f, v in values.items()
        ]
        score = round(sum(b["contribution"] for b in breakdown), 3)
        reasons = []
        matched = sorted(req & stack)
        if matched:
            reasons.append(f"Есть обязательный стек: {', '.join(matched)}")
        if values["theta"] >= 0.55:
            reasons.append(f"Сильный результат теста в категории (θ = {cand.get('theta')})")
        if cand.get("fsp_score"):
            reasons.append("Подтверждённые достижения ФСП")
        if values["freshness"] >= 0.6:
            reasons.append("Недавно решал регулярные задания")
        if values["salary"]:
            reasons.append("Ожидания по зарплате в пределах вилки")
        return {
            "candidate": to_card(cand),
            "score": score,
            "breakdown": breakdown,
            "reasons": reasons[:4] or ["Подходит по категории"],
            "salary_fit": bool(values["salary"]),
            "invitation_status": None,
        }

    def matches(
        self,
        need: Record,
        category: str | None,
        skills: list[str],
        has_fsp: bool | None,
        work_format: WorkFormat | None,
        city: str | None,
    ) -> dict[str, Any]:
        category = category or need["category"]
        base = [
            c for c in self.candidates.repo.all() if is_searchable(c) and c["category"] == category
        ]
        filtered = base
        if skills:
            filtered = [c for c in filtered if set(skills) <= set(c["stack"])]
        if has_fsp is not None:
            filtered = [c for c in filtered if bool(c.get("fsp_id")) == has_fsp]
        if work_format:
            filtered = [c for c in filtered if work_format in c["work_formats"]]
        if city:
            filtered = [c for c in filtered if c["privacy"].get("show_city") and c["city"] == city]
        items = sorted((self._score(need, c) for c in filtered), key=lambda m: -m["score"])
        cat = self.catalog.category(category) or {"label": category}
        return {
            "need_id": need["id"],
            "category": category,
            "category_label": cat["label"],
            "total_before_filters": len(base),
            "total": len(items),
            "filters": {
                "skills": skills,
                "has_fsp": has_fsp,
                "work_format": work_format,
                "city": city,
            },
            "items": items,
        }

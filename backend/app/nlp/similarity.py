"""Соответствие стека кандидата потребности (часть счёта ранжирования, T6.3).

Единая точка для подбора (модуль matching). Точное совпадение и синонимы дают 1,
смежная технология — частичный вклад из справочника смежности (FastAPI ↔ Django = 0,5).
Результат 0..1, детерминированно.
"""

from collections.abc import Iterable

from app.nlp.skills_lexicon import ADJACENCY, normalize_skill

REQUIRED_WEIGHT = 0.75
DESIRED_WEIGHT = 0.25


def _codes(skills: Iterable[str]) -> list[str]:
    """Коды без повторов; неизвестное справочнику название остаётся как есть (в нижнем регистре)."""
    result: dict[str, None] = {}
    for s in skills:
        if s and s.strip():
            result[normalize_skill(s) or s.strip().lower()] = None
    return list(result)


def skill_credit(skill: str, candidate: Iterable[str]) -> tuple[float, str | None]:
    """Насколько кандидат закрывает одну технологию: (вклад 0..1, чем закрыл)."""
    code = normalize_skill(skill) or skill.strip().lower()
    best, by = 0.0, None
    for have in _codes(candidate):
        if have == code:
            return 1.0, have
        w = ADJACENCY.get(frozenset((code, have)), 0.0)
        if w > best:
            best, by = w, have
    return best, by


def _part(skills: list[str], candidate: list[str]) -> float:
    if not skills:
        return 1.0
    return sum(skill_credit(s, candidate)[0] for s in skills) / len(skills)


def stack_match(required: Iterable[str], desired: Iterable[str], candidate: Iterable[str]) -> float:
    """Доля 0..1: обязательный стек весит 0,75, желательный — 0,25."""
    have = _codes(candidate)
    req = _codes(required)
    des = [s for s in _codes(desired) if s not in req]
    return round(REQUIRED_WEIGHT * _part(req, have) + DESIRED_WEIGHT * _part(des, have), 4)


def matched_skills(required: Iterable[str], candidate: Iterable[str]) -> list[str]:
    """Какие требуемые технологии есть у кандидата (точно или синонимом) — для объяснения."""
    have = set(_codes(candidate))
    result: list[str] = []
    for s in required:
        code = normalize_skill(s) or s.strip().lower()
        if code in have and s not in result:
            result.append(s)
    return result


def related_skills(required: Iterable[str], candidate: Iterable[str]) -> dict[str, str]:
    """Требуемая технология → смежная у кандидата (когда точной нет): {"django": "fastapi"}."""
    have = set(_codes(candidate))
    result: dict[str, str] = {}
    for s in required:
        code = normalize_skill(s) or s.strip().lower()
        if code in have:
            continue
        credit, by = skill_credit(s, have)
        if credit > 0 and by:
            result[s] = by
    return result

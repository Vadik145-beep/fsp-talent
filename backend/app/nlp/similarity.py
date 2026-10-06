"""Соответствие стека кандидата потребности (часть счёта ранжирования, T6.3).

Единая точка для подбора (модуль matching). Сейчас — точные совпадения кодов;
трек 3c добавляет близкие технологии (синонимы, смежный стек), сигнатуру сохраняет.
"""

from collections.abc import Iterable


def stack_match(required: Iterable[str], desired: Iterable[str], candidate: Iterable[str]) -> float:
    """Доля 0..1: обязательный стек весит 0,75, желательный — 0,25."""
    have = set(candidate)
    req, des = set(required), set(desired)
    req_part = len(req & have) / len(req) if req else 1.0
    des_part = len(des & have) / len(des) if des else 1.0
    return round(0.75 * req_part + 0.25 * des_part, 4)


def matched_skills(required: Iterable[str], candidate: Iterable[str]) -> list[str]:
    """Какие требуемые технологии есть у кандидата (для объяснения выдачи)."""
    have = set(candidate)
    return [s for s in required if s in have]

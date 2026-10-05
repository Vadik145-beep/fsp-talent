"""Справочники движка тестирования. Коды совпадают с общими соглашениями проекта."""

from __future__ import annotations

SPECIALIZATIONS: tuple[str, ...] = ("backend", "frontend", "mobile", "data_ml", "qa", "devops")

GRADES: tuple[str, ...] = ("intern", "junior", "middle", "senior")

GRADE_LABELS: dict[str, str] = {
    "intern": "Стажёр",
    "junior": "Junior",
    "middle": "Middle",
    "senior": "Senior",
}


def grade_index(grade: str) -> int:
    """Номер грейда (intern=0 … senior=3). Неизвестный код — ValueError."""
    try:
        return GRADES.index(grade)
    except ValueError:
        raise ValueError(f"Неизвестный грейд: {grade!r}") from None


def check_grade(grade: str) -> str:
    grade_index(grade)
    return grade


def check_specialization(spec: str) -> str:
    if spec not in SPECIALIZATIONS:
        raise ValueError(f"Неизвестная специализация: {spec!r}")
    return spec

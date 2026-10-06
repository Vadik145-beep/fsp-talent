"""Разбор свободного текста потребности работодателя в поля формы (T6.1).

Единая точка: эндпоинт `/api/matching/needs/parse` (модуль matching) вызывает только `parse_need`.
Сейчас — правила из MatchingService; трек 3c заменяет реализацию (правила + LLM),
сигнатуру сохраняет.
"""

from typing import Any


def parse_need(text: str) -> dict[str, Any]:
    """Текст → черновик потребности (формат ответа NeedParseResult из контракта)."""
    from app.matching.service import MatchingService

    return MatchingService().parse(text)

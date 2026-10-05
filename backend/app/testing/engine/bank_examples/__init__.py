"""Примеры параметрических шаблонов: по 2 на каждую специализацию, все 7 форматов.

Это образец для банка задач (T4.3): стартовые a, b заданы экспертно по целевому грейду
и уточняются калибровкой по накопленным ответам.
"""

from __future__ import annotations

from ..templates import ItemTemplate, TemplateRegistry
from . import backend, data_ml, devops, frontend, mobile, qa

EXAMPLE_TEMPLATES: tuple[ItemTemplate, ...] = (
    *backend.TEMPLATES,
    *frontend.TEMPLATES,
    *mobile.TEMPLATES,
    *data_ml.TEMPLATES,
    *qa.TEMPLATES,
    *devops.TEMPLATES,
)


def example_registry() -> TemplateRegistry:
    """Новый реестр с примерами шаблонов."""
    return TemplateRegistry(EXAMPLE_TEMPLATES)


__all__ = ["EXAMPLE_TEMPLATES", "example_registry"]

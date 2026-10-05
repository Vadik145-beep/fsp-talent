"""Рабочий банк задач (T4.3): по папке на специализацию, каждая отдаёт кортеж TEMPLATES.

Примеры из `bank_examples` тоже входят в банк. Папки специализаций независимы:
авторы задач разных специализаций не правят общие файлы.
"""

from __future__ import annotations

from ..bank_examples import EXAMPLE_TEMPLATES
from ..templates import ItemTemplate, TemplateRegistry
from . import backend, data_ml, devops, frontend, mobile, qa

BANK_TEMPLATES: tuple[ItemTemplate, ...] = (
    *EXAMPLE_TEMPLATES,
    *backend.TEMPLATES,
    *frontend.TEMPLATES,
    *mobile.TEMPLATES,
    *data_ml.TEMPLATES,
    *qa.TEMPLATES,
    *devops.TEMPLATES,
)


def bank_registry() -> TemplateRegistry:
    """Новый реестр со всем банком задач (примеры + шаблоны специализаций)."""
    return TemplateRegistry(BANK_TEMPLATES)


__all__ = ["BANK_TEMPLATES", "bank_registry"]

"""Банк задач: qa (T4.3). Шаблоны — в модулях папки, здесь только сборка."""

from __future__ import annotations

from ...templates import ItemTemplate
from . import api, automation, bug_reports, performance, security, sql, test_design, test_management

TEMPLATES: tuple[ItemTemplate, ...] = (
    *test_design.TEMPLATES,
    *bug_reports.TEMPLATES,
    *api.TEMPLATES,
    *sql.TEMPLATES,
    *automation.TEMPLATES,
    *test_management.TEMPLATES,
    *performance.TEMPLATES,
    *security.TEMPLATES,
)

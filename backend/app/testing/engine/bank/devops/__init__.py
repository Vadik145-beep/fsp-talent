"""Банк задач: devops (T4.3). Шаблоны — в модулях папки, здесь только сборка."""

from __future__ import annotations

from ...templates import ItemTemplate
from . import bash, ci_cd, containers, iac, incidents, kubernetes, linux, monitoring, networking

TEMPLATES: tuple[ItemTemplate, ...] = (
    *linux.TEMPLATES,
    *networking.TEMPLATES,
    *containers.TEMPLATES,
    *kubernetes.TEMPLATES,
    *ci_cd.TEMPLATES,
    *iac.TEMPLATES,
    *bash.TEMPLATES,
    *monitoring.TEMPLATES,
    *incidents.TEMPLATES,
)

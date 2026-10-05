"""Банк задач: frontend (T4.3). Шаблоны — в модулях папки, здесь только сборка."""

from __future__ import annotations

from ...templates import ItemTemplate
from . import (
    browser_net,
    css_layout,
    dom_events,
    js_async,
    js_semantics,
    react,
    security_a11y,
    typescript,
)

TEMPLATES: tuple[ItemTemplate, ...] = (
    *js_semantics.TEMPLATES,
    *js_async.TEMPLATES,
    *css_layout.TEMPLATES,
    *dom_events.TEMPLATES,
    *react.TEMPLATES,
    *browser_net.TEMPLATES,
    *typescript.TEMPLATES,
    *security_a11y.TEMPLATES,
)

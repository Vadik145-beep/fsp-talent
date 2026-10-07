"""Перевод между вариантом движка и контрактом API.

Клиент видит варианты ответа с id `a`, `b`, `c`…; движок проверяет ответ по индексам.
Форматы движка `multi_choice` / `find_bug_line` в API называются `multiple_choice` /
`find_error_line`.
"""

from __future__ import annotations

import string
from typing import Any

from app.testing.engine import ItemFormat, ItemInstance, NumericKey

API_FORMAT = {
    ItemFormat.SINGLE_CHOICE: "single_choice",
    ItemFormat.MULTI_CHOICE: "multiple_choice",
    ItemFormat.NUMERIC: "numeric",
    ItemFormat.SHORT_TEXT: "short_text",
    ItemFormat.CODE_OUTPUT: "code_output",
    ItemFormat.FIND_BUG_LINE: "find_error_line",
    ItemFormat.ORDERING: "ordering",
}
CHOICE_FORMATS = (ItemFormat.SINGLE_CHOICE, ItemFormat.MULTI_CHOICE)


def api_format(fmt: ItemFormat | str) -> str:
    return API_FORMAT[ItemFormat(fmt)]


def option_id(index: int) -> str:
    letters = string.ascii_lowercase
    return letters[index] if index < len(letters) else f"o{index + 1}"


def option_index(opt_id: str, n: int) -> int | None:
    for i in range(n):
        if option_id(i) == opt_id:
            return i
    return None


def item_view(
    inst: ItemInstance,
    *,
    instance_id: str,
    topic: str,
    topic_label: str,
    time_limit_sec: int,
) -> dict[str, Any]:
    """Публичная часть варианта в форме `ItemView` (без ключа, шаблона и seed)."""
    pub = inst.public
    opts = [{"id": option_id(i), "text": text} for i, text in enumerate(pub.options)]
    extra = dict(pub.extra)
    language = extra.get("language")
    unit = extra.get("unit")
    return {
        "instance_id": instance_id,
        "format": api_format(pub.format),
        "topic": topic,
        "topic_label": topic_label,
        "prompt": pub.prompt,
        "code": pub.code,
        "code_language": language if isinstance(language, str) else None,
        "options": opts if pub.format in CHOICE_FORMATS else None,
        "steps": opts if pub.format is ItemFormat.ORDERING else None,
        "unit": unit if isinstance(unit, str) else None,
        "time_limit_sec": int(time_limit_sec),
    }


def engine_response(inst: ItemInstance, answer: dict[str, Any]) -> Any:
    """Ответ из `AnswerPayload` → ответ для `check()` движка. Мусор → None (будет неверно)."""
    fmt = inst.format
    n = len(inst.public.options)
    if fmt in CHOICE_FORMATS:
        ids = answer.get("choice_ids") or []
        idx = [option_index(str(i), n) for i in ids]
        if not idx or any(i is None for i in idx):
            return None
        if fmt is ItemFormat.SINGLE_CHOICE:
            return idx[0] if len(idx) == 1 else None
        return idx
    if fmt is ItemFormat.ORDERING:
        ids = answer.get("order") or answer.get("choice_ids") or []
        idx = [option_index(str(i), n) for i in ids]
        return None if not idx or any(i is None for i in idx) else idx
    if fmt is ItemFormat.FIND_BUG_LINE:
        line = answer.get("line")
        if line is None and answer.get("value") is not None:
            line = answer["value"]
        return line
    if fmt is ItemFormat.NUMERIC:
        value = answer.get("value")
        return value if value is not None else answer.get("text")
    return answer.get("text")  # short_text, code_output


def answer_payload(inst: ItemInstance) -> dict[str, Any]:
    """Правильный ответ в форме `AnswerPayload` — только для админки."""
    fmt = inst.format
    key = inst.key
    payload: dict[str, Any] = {
        "choice_ids": None,
        "value": None,
        "text": None,
        "line": None,
        "order": None,
    }
    if fmt is ItemFormat.SINGLE_CHOICE:
        payload["choice_ids"] = [option_id(int(key))]
    elif fmt is ItemFormat.MULTI_CHOICE:
        payload["choice_ids"] = [option_id(i) for i in sorted(key)]
    elif fmt is ItemFormat.ORDERING:
        payload["order"] = [option_id(i) for i in key]
    elif fmt is ItemFormat.FIND_BUG_LINE:
        payload["line"] = int(key)
    elif fmt is ItemFormat.NUMERIC:
        assert isinstance(key, NumericKey)
        payload["value"] = key.value
    elif fmt is ItemFormat.SHORT_TEXT:
        payload["text"] = key[0]
    else:
        payload["text"] = str(key)
    return payload

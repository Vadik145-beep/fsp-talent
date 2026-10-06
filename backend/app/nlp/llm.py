"""Клиент OpenAI-совместимого API со строгим JSON-ответом.

Правило модуля: LLM только улучшает результат. Любая ошибка (нет ключа, таймаут, не JSON,
не прошла валидация pydantic) → `None`, и вызывающий код остаётся на правилах.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.nlp.settings import NlpSettings, get_nlp_settings

log = logging.getLogger(__name__)


def llm_enabled(settings: NlpSettings | None = None) -> bool:
    return (settings or get_nlp_settings()).llm_enabled


def _extract_json(content: str) -> Any:
    """Ответ модели → JSON (терпим обёртку ```json ... ```)."""
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    return json.loads(text)


def complete_json[T: BaseModel](
    system: str,
    user: str,
    schema: type[T],
    *,
    settings: NlpSettings | None = None,
    transport: httpx.BaseTransport | None = None,
) -> T | None:
    """Запрос к /chat/completions → объект `schema` или None (без исключений)."""
    cfg = settings or get_nlp_settings()
    if not cfg.llm_enabled:
        return None
    url = cfg.llm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": cfg.llm_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    try:
        with httpx.Client(timeout=cfg.llm_timeout_sec, transport=transport) as client:
            resp = client.post(
                url, json=payload, headers={"Authorization": f"Bearer {cfg.llm_api_key}"}
            )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return schema.model_validate(_extract_json(content))
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
        # ValueError покрывает и json.JSONDecodeError
        log.warning("LLM недоступна или ответила не по схеме, работаем по правилам: %s", exc)
        return None

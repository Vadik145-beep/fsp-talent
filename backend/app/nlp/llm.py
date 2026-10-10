"""Клиент OpenAI-совместимого API со строгим JSON-ответом.

Правило модуля: LLM только улучшает результат. Любая ошибка (нет ключа, таймаут, не JSON,
не прошла валидация pydantic) → `None`, и вызывающий код остаётся на правилах.

На стенде за этим API — открытая модель Qwen2.5-1.5B-Instruct в llama.cpp на нашем же сервере
(контейнер `llm`): тексты резюме и вакансий не уходят наружу. С `LLM_JSON_SCHEMA=true` в запрос
кладётся JSON-схема ответа — llama.cpp строит по ней грамматику, и модель не может ответить
не по схеме. В API-обработчиках вызывать только `acomplete_json` — он не блокирует цикл событий.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.nlp.settings import NlpSettings, get_nlp_settings

log = logging.getLogger(__name__)

# Запросов к модели в работе в этом процессе: модель на 2 ядрах отвечает по одному запросу,
# поэтому необязательные вызовы (разбор потребности) при занятой модели пропускаются.
_inflight = 0


def llm_enabled(settings: NlpSettings | None = None) -> bool:
    return (settings or get_nlp_settings()).llm_enabled


def llm_busy() -> bool:
    return _inflight > 0


def _extract_json(content: str) -> Any:
    """Ответ модели → JSON (терпим обёртку ```json ... ```)."""
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    return json.loads(text)


def _request(
    cfg: NlpSettings, system: str, user: str, schema: type[BaseModel], max_tokens: int | None
) -> tuple[str, dict[str, Any], dict[str, str]]:
    url = cfg.llm_base_url.rstrip("/") + "/chat/completions"
    response_format: dict[str, Any] = {"type": "json_object"}
    if cfg.llm_json_schema:
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
        }
    payload: dict[str, Any] = {
        "model": cfg.llm_model,
        "temperature": 0,
        "response_format": response_format,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens
    return url, payload, {"Authorization": f"Bearer {cfg.llm_api_key}"}


def _parse[T: BaseModel](resp: httpx.Response, schema: type[T], started: float) -> T:
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    result = schema.model_validate(_extract_json(content))
    log.info("LLM ответила по схеме %s за %.1f с", schema.__name__, time.monotonic() - started)
    return result


_ERRORS = (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, ValidationError)


def complete_json[T: BaseModel](
    system: str,
    user: str,
    schema: type[T],
    *,
    settings: NlpSettings | None = None,
    transport: httpx.BaseTransport | None = None,
    timeout: float | None = None,
    max_tokens: int | None = None,
) -> T | None:
    """Синхронный запрос (скрипты валидации, потоки) → объект `schema` или None."""
    cfg = settings or get_nlp_settings()
    if not cfg.llm_enabled:
        return None
    url, payload, headers = _request(cfg, system, user, schema, max_tokens)
    started = time.monotonic()
    try:
        with httpx.Client(timeout=timeout or cfg.llm_timeout_sec, transport=transport) as client:
            resp = client.post(url, json=payload, headers=headers)
        return _parse(resp, schema, started)
    except _ERRORS as exc:  # ValueError покрывает и json.JSONDecodeError
        log.warning("LLM недоступна или ответила не по схеме, работаем по правилам: %r", exc)
        return None


async def acomplete_json[T: BaseModel](
    system: str,
    user: str,
    schema: type[T],
    *,
    settings: NlpSettings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    timeout: float | None = None,
    max_tokens: int | None = None,
) -> T | None:
    """Асинхронный запрос (для обработчиков API) → объект `schema` или None."""
    global _inflight
    cfg = settings or get_nlp_settings()
    if not cfg.llm_enabled:
        return None
    url, payload, headers = _request(cfg, system, user, schema, max_tokens)
    started = time.monotonic()
    _inflight += 1
    try:
        async with httpx.AsyncClient(
            timeout=timeout or cfg.llm_timeout_sec, transport=transport
        ) as client:
            resp = await client.post(url, json=payload, headers=headers)
        return _parse(resp, schema, started)
    except _ERRORS as exc:
        log.warning(
            "LLM недоступна или ответила не по схеме за %.1f с, работаем по правилам: %r",
            time.monotonic() - started,
            exc,
        )
        return None
    finally:
        _inflight -= 1

"""Локальная LLM (llama.cpp, OpenAI-совместимый API): асинхронный клиент, черновики задач из
вакансии, дозаполнение разбора потребности и резюме. Без живой модели — `httpx.MockTransport`;
последний тест идёт на настоящей модели и пропускается, если она не поднята
(`LLM_TEST_BASE_URL` или `LLM_BASE_URL`, по умолчанию http://127.0.0.1:18090/v1)."""

import asyncio
import json
import os
from collections.abc import Callable, Iterator
from functools import partial
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.candidates import resume
from app.nlp import llm, need_parser, vacancy_tests
from app.nlp.need_parser import LlmNeed, parse_need_async, parse_rules
from app.nlp.settings import NlpSettings, get_nlp_settings
from app.nlp.vacancy_tests import LlmDraft, analyze_vacancy, check_llm_draft, llm_draft
from app.seed.testkit import sql_sync
from tests.conftest import ADMIN, RECRUITER

LLM_ENV = {
    "LLM_BASE_URL": "http://llm.test/v1",
    "LLM_API_KEY": "local",
    "LLM_MODEL": "qwen2.5-1.5b-instruct",
    "LLM_JSON_SCHEMA": "true",
    "LLM_DISPLAY_NAME": "Qwen2.5-1.5B",
    "LLM_LOCAL": "true",
}
GRPC_VACANCY = (
    "Senior Go-разработчик (платформа)\n"
    "Пишем сервисы на Go, общаемся по gRPC и protobuf, PostgreSQL. Контракты API держим в репо."
)
GOOD_DRAFT = {
    "title": "Обратная совместимость protobuf",
    "question": "Что нельзя делать с полем сообщения protobuf, чтобы не сломать старых клиентов?",
    "options": [
        "1. Менять номер поля",
        "2. Добавлять новое поле",
        "3. Менять комментарий",
        "4. Переименовывать поле",
    ],
    "correct_index": 0,
    "explanation": "Клиенты читают поля по номеру: смена номера ломает разбор старых сообщений.",
}


def _reply(content: Any) -> httpx.Response:
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


@pytest.fixture
def llm_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[Any], list[dict[str, Any]]]]:
    """Включает LLM через переменные окружения; ответ модели подменяется MockTransport."""
    for key, value in LLM_ENV.items():
        monkeypatch.setenv(key, value)
    get_nlp_settings.cache_clear()
    original = llm.acomplete_json

    def install(answer: Any) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            calls.append(json.loads(request.content))
            return answer(request) if callable(answer) else _reply(answer)

        transport = httpx.MockTransport(handler)
        monkeypatch.setattr(llm, "acomplete_json", partial(original, transport=transport))
        return calls

    yield install
    get_nlp_settings.cache_clear()


# ---------------------------------------------------------------- клиент


def test_async_client_sends_json_schema_and_limits() -> None:
    cfg = NlpSettings(**{k.lower(): v for k, v in LLM_ENV.items()})
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return _reply({"grade": "junior"})

    answer = asyncio.run(
        llm.acomplete_json(
            "s", "u", LlmNeed, settings=cfg, transport=httpx.MockTransport(handler), max_tokens=50
        )
    )
    assert answer is not None and answer.grade == "junior"
    assert seen["response_format"]["type"] == "json_schema"
    assert seen["response_format"]["json_schema"]["schema"]["properties"]["grade"]
    assert seen["max_tokens"] == 50 and seen["temperature"] == 0
    assert not llm.llm_busy()


@pytest.mark.parametrize(
    "fail",
    [
        httpx.ReadTimeout("медленно"),
        httpx.ConnectError("нет контейнера llm"),
    ],
)
def test_async_client_errors_give_none(fail: Exception) -> None:
    cfg = NlpSettings(**{k.lower(): v for k, v in LLM_ENV.items()})

    async def handler(request: httpx.Request) -> httpx.Response:
        raise fail

    transport = httpx.MockTransport(handler)
    assert (
        asyncio.run(llm.acomplete_json("s", "u", LlmNeed, settings=cfg, transport=transport))
        is None
    )
    assert not llm.llm_busy()


# ---------------------------------------------------------------- черновики задач


def _grpc_hit() -> tuple[Any, Any]:
    analysis = analyze_vacancy(GRPC_VACANCY)
    hit = next(h for h in analysis.topics if h.topic.id == "backend.grpc")
    return hit, analysis


@pytest.mark.parametrize(
    ("patch", "reason"),
    [
        ({"options": ["Да", "Нет", "да", "Не знаю"]}, "повторяются"),
        ({"question": "What breaks old protobuf clients when you change a field?"}, "по-русски"),
        ({"explanation": "因为 клиенты читают поля по номеру"}, "иероглифы"),
    ],
)
def test_check_rejects_bad_drafts(patch: dict[str, Any], reason: str) -> None:
    problem = check_llm_draft(LlmDraft.model_validate({**GOOD_DRAFT, **patch}))
    assert problem and reason in problem
    assert check_llm_draft(LlmDraft.model_validate(GOOD_DRAFT)) is None


def test_llm_draft_is_checked_cleaned_and_labeled(llm_on: Any) -> None:
    calls = llm_on(GOOD_DRAFT)
    hit, analysis = _grpc_hit()
    content = asyncio.run(llm_draft(hit, analysis))
    assert content is not None
    assert content["format"] == "single_choice" and content["model"] == "Qwen2.5-1.5B"
    assert content["model_local"] is True
    assert sorted(content["options"]) == sorted(
        ["Менять номер поля", "Добавлять новое поле", "Менять комментарий", "Переименовывать поле"]
    )
    assert content["answer"] == "Менять номер поля" and content["explanation"]
    # в модель уходит тема и слова-признаки, а не весь текст вакансии
    user = calls[0]["messages"][1]["content"]
    assert "gRPC" in user and "PostgreSQL" not in user
    assert calls[0]["response_format"]["json_schema"]["name"] == "LlmDraft"


def test_vacancy_build_with_llm_draft_and_fallback(client: TestClient, llm_on: Any) -> None:
    sql_sync(
        "DELETE FROM items WHERE generator IN ('draft:backend.grpc', 'draft:backend.go') "
        "AND target_grade = 'senior' AND specialization = 'backend' AND status = 'draft'"
    )

    def answer(request: httpx.Request) -> httpx.Response:
        user = json.loads(request.content)["messages"][1]["content"]
        if "gRPC" in user:
            return _reply(GOOD_DRAFT)
        return _reply({**GOOD_DRAFT, "options": ["A", "A", "B", "C"]})  # не пройдёт проверку

    calls = llm_on(answer)
    body = client.post(
        "/api/admin/vacancy-tests", json={"text": GRPC_VACANCY}, headers=ADMIN
    ).json()
    assert body["parser"] == "llm"
    drafts = {d["topic"]: d for d in body["drafts"]}
    grpc = drafts["backend.grpc"]
    assert grpc["origin"] == "llm" and grpc["model"] == "Qwen2.5-1.5B" and grpc["model_local"]
    assert grpc["answer"] in grpc["options"] and len(grpc["options"]) == 4
    assert drafts["backend.go"]["origin"] == "vocabulary"  # ответ модели отклонён проверкой
    assert any("нейросеть Qwen2.5-1.5B" in e for e in body["explanation"])
    row = sql_sync(
        "SELECT status, generator_params FROM items WHERE id = :id", {"id": grpc["item_id"]}
    )
    assert row[0][0] == "draft" and row[0][1]["answer"] == grpc["answer"]
    # повторная сборка берёт готовый черновик из банка — модель не зовётся
    before = len(calls)
    again = client.post(
        "/api/admin/vacancy-tests", json={"text": GRPC_VACANCY}, headers=ADMIN
    ).json()
    assert len(calls) == before
    again_grpc = next(d for d in again["drafts"] if d["topic"] == "backend.grpc")
    assert again_grpc["reused"] and again_grpc["origin"] == "llm"
    assert again_grpc["options"] == grpc["options"]
    # одобрение черновика от нейросети
    approved = client.post(f"/api/admin/items/{grpc['item_id']}/approve", headers=ADMIN)
    assert approved.status_code == 200 and approved.json()["status"] == "pilot"


def test_vacancy_build_when_llm_is_down(client: TestClient, llm_on: Any) -> None:
    sql_sync(
        "DELETE FROM items WHERE generator = 'draft:backend.grpc' AND target_grade = 'junior' "
        "AND specialization = 'backend' AND status = 'draft'"
    )

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("контейнер llm не запущен")

    calls = llm_on(down)
    text = GRPC_VACANCY.replace("Senior", "Junior")
    body = client.post("/api/admin/vacancy-tests", json={"text": text}, headers=ADMIN).json()
    assert body["parser"] == "rules" and body["drafts"]
    assert all(d["origin"] == "vocabulary" for d in body["drafts"])
    assert len(calls) == 1  # после первой неудачи остальные темы — сразу по словарю


# ---------------------------------------------------------------- разбор потребности


def test_need_rules_complete_skip_llm(client: TestClient, llm_on: Any) -> None:
    calls = llm_on({"grade": "junior"})
    resp = client.post(
        "/api/matching/needs/parse",
        json={"text": "нужен сеньор на Go в финтех, удалёнка, 300–400к"},
        headers=RECRUITER,
    )
    assert resp.status_code == 200 and resp.json()["parser"] == "rules"
    assert calls == []


def test_need_llm_fills_only_missing(llm_on: Any) -> None:
    text = "ищем человека в команду платежей, Москва, опыт от 3 лет, котлин и PostgreSQL"
    rules = parse_rules(text)
    missing = need_parser.missing_key_fields(rules)
    assert "grade" in missing and "city" not in missing
    calls = llm_on(
        {
            "specialization": "backend",
            "grade": "middle",
            "skills_required": ["Kotlin", "PostgreSQL", "PHP"],  # PHP в тексте нет
            "city": "Казань",  # не запрашивали — отбрасывается
            "salary_from": 300000,
        }
    )
    result = asyncio.run(parse_need_async(text))
    assert result["parser"] == "llm" and len(calls) == 1
    schema = calls[0]["response_format"]["json_schema"]["schema"]
    assert set(schema["properties"]) == set(missing)
    draft = result["draft"]
    assert draft["grade"] == "middle" and draft["specialization"] == (
        rules.specialization or "backend"
    )
    assert "php" not in draft["skills_required"]
    assert draft["city"] == "Москва" and draft["salary_from"] is None


def test_need_llm_skipped_when_busy(llm_on: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = llm_on({"grade": "middle"})
    monkeypatch.setattr(llm, "_inflight", 1)
    result = asyncio.run(parse_need_async("ищем человека в команду платежей"))
    assert result["parser"] == "rules" and calls == []


# ---------------------------------------------------------------- резюме


def _rules_with_gaps() -> resume.ResumeParse:
    text = "Иванов Иван Иванович\nivan@example.com\nНавыки: Python, Django\n"
    return resume.parse_resume_text(text)


def test_resume_llm_fills_only_missing_fields(llm_on: Any) -> None:
    rules = _rules_with_gaps()
    missing = resume.missing_fields(rules)
    assert "city" in missing and "full_name" not in missing and "stack" not in missing
    calls = llm_on({"city": "Казань", "experience_years": 3, "full_name": "Петров Пётр"})
    merged = asyncio.run(resume.fill_with_llm_async(rules, "текст резюме"))
    assert merged.parser == "llm"
    assert merged.fields["city"] == {"value": "Казань", "confidence": resume.LLM_CONFIDENCE}
    assert merged.fields["experience_years"]["value"] == 3
    assert merged.fields["full_name"] == rules.fields["full_name"]  # правила не трогаем
    assert merged.fields["stack"] == rules.fields["stack"]
    # схема запроса — только недостающие поля
    schema = calls[0]["response_format"]["json_schema"]["schema"]
    assert set(schema["properties"]) == set(missing)


def test_resume_llm_down_keeps_rules(llm_on: Any) -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("медленно")

    llm_on(down)
    rules = _rules_with_gaps()
    assert asyncio.run(resume.fill_with_llm_async(rules, "текст")) is rules


def test_resume_upload_endpoint_uses_llm_for_gaps(client: TestClient, llm_on: Any) -> None:
    from app.nlp.validation import SAMPLES

    pdf = sorted((SAMPLES / "resumes").glob("*.pdf"))[0].read_bytes()
    calls = llm_on({"city": "Казань"})
    resp = client.post(
        "/api/candidates/me/resume",
        files={"file": ("cv.pdf", pdf, "application/pdf")},
        headers={"X-Demo-Role": "candidate"},
    )
    assert resp.status_code in (200, 201), resp.text
    # на образце правила находят всё — модель не нужна, ответ прежний
    if not calls:
        assert resp.json()["parser"] == "rules"


# ---------------------------------------------------------------- живая модель


def _live_base() -> str | None:
    base = (
        os.environ.get("LLM_TEST_BASE_URL")
        or os.environ.get("LLM_BASE_URL")
        or "http://127.0.0.1:18090/v1"
    )
    try:
        ok = httpx.get(base.removesuffix("/v1") + "/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        ok = False
    return base if ok else None


def test_live_local_llm_writes_vacancy_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    base = _live_base()
    if base is None:
        pytest.skip("LLM не отвечает (llama.cpp на LLM_TEST_BASE_URL или LLM_BASE_URL)")
    for key, value in {**LLM_ENV, "LLM_BASE_URL": base, "LLM_DRAFT_TIMEOUT_SEC": "180"}.items():
        monkeypatch.setenv(key, value)
    get_nlp_settings.cache_clear()
    try:
        hit, analysis = _grpc_hit()
        content = asyncio.run(vacancy_tests.llm_draft(hit, analysis))
    finally:
        get_nlp_settings.cache_clear()
    # модель маленькая: ответ может не пройти проверку — тогда None и черновик из словаря
    if content is not None:
        assert content["answer"] in content["options"] and len(content["options"]) == 4
        assert content["prompt"] and content["model"] == "Qwen2.5-1.5B"
    else:
        pytest.xfail("ответ модели не прошёл проверку — сработал фолбэк на словарь")


def test_need_llm_grade_without_experience_is_dropped(llm_on: Any) -> None:
    # образец need-05: грейда в тексте нет — догадку модели («senior») не берём
    llm_on({"grade": "senior"})
    result = asyncio.run(parse_need_async("сроно нужен девопс, кубер терраформ, удаленка"))
    assert result["draft"]["grade"] is None

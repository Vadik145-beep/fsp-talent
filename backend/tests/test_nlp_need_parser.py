"""Разбор свободного текста потребности (T6.1): правила, метрика на образцах, LLM с откатом."""

import json

import httpx
import pytest

from app.matching.schemas import NeedParseResult
from app.nlp import llm
from app.nlp.need_parser import LlmNeed, merge_llm, parse_need, parse_rules
from app.nlp.settings import NlpSettings
from app.nlp.text_rules import detect_salary
from app.nlp.validation import need_rows


def test_samples_accuracy_at_least_10_of_12() -> None:
    rows = need_rows()
    assert len(rows) == 12
    ok = sum(r.ok for r in rows)
    assert ok >= 10, [(r.id, [f for f, v in r.fields.items() if not v]) for r in rows if not r.ok]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("300–400к", (300_000, 400_000)),
        ("от 250 тыс.", (250_000, None)),
        ("до 120к", (None, 120_000)),
        ("200-260 тысяч", (200_000, 260_000)),
        ("Вилка 250 000 – 300 000 руб.", (250_000, 300_000)),
        ("от 350 000 до 450 000 ₽ до вычета налогов", (350_000, 450_000)),
        ("100-140 т.р.", (100_000, 140_000)),
        ("гибрид спб, 180-230", (180_000, 230_000)),
        ("офис Новосибирск, 60 000", (60_000, 60_000)),
        ("от 150k", (150_000, None)),
    ],
)
def test_salary_forms(text: str, expected: tuple[int | None, int | None]) -> None:
    s = detect_salary(text)
    assert s is not None
    assert (s.salary_from, s.salary_to) == expected


@pytest.mark.parametrize(
    "text",
    ["опыт от 4 лет, команда 7 человек", "2 млн транзакций в сутки", "зп обсуждается", "5/2"],
)
def test_no_salary_where_there_is_none(text: str) -> None:
    assert detect_salary(text) is None


def test_unseen_phrases() -> None:
    """Формулировки, которых нет в образцах: правила не подогнаны под 12 строк."""
    p = parse_rules(
        "Требуется ведущий андроид-разработчик, котлин и компоуз, Питер, офис, до 400 т.р."
    )
    assert (p.specialization, p.grade, p.city, p.work_format) == (
        "mobile",
        "senior",
        "Санкт-Петербург",
        "office",
    )
    assert {s.code for s in p.required} >= {"kotlin", "jetpack_compose"}
    assert (p.salary_from, p.salary_to) == (None, 400_000)

    p = parse_rules("джун QA на автотесты: pytest, Postman. Плюсом — JMeter. Удалённо, 90-110к")
    assert (p.specialization, p.grade, p.work_format) == ("qa", "junior", "remote")
    assert {s.code for s in p.required} == {"pytest", "postman"}
    assert {s.code for s in p.desired} == {"jmeter"}
    assert (p.salary_from, p.salary_to) == (90_000, 110_000)

    p = parse_rules("Senior DevOps в банк, k8s/helm/terraform, гибрид, Екатеринбург, от 300к")
    assert (p.specialization, p.grade, p.city) == ("devops", "senior", "Екатеринбург")
    assert p.domains == ["банк"]


def test_parse_need_matches_contract() -> None:
    result = parse_need("ищем фронта на вью, мидл, гибрид мск, денег 200-250к, плюсом nuxt")
    model = NeedParseResult.model_validate(result)
    assert model.parser == "rules"
    assert model.draft.skills_required == ["vue"]
    assert model.draft.skills_desired == []  # Nuxt нет в справочнике стека
    assert model.unrecognized == ["Nuxt"]
    assert model.draft.title == "Middle Frontend (Vue)"
    assert "salary_from" in model.recognized_fields


# ---------------------------------------------------------------- LLM

LLM_ON = NlpSettings(llm_base_url="http://llm.local/v1", llm_api_key="k", llm_model="m")


def _transport(content: str, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer k"
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})

    return httpx.MockTransport(handler)


def test_llm_disabled_without_key() -> None:
    assert not llm.llm_enabled(NlpSettings())
    assert llm.complete_json("s", "u", LlmNeed, settings=NlpSettings()) is None


def test_llm_valid_json_is_parsed_and_merged() -> None:
    content = json.dumps(
        {
            "specialization": "backend",
            "grade": "senior",
            "skills_required": ["Golang", "Postgres"],
            "skills_desired": ["Kafka"],
            "work_format": "remote",
            "salary_from": 300000,
            "salary_to": 400000,
            "team_description": "платёжный шлюз",
        }
    )
    answer = llm.complete_json("s", "u", LlmNeed, settings=LLM_ON, transport=_transport(content))
    assert answer is not None
    merged = merge_llm(parse_rules("нужен сеньор на Go"), answer)
    assert merged.parser == "llm"
    assert [s.code for s in merged.required] == ["go", "postgresql"]
    assert [s.code for s in merged.desired] == ["kafka"]
    assert merged.team_description == "платёжный шлюз"


@pytest.mark.parametrize(
    ("content", "status"),
    [
        ("не JSON вовсе", 200),
        (json.dumps({"grade": "lead"}), 200),  # не проходит валидацию pydantic
        ("{}", 500),
    ],
)
def test_llm_errors_fall_back_to_none(content: str, status: int) -> None:
    transport = _transport(content, status)
    assert llm.complete_json("s", "u", LlmNeed, settings=LLM_ON, transport=transport) is None


def test_llm_fenced_json_is_accepted() -> None:
    content = '```json\n{"grade": "junior"}\n```'
    answer = llm.complete_json("s", "u", LlmNeed, settings=LLM_ON, transport=_transport(content))
    assert answer is not None and answer.grade == "junior"

"""Потребности и подборка на БД [ТЗ 2.1 «Функциональные требования к поиску и подбору»; T6.1–T6.4]:
CRUD, разбор текста, рекомендованные категории, ранжирование с объяснением (сумма вкладов = счёт),
веса из настроек, фильтры без потери подборки, исключение скрытых кандидатов, изоляция.
"""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.common import fixtures
from app.matching.parser import parse_need_text
from app.matching.scoring import normal_cdf
from app.matching.service import MatchingService
from app.nlp.similarity import stack_match
from app.seed.testkit import reseed_sync, sql_sync
from tests.conftest import RECRUITER, RECRUITER_C2

PRIVATE_KEYS = {"full_name", "email", "phone", "telegram", "min_salary", "fsp_id", "user_id"}
NEED = {
    "title": "Middle Python-разработчик",
    "raw_text": None,
    "specialization": "backend",
    "grade": "middle",
    "skills_required": ["Python", "postgresql"],
    "skills_desired": ["kafka"],
    "team_description": "Платёжный шлюз",
    "work_format": "remote",
    "city": None,
    "salary_from": 200000,
    "salary_to": 280000,
}


@pytest.fixture(scope="module", autouse=True)
def _restore_seed_after_module() -> Iterator[None]:
    yield
    reseed_sync()


@pytest.fixture(autouse=True)
def _fresh_db() -> None:
    reseed_sync()


def matches(client: TestClient, need_id: int = 1, **params: Any) -> Any:
    response = client.get(
        f"/api/matching/needs/{need_id}/candidates", params=params, headers=RECRUITER
    )
    assert response.status_code == 200, response.text
    return response.json()


def ids(result: Any) -> list[int]:
    return [m["candidate"]["id"] for m in result["items"]]


# ---------- разбор текста (T6.1, правила) ----------


def test_parse_free_text() -> None:
    result = parse_need_text("нужен сеньор на Go в финтех, удалёнка, 300–400к")
    draft = result["draft"]
    assert draft["specialization"] == "backend" and draft["grade"] == "senior"
    assert draft["skills_required"] == ["go"] and draft["work_format"] == "remote"
    assert (draft["salary_from"], draft["salary_to"]) == (300000, 400000)
    assert draft["team_description"] == "Сфера: Финтех"
    assert draft["title"] == "Senior Backend-разработчик (Go)"
    assert result["parser"] == "rules"

    second = parse_need_text(
        "Ищем мидл фронтендера: React и TypeScript, желательно Next.js, гибрид, Москва, "
        "от 200 до 260 тыс"
    )["draft"]
    assert second["specialization"] == "frontend" and second["grade"] == "middle"
    assert set(second["skills_required"]) == {"react", "typescript"}
    assert second["skills_desired"] == ["nextjs"]
    assert second["work_format"] == "hybrid" and second["city"] == "Москва"
    assert (second["salary_from"], second["salary_to"]) == (200000, 260000)
    # точка стыка с nlp (трек 3c) сохраняется
    assert MatchingService().parse("джун QA, автотесты на Python")["draft"]["grade"] == "junior"


def test_parse_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/matching/needs/parse",
        json={"text": "Senior DevOps, Kubernetes и Terraform, офис в Казани, 250-320к"},
        headers=RECRUITER,
    )
    assert response.status_code == 200
    draft = response.json()["draft"]
    assert draft["specialization"] == "devops" and draft["city"] == "Казань"
    assert {"kubernetes", "terraform"} <= set(draft["skills_required"])
    assert (
        client.post("/api/matching/needs/parse", json={"text": "x"}, headers=RECRUITER).status_code
        == 422
    )


# ---------- CRUD потребностей ----------


def test_need_crud(client: TestClient) -> None:
    created = client.post("/api/matching/needs", json=NEED, headers=RECRUITER)
    assert created.status_code == 201, created.text
    need = created.json()
    assert need["category"] == "backend:middle" and need["category_label"] == "Backend · Middle"
    assert need["skills_required"] == ["python", "postgresql"]
    assert need["company_id"] == 1 and need["status"] == "active"
    assert need["candidates_count"] == matches(client, need["id"])["total_before_filters"]

    listed = client.get("/api/matching/needs", headers=RECRUITER).json()
    assert listed[0]["id"] == need["id"] and {n["company_id"] for n in listed} == {1}
    assert client.get(f"/api/matching/needs/{need['id']}", headers=RECRUITER).json() == need

    updated = client.put(
        f"/api/matching/needs/{need['id']}",
        json={**NEED, "grade": "senior", "status": "closed"},
        headers=RECRUITER,
    ).json()
    assert updated["category"] == "backend:senior" and updated["status"] == "closed"

    assert client.delete(f"/api/matching/needs/{need['id']}", headers=RECRUITER).status_code == 204
    assert client.get(f"/api/matching/needs/{need['id']}", headers=RECRUITER).status_code == 404


def test_need_validation(client: TestClient) -> None:
    bad_range = client.post(
        "/api/matching/needs", json={**NEED, "salary_from": 300000}, headers=RECRUITER
    )
    assert bad_range.status_code == 422
    assert bad_range.json()["details"]["errors"][0]["type"] == "salary_range_invalid"
    no_salary = {k: v for k, v in NEED.items() if k != "salary_to"}
    assert client.post("/api/matching/needs", json=no_salary, headers=RECRUITER).status_code == 422
    unknown = client.post(
        "/api/matching/needs", json={**NEED, "skills_required": ["cobol"]}, headers=RECRUITER
    )
    assert unknown.status_code == 422 and unknown.json()["code"] == "unknown_skills"


def test_need_isolation(client: TestClient) -> None:
    other = next(n for n in fixtures.load("needs") if n["company_id"] != 1)
    base = f"/api/matching/needs/{other['id']}"
    assert client.get(base, headers=RECRUITER).status_code == 404
    assert client.get(f"{base}/categories", headers=RECRUITER).status_code == 404
    assert client.get(f"{base}/candidates", headers=RECRUITER).status_code == 404
    assert client.put(base, json=NEED, headers=RECRUITER).status_code == 404
    assert client.delete(base, headers=RECRUITER).status_code == 404
    assert client.get(base, headers=RECRUITER_C2).status_code == 200
    assert (
        client.get("/api/matching/needs", headers={"X-Demo-Role": "candidate"}).status_code == 403
    )


# ---------- категории (T6.2) ----------


def test_recommended_categories(client: TestClient) -> None:
    cats = client.get("/api/matching/needs/1/categories", headers=RECRUITER).json()
    assert [(c["category"], c["relation"]) for c in cats] == [
        ("backend:middle", "primary"),
        ("backend:junior", "grade_lower"),
        ("backend:senior", "grade_higher"),
        ("devops:middle", "adjacent_specialization"),
        ("data_ml:middle", "adjacent_specialization"),
    ]
    for c in cats:
        bank = client.get(
            "/api/candidates", params={"category": c["category"]}, headers=RECRUITER
        ).json()
        assert c["candidates_count"] == bank["total"], c["category"]
        # переход в категорию: подборка той же категории того же размера
        assert matches(client, category=c["category"])["total"] == c["candidates_count"]


# ---------- ранжирование с объяснением (T6.3) ----------


def test_ranking_is_explained_and_consistent(client: TestClient) -> None:
    result = matches(client)
    need = client.get("/api/matching/needs/1", headers=RECRUITER).json()
    assert result["items"] and result["total"] == result["total_before_filters"]
    scores = [m["score"] for m in result["items"]]
    assert scores == sorted(scores, reverse=True)
    for m in result["items"]:
        card = m["candidate"]
        assert card["category"] == "backend:middle"
        assert not PRIVATE_KEYS & set(card)
        assert 2 <= len(m["reasons"]) <= 4
        parts = {b["factor"]: b for b in m["breakdown"]}
        assert set(parts) == {"stack", "theta", "fsp", "freshness", "salary", "work_format"}
        assert abs(sum(b["contribution"] for b in m["breakdown"]) - m["score"]) < 1e-3
        assert abs(sum(b["weight"] for b in m["breakdown"]) - 1) < 1e-3
        for b in m["breakdown"]:
            assert abs(b["value"] * b["weight"] - b["contribution"]) < 1e-3
        # значения факторов — по формуле
        expected_stack = stack_match(need["skills_required"], need["skills_desired"], card["stack"])
        assert abs(parts["stack"]["value"] - expected_stack) < 1e-3
        theta = card["theta"]
        assert abs(parts["theta"]["value"] - (normal_cdf(theta) if theta is not None else 0)) < 1e-3
        fsp = (card["fsp_score"] or 0) / 100
        assert abs(parts["fsp"]["value"] - fsp) < 1e-3
        assert abs(parts["freshness"]["value"] - card["freshness"]) < 1e-3
    assert matches(client) == result, "выдача стабильна"


def test_salary_fit_does_not_reveal_amount(client: TestClient) -> None:
    raw = json.dumps(matches(client), ensure_ascii=False)
    assert '"min_salary"' not in raw
    sql_sync("UPDATE needs SET salary_from = 50000, salary_to = 60000 WHERE id = 1")
    low = matches(client)
    assert all(not m["salary_fit"] for m in low["items"])
    assert all(
        next(b for b in m["breakdown"] if b["factor"] == "salary")["value"] == 0
        for m in low["items"]
    )


def test_weights_from_platform_settings(client: TestClient) -> None:
    weights = {"stack": 0, "theta": 1, "fsp": 0, "freshness": 0, "salary": 0, "work_format": 0}
    sql_sync(
        "UPDATE platform_settings SET value = CAST(:v AS jsonb) WHERE key = 'ranking_weights'",
        {"v": json.dumps(weights)},
    )
    result = matches(client)
    for m in result["items"]:
        theta = next(b for b in m["breakdown"] if b["factor"] == "theta")
        assert theta["weight"] == 1 and abs(m["score"] - theta["value"]) < 1e-3
    thetas = [m["candidate"]["theta"] or -9 for m in result["items"]]
    assert thetas == sorted(thetas, reverse=True)


def test_fsp_is_bonus_without_penalty(client: TestClient) -> None:
    result = matches(client)
    for m in result["items"]:
        fsp = next(b for b in m["breakdown"] if b["factor"] == "fsp")
        if not m["candidate"]["has_fsp"]:
            assert fsp["value"] == 0 and fsp["contribution"] == 0
            assert not any("ФСП" in r for r in m["reasons"])
        elif fsp["value"] > 0:
            assert any(r.startswith("Подтверждено ФСП") for r in m["reasons"])


def test_invitation_status_in_results(client: TestClient) -> None:
    # кандидат 1 (backend:middle) принял приглашение компании 1
    item = next(m for m in matches(client)["items"] if m["candidate"]["id"] == 1)
    assert item["invitation_status"] == "accepted"


# ---------- фильтры без потери подборки (T6.4) ----------


def test_filters_narrow_and_reset(client: TestClient) -> None:
    sql_sync("UPDATE needs SET skills_required = '{python}', skills_desired = '{}' WHERE id = 1")
    base = matches(client)
    assert base["total"] >= 2
    for params in (
        {"skills": ["python"]},
        {"has_fsp": True},
        {"has_fsp": False},
        {"work_format": "remote"},
        {"city": base["items"][0]["candidate"]["city"] or "Казань"},
    ):
        narrowed = matches(client, **params)
        assert narrowed["total_before_filters"] == base["total"], params
        assert set(ids(narrowed)) <= set(ids(base)), params
        # порядок внутри подборки сохраняется
        assert ids(narrowed) == [i for i in ids(base) if i in set(ids(narrowed))]
        for m in narrowed["items"]:
            card = m["candidate"]
            if "skills" in params:
                assert "python" in card["stack"]
            if "has_fsp" in params:
                assert card["has_fsp"] is params["has_fsp"]
            if "work_format" in params:
                assert "remote" in card["work_formats"]
            if "city" in params:
                assert card["city"] == params["city"]
    combined = matches(client, skills=["python"], work_format="remote")
    assert combined["filters"] == {
        "skills": ["python"],
        "has_fsp": None,
        "work_format": "remote",
        "city": None,
    }
    assert matches(client) == base, "сброс фильтров возвращает исходную подборку"


def test_unknown_category_is_422(client: TestClient) -> None:
    response = client.get(
        "/api/matching/needs/1/candidates", params={"category": "nope:x"}, headers=RECRUITER
    )
    assert response.status_code == 422


# ---------- кто не попадает в выдачу ----------


def test_hidden_candidates_excluded(client: TestClient) -> None:
    base = set(ids(matches(client)))
    assert len(base) >= 3
    first, second, third = sorted(base)[:3]
    sql_sync(
        "UPDATE candidate_profiles SET publication_consent = false WHERE id = :i", {"i": first}
    )
    sql_sync("UPDATE candidate_profiles SET job_search_paused = true WHERE id = :i", {"i": second})
    sql_sync(
        "UPDATE users SET blocked = true "
        "WHERE id = (SELECT user_id FROM candidate_profiles WHERE id = :i)",
        {"i": third},
    )
    hidden = {first, second, third}
    after = matches(client)
    assert not hidden & set(ids(after))
    assert after["total_before_filters"] == len(base) - len(hidden)
    cats = client.get("/api/matching/needs/1/categories", headers=RECRUITER).json()
    assert cats[0]["candidates_count"] == len(base) - len(hidden)

"""Статус «грейд не подтверждён» (ответ организаторов FTT.4).

Грейд соискатель выбирает сам, но официально он присваивается только по результату теста.
Заявленный грейд виден соискателю и админу; в подборку и банк кандидатов он не пускает.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.common import fixtures
from app.seed.testkit import reseed_sync
from tests.conftest import ADMIN, CANDIDATE, RECRUITER, as_role
from tests.test_testing_api import run_to_end, start

CAND_40 = as_role("candidate", 40)  # QA, без грейда и тестов, согласие на публикацию есть
DECLARE = {"specialization": "qa", "grade": "junior"}


@pytest.fixture(scope="module", autouse=True)
def _restore_seed_after_module() -> Iterator[None]:
    yield
    reseed_sync()


@pytest.fixture(autouse=True)
def _fresh_db() -> None:
    reseed_sync()


def bank_ids(client: TestClient, **params: Any) -> set[int]:
    """id всех кандидатов банка по фильтру (с листанием: в демо-базе больше 100 кандидатов)."""
    ids: set[int] = set()
    page = 1
    while True:
        query = {"page_size": 100, "page": page, **params}
        r = client.get("/api/candidates", params=query, headers=RECRUITER)
        assert r.status_code == 200, r.text
        ids |= {c["id"] for c in r.json()["items"]}
        if page * 100 >= r.json()["total"]:
            return ids
        page += 1


def qa_need(client: TestClient) -> dict[str, Any]:
    skill = fixtures.by_id("candidates", 40)["stack"][0]  # type: ignore[index]
    body = {
        "title": "QA-инженер",
        "raw_text": None,
        "specialization": "qa",
        "grade": "junior",
        "skills_required": [skill],
        "skills_desired": [],
        "team_description": "",
        "work_format": "remote",
        "city": None,
        "salary_from": 80000,
        "salary_to": 150000,
    }
    r = client.post("/api/matching/needs", json=body, headers=RECRUITER)
    assert r.status_code == 201, r.text
    need: dict[str, Any] = r.json()
    return need


def admin_row(client: TestClient, user_id: int) -> dict[str, Any]:
    email = fixtures.by_id("users", user_id)["email"]  # type: ignore[index]
    r = client.get("/api/admin/users", params={"q": email}, headers=ADMIN)
    assert r.status_code == 200, r.text
    row: dict[str, Any] = next(u for u in r.json()["items"] if u["id"] == user_id)
    return row


def test_declared_grade_is_unconfirmed_and_not_in_selection(client: TestClient) -> None:
    profile = client.get("/api/candidates/me/profile", headers=CAND_40).json()
    assert profile["grade"] is None and profile["grade_status"] == "none"
    assert admin_row(client, 40)["grade_status"] == "none"
    need = qa_need(client)
    count_before = need["candidates_count"]

    r = client.put("/api/candidates/me/declared-grade", json=DECLARE, headers=CAND_40)
    assert r.status_code == 200, r.text
    status = r.json()
    assert status["grade_status"] == "unconfirmed"
    assert status["declared_grade"] == "junior" and status["declared_specialization"] == "qa"
    assert status["grade"] is None and status["grade_confirmed_at"] is None

    profile = client.get("/api/candidates/me/profile", headers=CAND_40).json()
    assert profile["grade_status"] == "unconfirmed" and profile["declared_at"]
    assert profile["grade"] is None and profile["category"] is None
    dashboard = client.get("/api/candidates/me/dashboard", headers=CAND_40).json()
    assert dashboard["grade_status"] == "unconfirmed" and not dashboard["onboarding_completed"]
    assert any("Junior не подтверждён" in h for h in dashboard["hints"])

    # явное правило: заявленный грейд не пускает в банк кандидатов и подборку
    assert 40 not in bank_ids(client)
    assert 40 not in bank_ids(client, specialization="qa", grade="junior")
    found = client.get(f"/api/matching/needs/{need['id']}/candidates", headers=RECRUITER).json()
    assert 40 not in {m["candidate"]["id"] for m in found["items"]}
    again = client.get(f"/api/matching/needs/{need['id']}", headers=RECRUITER).json()
    assert again["candidates_count"] == count_before
    assert client.get("/api/candidates/40", headers=RECRUITER).status_code == 404

    row = admin_row(client, 40)
    assert row["grade_status"] == "unconfirmed" and row["grade_label"] == "QA · Junior"


def test_passed_test_confirms_grade(client: TestClient) -> None:
    client.put("/api/candidates/me/declared-grade", json=DECLARE, headers=CAND_40)
    state = start(client, CAND_40, "qa", "junior")
    run_to_end(client, CAND_40, state, right=True)
    grade = client.get("/api/candidates/me/grade", headers=CAND_40).json()
    assert grade["grade_status"] == "confirmed" and grade["grade"] is not None
    assert grade["grade_confirmed_at"] is not None
    profile = client.get("/api/candidates/me/profile", headers=CAND_40).json()
    assert profile["grade_status"] == "confirmed" and profile["grade_confirmed_at"]
    assert 40 in bank_ids(client, specialization="qa")
    assert admin_row(client, 40)["grade_status"] == "confirmed"


def test_failed_test_keeps_unconfirmed(client: TestClient) -> None:
    state = start(client, CAND_40, "qa", "middle")  # старт теста тоже заявляет грейд
    status = client.get("/api/candidates/me/grade", headers=CAND_40).json()
    assert status["grade_status"] == "unconfirmed" and status["declared_grade"] == "middle"
    run_to_end(client, CAND_40, state, right=False)
    status = client.get("/api/candidates/me/grade", headers=CAND_40).json()
    assert status["grade_status"] == "unconfirmed" and status["grade"] is None
    assert 40 not in bank_ids(client)


def test_seed_candidate_confirmed_and_other_roles_without_status(client: TestClient) -> None:
    profile = client.get("/api/candidates/me/profile", headers=CANDIDATE).json()
    assert profile["grade_status"] == "confirmed" and profile["grade_confirmed_at"]
    grade = client.get("/api/testing/grade", headers=CANDIDATE).json()
    assert grade["grade_status"] == "confirmed"
    recruiter_user = next(u for u in fixtures.all_records("users") if u["role"] == "recruiter")
    assert admin_row(client, recruiter_user["id"])["grade_status"] is None


def test_declare_validation(client: TestClient) -> None:
    bad = client.put(
        "/api/candidates/me/declared-grade",
        json={"specialization": "qa", "grade": "guru"},
        headers=CAND_40,
    )
    assert bad.status_code == 422
    assert client.put("/api/candidates/me/declared-grade", json=DECLARE).status_code == 401
    assert (
        client.put("/api/candidates/me/declared-grade", json=DECLARE, headers=RECRUITER).status_code
        == 403
    )

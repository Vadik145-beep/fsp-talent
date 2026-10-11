"""Компания рекрутера на БД: профиль, права администратора компании, рекрутеры, дашборд."""

from collections import Counter
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.common import fixtures
from app.seed.testkit import reseed_sync, sql_sync
from tests.conftest import RECRUITER, RECRUITER_C2, as_role

RECRUITER_NOT_ADMIN = as_role("recruiter", 42)  # рекрутер компании 1 без прав администратора

UPDATE = {
    "name": "Северный код (обновлено)",
    "description": "Платёжные сервисы",
    "industry": "Финтех",
    "website": "https://severny-kod.example.com",
    "city": "Москва",
    "contact_email": "hr@example.com",
    "contact_phone": "+7 900 000-10-01",
}


@pytest.fixture(autouse=True, scope="module")
def _fresh_db_module() -> Iterator[None]:
    reseed_sync()
    yield
    reseed_sync()


def test_company_profile_and_update(client: TestClient) -> None:
    company = client.get("/api/companies/my", headers=RECRUITER).json()
    src = fixtures.by_id("companies", 1)
    assert src is not None
    assert company["name"] == src["name"] and company["created_at"] == src["created_at"]
    forbidden = client.put("/api/companies/my", json=UPDATE, headers=RECRUITER_NOT_ADMIN)
    assert forbidden.status_code == 403
    saved = client.put("/api/companies/my", json=UPDATE, headers=RECRUITER)
    assert saved.status_code == 200 and saved.json()["name"] == UPDATE["name"]
    assert sql_sync("SELECT name FROM companies WHERE id = 1")[0][0] == UPDATE["name"]
    assert client.get("/api/companies/my", headers=RECRUITER).json()["city"] == "Москва"
    invalid = client.put("/api/companies/my", json={**UPDATE, "name": "X"}, headers=RECRUITER)
    assert invalid.status_code == 422
    other = client.get("/api/companies/my", headers=RECRUITER_C2).json()
    assert other["id"] == 2


def test_recruiters_from_db(client: TestClient) -> None:
    recruiters = client.get("/api/companies/my/recruiters", headers=RECRUITER).json()
    expected = [r for r in fixtures.load("recruiters") if r["company_id"] == 1]
    assert recruiters == expected


def test_dashboard_counts_from_db(client: TestClient) -> None:
    dashboard = client.get("/api/companies/my/dashboard", headers=RECRUITER).json()
    invs = [i for i in fixtures.load("invitations") if i["company_id"] == 1]
    assert dashboard["invitations_by_status"] == dict(Counter(i["status"] for i in invs))
    active_mine = sum(
        1 for i in invs if i["recruiter_id"] == 1 and i["status"] in ("sent", "viewed")
    )
    assert dashboard["quota"] == {"limit": 20, "used": active_mine, "left": 20 - active_mine}
    needs = [n for n in fixtures.load("needs") if n["company_id"] == 1 and n["status"] == "active"]
    assert {n["id"] for n in dashboard["active_needs"]} == {n["id"] for n in needs}
    vacancies = {v["id"] for v in fixtures.load("vacancies") if v["company_id"] == 1}
    new_apps = [
        a
        for a in fixtures.load("applications")
        if a["vacancy_id"] in vacancies and a["status"] == "new"
    ]
    assert dashboard["new_applications_count"] == len(new_apps)
    # отклик — кандидат сам открыл контакты: на главной имя, а не только псевдоним
    names = {c["id"]: c["full_name"] for c in fixtures.load("candidates")}
    by_id = {a["id"]: a for a in new_apps}
    for brief in dashboard["recent_applications"]:
        assert brief["candidate_name"] == names[by_id[brief["id"]]["candidate_id"]]

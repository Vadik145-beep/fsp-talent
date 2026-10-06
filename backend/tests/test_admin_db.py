"""Админка на БД: пользователи (поиск, блокировка, роль), компании, журнал действий."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.common import fixtures
from app.seed.testkit import reseed_sync, sql_sync
from tests.conftest import ADMIN, RECRUITER, as_role


@pytest.fixture(autouse=True, scope="module")
def _fresh_db_module() -> Iterator[None]:
    reseed_sync()
    yield
    reseed_sync()


@pytest.fixture
def fresh_db() -> None:
    reseed_sync()


def test_users_search_and_filters(client: TestClient) -> None:
    all_users = client.get("/api/admin/users", params={"page_size": 200}, headers=ADMIN).json()
    assert all_users["total"] == len(fixtures.load("users"))
    recruiters = client.get("/api/admin/users", params={"role": "recruiter"}, headers=ADMIN).json()
    assert recruiters["total"] == 7 and all(u["role"] == "recruiter" for u in recruiters["items"])
    found = client.get("/api/admin/users", params={"q": "CANDIDATE@"}, headers=ADMIN).json()
    assert [u["id"] for u in found["items"]] == [1]
    by_name = client.get("/api/admin/users", params={"q": "Латыпов"}, headers=ADMIN).json()
    assert 1 in {u["id"] for u in by_name["items"]}
    blocked = client.get("/api/admin/users", params={"blocked": "true"}, headers=ADMIN).json()
    assert {u["id"] for u in blocked["items"]} == {
        u["id"] for u in fixtures.load("users") if u["blocked"]
    }
    page = client.get("/api/admin/users", params={"page": 2, "page_size": 10}, headers=ADMIN)
    assert [u["id"] for u in page.json()["items"]] == list(range(11, 21))


def test_block_and_unblock_user(client: TestClient, fresh_db: None) -> None:
    bank = client.get("/api/candidates", params={"page_size": 100}, headers=RECRUITER).json()
    assert 2 in {c["id"] for c in bank["items"]}
    response = client.patch("/api/admin/users/2", json={"blocked": True}, headers=ADMIN)
    assert response.status_code == 200 and response.json()["blocked"] is True
    assert sql_sync("SELECT blocked FROM users WHERE id = 2")[0][0] is True
    # заблокированный кандидат пропадает из выдачи
    bank = client.get("/api/candidates", params={"page_size": 100}, headers=RECRUITER).json()
    assert 2 not in {c["id"] for c in bank["items"]}
    journal = client.get("/api/admin/users/2/audit", headers=ADMIN).json()
    assert journal[0]["action"] == "user_blocked" and journal[0]["actor_user_id"] == 48
    client.patch("/api/admin/users/2", json={"blocked": False}, headers=ADMIN)
    actions = [a["action"] for a in client.get("/api/admin/users/2/audit", headers=ADMIN).json()]
    assert actions[:2] == ["user_unblocked", "user_blocked"]
    # повторная блокировка без изменений журнал не засоряет
    client.patch("/api/admin/users/2", json={"blocked": False}, headers=ADMIN)
    assert len(client.get("/api/admin/users/2/audit", headers=ADMIN).json()) == len(actions)


def test_change_role(client: TestClient, fresh_db: None) -> None:
    promoted = client.patch("/api/admin/users/42", json={"role": "admin"}, headers=ADMIN)
    assert promoted.status_code == 200 and promoted.json()["role"] == "admin"
    entry = client.get("/api/admin/audit", params={"action": "user_role_changed"}, headers=ADMIN)
    item = entry.json()["items"][0]
    assert item["target_id"] == 42 and item["details"] == {"role": ["recruiter", "admin"]}
    back = client.patch("/api/admin/users/42", json={"role": "recruiter"}, headers=ADMIN)
    assert back.json()["role"] == "recruiter"
    # роль без профиля не назначается
    wrong = client.patch("/api/admin/users/2", json={"role": "recruiter"}, headers=ADMIN)
    assert wrong.status_code == 409 and wrong.json()["code"] == "role_profile_missing"
    wrong = client.patch("/api/admin/users/41", json={"role": "candidate"}, headers=ADMIN)
    assert wrong.status_code == 409
    assert (
        client.patch("/api/admin/users/999", json={"blocked": True}, headers=ADMIN).status_code
        == 404
    )


def test_cannot_block_or_demote_self(client: TestClient, fresh_db: None) -> None:
    for body in ({"blocked": True}, {"role": "recruiter"}):
        response = client.patch("/api/admin/users/48", json=body, headers=ADMIN)
        assert response.status_code == 409 and response.json()["code"] == "cannot_change_self"
    other_admin = as_role("admin", 49)
    blocked = client.patch("/api/admin/users/48", json={"blocked": True}, headers=other_admin)
    assert blocked.status_code == 200


def test_companies_scoring_and_block(client: TestClient, fresh_db: None) -> None:
    companies = {c["id"]: c for c in client.get("/api/admin/companies", headers=ADMIN).json()}
    assert set(companies) == {1, 2, 3}
    first = companies[1]
    invs = [i for i in fixtures.load("invitations") if i["company_id"] == 1]
    assert first["invitations_sent"] == len(invs)
    answered = sum(1 for i in invs if i["status"] in ("accepted", "declined"))
    decided = answered + sum(1 for i in invs if i["status"] == "expired")
    assert first["response_rate"] == round(answered / decided, 2)
    assert first["recruiters_count"] == 3
    for c in companies.values():
        assert 0 <= c["trust_score"] <= 100
    # жалобы снижают скоринг: подтверждаем жалобу на компанию 3
    before = companies[3]["trust_score"]
    sql_sync("UPDATE reports SET status = 'resolved' WHERE company_id = 3")
    after = {c["id"]: c for c in client.get("/api/admin/companies", headers=ADMIN).json()}[3]
    assert after["trust_score"] < before

    blocked = client.patch("/api/admin/companies/2", json={"blocked": True}, headers=ADMIN)
    assert blocked.status_code == 200 and blocked.json()["blocked"] is True
    assert sql_sync("SELECT blocked FROM companies WHERE id = 2")[0][0] is True
    audit = client.get("/api/admin/audit", params={"target_type": "company"}, headers=ADMIN)
    assert audit.json()["items"][0]["action"] == "company_blocked"
    assert (
        client.patch("/api/admin/companies/99", json={"blocked": True}, headers=ADMIN).status_code
        == 404
    )


def test_audit_log_from_db(client: TestClient, fresh_db: None) -> None:
    body = client.get("/api/admin/audit", params={"page_size": 200}, headers=ADMIN).json()
    assert body["total"] == len(fixtures.load("audit_log"))
    dates = [a["at"] for a in body["items"]]
    assert dates == sorted(dates, reverse=True)
    grade = client.get("/api/admin/audit", params={"action": "grade_changed"}, headers=ADMIN)
    assert all(a["action"] == "grade_changed" for a in grade.json()["items"])

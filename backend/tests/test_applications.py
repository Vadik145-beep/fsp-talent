"""Отклики на БД [ТЗ 2.1, 2.2; T8.2, T8.3]: отклик кандидата, контакты компании сразу после
отклика (и не раньше) + audit_log, один отклик на вакансию, статусы и их видимость обеим
сторонам, изоляция компаний, письма в фоне.

Каждый тест начинает с чистого сида — тесты не зависят друг от друга.
"""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.common import fixtures
from app.common.enums import ApplicationStatus
from app.seed.testkit import reseed_sync, sql_sync
from app.vacancies.service import APPLICATION_TRANSITIONS, can_application_transition
from tests.conftest import CANDIDATE, CANDIDATE_NO_FSP, RECRUITER, RECRUITER_C2, as_role

RECRUITER_C3 = as_role("recruiter", 46)  # рекрутер компании 3 («Тайга», вакансия 7)
C3_EMAILS = ["v.ershov.hr@example.com", "a.pestova.hr@example.com"]


@pytest.fixture(scope="module", autouse=True)
def _restore_seed_after_module() -> Iterator[None]:
    yield
    reseed_sync()


@pytest.fixture(autouse=True)
def _fresh_db() -> None:
    reseed_sync()


@pytest.fixture
def mails(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    sent: list[dict[str, str]] = []

    def fake_send(to: str, subject: str, text: str, html: str | None = None) -> None:
        sent.append({"to": to, "subject": subject, "text": text})

    monkeypatch.setattr("app.core.email.send_email", fake_send)
    return sent


def candidate(candidate_id: int) -> dict[str, Any]:
    cand = fixtures.by_id("candidates", candidate_id)
    assert cand is not None
    return cand


def apply(
    client: TestClient, vacancy_id: int, headers: dict[str, str] = CANDIDATE, letter: str = ""
) -> Any:
    response = client.post(
        f"/api/vacancies/{vacancy_id}/applications",
        json={"cover_letter": letter},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def set_status(client: TestClient, app_id: int, status: str, headers: dict[str, str]) -> Any:
    return client.patch(f"/api/applications/{app_id}", json={"status": status}, headers=headers)


def my_status(client: TestClient, app_id: int, headers: dict[str, str] = CANDIDATE) -> str:
    mine = client.get("/api/applications", headers=headers).json()
    return str(next(a["status"] for a in mine if a["id"] == app_id))


# ---------- машина состояний (без БД) ----------


def test_transition_table() -> None:
    s = ApplicationStatus
    assert can_application_transition(s.new, s.viewed)
    assert can_application_transition(s.viewed, s.invited)
    assert can_application_transition(s.viewed, s.rejected)
    assert can_application_transition(s.new, s.rejected)
    assert can_application_transition(s.invited, s.rejected)
    assert can_application_transition(s.rejected, s.invited)
    for back in (s.new, s.viewed):
        assert not can_application_transition(s.invited, back)
        assert not can_application_transition(s.rejected, back)
    assert not can_application_transition(s.viewed, s.new)
    assert set(APPLICATION_TRANSITIONS) == set(s)


# ---------- контакты: до и после отклика ----------


def test_contacts_hidden_before_and_open_right_after_apply(
    client: TestClient, mails: list[dict[str, str]]
) -> None:
    cand = candidate(1)
    private = [cand["full_name"], cand["email"], cand["phone"], cand["telegram"]]

    # до отклика компания 3 видит только обезличенный профиль
    before = client.get("/api/candidates/1", headers=RECRUITER_C3).json()
    assert before["contacts"] is None
    raw = json.dumps(before, ensure_ascii=False)
    assert not any(v in raw for v in private)
    assert client.get("/api/vacancies/7/applications", headers=RECRUITER_C3).json()
    assert all(
        a["candidate_id"] != 1 for a in client.get("/api/applications", headers=RECRUITER_C3).json()
    )

    created = apply(client, 7, letter="  Есть опыт с Kubernetes и Terraform.  ")
    assert created["status"] == "new"
    assert created["vacancy_title"] == "DevOps-инженер"
    assert created["company_id"] == 3 and created["company_name"] == "Облачные системы «Тайга»"
    assert created["cover_letter"] == "Есть опыт с Kubernetes и Terraform."
    # кандидату — без карточки и контактов
    assert created["candidate"] is None and created["candidate_contacts"] is None

    # сразу после отклика компания видит контакты: в откликах и в профиле
    apps = client.get("/api/vacancies/7/applications", headers=RECRUITER_C3).json()
    assert apps[0]["id"] == created["id"], "новые отклики сверху"
    assert apps[0]["candidate_contacts"] == {
        "full_name": cand["full_name"],
        "email": cand["email"],
        "phone": cand["phone"],
        "telegram": cand["telegram"],
    }
    assert apps[0]["candidate"]["category_label"] == "Backend · Middle"
    company_apps = client.get("/api/applications", headers=RECRUITER_C3).json()
    assert next(a for a in company_apps if a["id"] == created["id"])["candidate_contacts"]
    after = client.get("/api/candidates/1", headers=RECRUITER_C3).json()
    assert after["contacts"]["email"] == cand["email"]
    # другой компании контакты не открылись
    assert client.get("/api/candidates/26", headers=RECRUITER_C2).json()["contacts"] is None

    # раскрытие — в audit_log
    audit = sql_sync(
        "SELECT action, actor_role, details FROM audit_log "
        "WHERE target_type = 'application' AND target_id = :id",
        {"id": created["id"]},
    )
    assert len(audit) == 1
    action, role, details = audit[0]
    assert (action, role) == ("contacts_revealed", "candidate")
    assert details == {"candidate_id": 1, "company_id": 3, "vacancy_id": 7}

    # письмо рекрутерам компании о новом отклике
    assert sorted(m["to"] for m in mails) == sorted(C3_EMAILS)
    assert all("Новый отклик" in m["subject"] and "DevOps" in m["subject"] for m in mails)
    assert "Kubernetes" in mails[0]["text"] and cand["email"] in mails[0]["text"]


def test_application_is_stored_in_db(client: TestClient) -> None:
    created = apply(client, 2, letter="Привет")
    rows = sql_sync(
        "SELECT vacancy_id, candidate_id, cover_letter, status FROM applications WHERE id = :id",
        {"id": created["id"]},
    )
    assert [tuple(r) for r in rows] == [(2, 1, "Привет", "new")]


# ---------- ограничения отклика ----------


def test_second_application_is_409(client: TestClient) -> None:
    created = apply(client, 7)
    again = client.post("/api/vacancies/7/applications", json={}, headers=CANDIDATE)
    assert again.status_code == 409
    assert again.json()["code"] == "already_applied"
    assert again.json()["details"] == {"application_id": created["id"]}
    # отклик из сида (кандидат 1 → вакансия 1)
    seed_dup = client.post("/api/vacancies/1/applications", json={}, headers=CANDIDATE)
    assert seed_dup.status_code == 409
    count = sql_sync("SELECT count(*) FROM applications WHERE candidate_id = 1 AND vacancy_id = 7")
    assert count[0][0] == 1


def test_apply_only_to_published(client: TestClient) -> None:
    for vacancy_id in (8, 6, 999999):  # черновик, снята, нет такой
        response = client.post(
            f"/api/vacancies/{vacancy_id}/applications", json={}, headers=CANDIDATE
        )
        assert response.status_code == 404, vacancy_id
        assert response.json()["code"] == "not_found"
    client.post("/api/vacancies/2/unpublish", headers=RECRUITER)
    gone = client.post("/api/vacancies/2/applications", json={}, headers=CANDIDATE)
    assert gone.status_code == 404


def test_cover_letter_limit(client: TestClient) -> None:
    long = client.post(
        "/api/vacancies/7/applications", json={"cover_letter": "я" * 3001}, headers=CANDIDATE
    )
    assert long.status_code == 422
    assert apply(client, 7)["cover_letter"] == "", "письмо необязательно"


def test_roles(client: TestClient) -> None:
    by_recruiter = client.post("/api/vacancies/1/applications", json={}, headers=RECRUITER)
    assert by_recruiter.status_code == 403
    by_candidate = set_status(client, 3, "viewed", CANDIDATE)
    assert by_candidate.status_code == 403
    assert client.get("/api/applications").status_code == 401


# ---------- статусы и видимость обеим сторонам ----------


def test_status_flow_visible_to_both_sides(client: TestClient, mails: list[dict[str, str]]) -> None:
    app_id = apply(client, 7)["id"]
    mails.clear()
    assert my_status(client, app_id) == "new"

    viewed = set_status(client, app_id, "viewed", RECRUITER_C3)
    assert viewed.status_code == 200, viewed.text
    assert viewed.json()["status"] == "viewed" and viewed.json()["candidate_contacts"]
    assert my_status(client, app_id) == "viewed"

    invited = set_status(client, app_id, "invited", RECRUITER_C3).json()
    assert invited["status"] == "invited"
    assert my_status(client, app_id) == "invited"
    apps = client.get("/api/vacancies/7/applications", headers=RECRUITER_C3).json()
    assert next(a for a in apps if a["id"] == app_id)["status"] == "invited"

    # назад нельзя
    for back in ("new", "viewed"):
        response = set_status(client, app_id, back, RECRUITER_C3)
        assert response.status_code == 409, back
        assert response.json()["code"] == "invalid_transition"
        assert response.json()["details"] == {"from": "invited", "to": back}
    # исправление решения — можно
    assert set_status(client, app_id, "rejected", RECRUITER_C3).json()["status"] == "rejected"
    assert my_status(client, app_id) == "rejected"
    # тот же статус — без изменений и без письма
    sent_before = len(mails)
    assert set_status(client, app_id, "rejected", RECRUITER_C3).status_code == 200
    assert len(mails) == sent_before

    # письма кандидату о каждой смене статуса
    assert [m["to"] for m in mails] == ["candidate@example.com"] * 3
    assert "Просмотрен" in mails[0]["subject"]
    assert "Приглашён" in mails[1]["subject"] and "пообщаться" in mails[1]["text"]
    assert "Отказ" in mails[2]["subject"]

    updated = sql_sync("SELECT status FROM applications WHERE id = :id", {"id": app_id})
    assert updated[0][0] == "rejected"


def test_unknown_status_is_422(client: TestClient) -> None:
    response = set_status(client, 3, "hired", RECRUITER)
    assert response.status_code == 422


def test_unavailable_smtp_does_not_break_requests(client: TestClient) -> None:
    # в тестах SMTP_PORT=1 — письма не уходят, но отклик и смена статуса проходят
    app_id = apply(client, 7)["id"]
    assert set_status(client, app_id, "viewed", RECRUITER_C3).status_code == 200


# ---------- изоляция ----------


def test_isolation(client: TestClient) -> None:
    # чужой отклик неотличим от несуществующего
    foreign = set_status(client, 3, "viewed", RECRUITER_C2)  # отклик на вакансию компании 1
    assert foreign.status_code == 404 and foreign.json()["code"] == "not_found"
    assert set_status(client, 999999, "viewed", RECRUITER).status_code == 404
    assert client.get("/api/vacancies/1/applications", headers=RECRUITER_C2).status_code == 404

    c2 = client.get("/api/applications", headers=RECRUITER_C2).json()
    assert c2 and {a["company_id"] for a in c2} == {2}
    seed_c2 = {a["id"] for a in fixtures.load("applications") if a["company_id"] == 2}
    assert {a["id"] for a in c2} == seed_c2

    mine = client.get("/api/applications", headers=CANDIDATE).json()
    assert {a["candidate_id"] for a in mine} == {1}
    assert all(a["candidate"] is None and a["candidate_contacts"] is None for a in mine)
    other = client.get("/api/applications", headers=CANDIDATE_NO_FSP).json()
    assert {a["id"] for a in other} == {5}


def test_recruiter_sees_category_and_test_result(client: TestClient) -> None:
    apps = client.get("/api/applications", headers=RECRUITER).json()
    seed_c1 = [a for a in fixtures.load("applications") if a["company_id"] == 1]
    assert len(apps) == len(seed_c1)
    for a in apps:
        card = a["candidate"]
        assert card["category"] and card["category_label"], a["id"]
        assert "theta" in card and "topic_scores" in card
        assert a["candidate_contacts"]["email"]
        # в обезличенной карточке нет личных полей — они только в candidate_contacts
        assert not {"full_name", "email", "phone", "telegram", "min_salary"} & set(card)
    assert [a["created_at"] for a in apps] == sorted((a["created_at"] for a in apps), reverse=True)


def test_dashboard_counts_new_applications(client: TestClient) -> None:
    before = client.get("/api/companies/my/dashboard", headers=RECRUITER_C3)
    assert before.status_code == 200, before.text
    count = before.json()["new_applications_count"]
    apply(client, 7)
    after = client.get("/api/companies/my/dashboard", headers=RECRUITER_C3).json()
    assert after["new_applications_count"] == count + 1

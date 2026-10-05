"""По тесту (минимум) на каждый роутер: заглушки отдают данные из фикстур data/seed."""

import io

from fastapi.testclient import TestClient

from app.common import fixtures
from tests.conftest import ADMIN, CANDIDATE, CANDIDATE_NO_FSP, RECRUITER


def test_auth_login_and_me(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"email": "candidate@example.com", "password": "demo1234"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["user"]["fsp_id"] == "FSP-000001"
    assert "refresh_token" in response.cookies
    refreshed = client.post("/api/auth/refresh")
    assert refreshed.status_code == 200
    assert client.post("/api/auth/logout").status_code == 204
    bad = client.post("/api/auth/login", json={"email": "candidate@example.com", "password": "x"})
    assert bad.status_code == 401 and bad.json()["code"] == "invalid_credentials"


def test_auth_register_and_verify(client: TestClient) -> None:
    body = {
        "email": "new.user@example.com",
        "password": "S3cure-pass",
        "full_name": "Новый Пользователь",
        "role": "candidate",
        "consent_processing": True,
    }
    assert client.post("/api/auth/register", json=body).status_code == 201
    taken = client.post("/api/auth/register", json={**body, "email": "candidate@example.com"})
    assert taken.status_code == 409 and taken.json()["code"] == "email_taken"
    no_consent = client.post("/api/auth/register", json={**body, "consent_processing": False})
    assert no_consent.status_code == 422
    assert client.post("/api/auth/verify-email", json={"token": "expired-token"}).status_code == 410
    url = client.get("/api/auth/fsp/authorize-url").json()["authorize_url"]
    assert "/realms/fsp/" in url


def test_users_consents(client: TestClient) -> None:
    consents = client.get("/api/users/me/consents", headers=CANDIDATE).json()
    assert {c["type"] for c in consents} == {"processing", "publication"}
    revoke = client.put(
        "/api/users/me/consents/publication", json={"granted": False}, headers=CANDIDATE
    )
    assert revoke.status_code == 200 and revoke.json()["revoked_at"]
    forbidden = client.put(
        "/api/users/me/consents/processing", json={"granted": False}, headers=CANDIDATE
    )
    assert forbidden.status_code == 409


def test_catalog(client: TestClient) -> None:
    assert len(client.get("/api/catalog/specializations").json()) == 6
    assert [g["id"] for g in client.get("/api/catalog/grades").json()] == [
        "intern",
        "junior",
        "middle",
        "senior",
    ]
    assert len(client.get("/api/catalog/categories").json()) == 24
    skills = client.get("/api/catalog/skills", params={"specialization": "mobile"}).json()
    assert all("mobile" in s["specializations"] for s in skills)
    assert len(client.get("/api/catalog/decline-reasons").json()) == 5


def test_candidates_own_cabinet(client: TestClient) -> None:
    profile = client.get("/api/candidates/me/profile", headers=CANDIDATE).json()
    assert profile == fixtures.by_id("candidates", 1)
    dashboard = client.get("/api/candidates/me/dashboard", headers=CANDIDATE).json()
    assert dashboard["category"] == "backend:middle"
    no_fsp = client.get("/api/candidates/me/dashboard", headers=CANDIDATE_NO_FSP).json()
    assert no_fsp["fsp_linked"] is False and no_fsp["hints"]
    pdf = client.get("/api/candidates/me/profile.pdf", headers=CANDIDATE)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    resume = client.post(
        "/api/candidates/me/resume",
        files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=CANDIDATE,
    )
    assert resume.status_code == 200
    settings = client.put(
        "/api/candidates/me/settings/job-search", json={"paused": True}, headers=CANDIDATE
    )
    assert settings.json()["job_search_paused"] is True


def test_candidates_bank_filters(client: TestClient) -> None:
    body = client.get(
        "/api/candidates",
        params={"specialization": "backend", "has_fsp": "false"},
        headers=RECRUITER,
    ).json()
    assert all(c["specialization"] == "backend" and not c["has_fsp"] for c in body["items"])


def test_companies(client: TestClient) -> None:
    company = client.get("/api/companies/my", headers=RECRUITER).json()
    assert company["name"] == "Северный код"
    assert len(client.get("/api/companies/my/recruiters", headers=RECRUITER).json()) == 3
    dashboard = client.get("/api/companies/my/dashboard", headers=RECRUITER).json()
    assert dashboard["quota"]["limit"] == 20


def test_testing_flow(client: TestClient) -> None:
    survey = client.get("/api/testing/survey", headers=CANDIDATE).json()
    assert len(survey) == len(fixtures.load("survey_questions"))
    result = client.post(
        "/api/testing/survey",
        json={"answers": [{"question_id": "q1", "option_ids": ["q1_data"]}]},
        headers=CANDIDATE,
    ).json()
    assert result["recommended_specialization"] == "data_ml"
    # у кандидата 1 активен кулдаун смены грейда
    blocked = client.post(
        "/api/testing/sessions",
        json={"specialization": "backend", "target_grade": "senior", "kind": "higher"},
        headers=CANDIDATE,
    )
    assert blocked.status_code == 409 and blocked.json()["code"] == "cooldown_active"
    grade = client.get("/api/testing/grade", headers=CANDIDATE).json()
    assert grade["can_test_higher"] is False and grade["higher_available_at"]
    finished = next(s for s in client.get("/api/testing/sessions", headers=CANDIDATE).json())
    res = client.get(f"/api/testing/sessions/{finished['id']}/result", headers=CANDIDATE).json()
    assert res["category"] == "backend:middle"
    assert "correct_answer" not in str(res)


def test_testing_in_progress_session(client: TestClient) -> None:
    headers = {"X-Demo-Role": "candidate", "X-Demo-User-Id": "39"}
    session = next(s for s in fixtures.load("test_sessions") if s["status"] == "in_progress")
    state = client.get(f"/api/testing/sessions/{session['id']}", headers=headers).json()
    assert state["current_item"]["prompt"]
    assert "correct_answer" not in state["current_item"]
    ack = client.post(
        f"/api/testing/sessions/{session['id']}/answers",
        json={"instance_id": state["current_item"]["instance_id"], "answer": {"choice_ids": ["a"]}},
        headers=headers,
    ).json()
    assert ack["answered"] == session["items_answered"] + 1
    # чужая сессия не видна
    other = client.get(f"/api/testing/sessions/{session['id']}", headers=CANDIDATE)
    assert other.status_code == 404


def test_fsp_with_and_without_history(client: TestClient) -> None:
    status = client.get("/api/fsp/status", headers=CANDIDATE).json()
    assert status["linked"] and status["has_history"]
    assert client.get("/api/fsp/achievements", headers=CANDIDATE).json()
    empty = client.get("/api/fsp/status", headers=CANDIDATE_NO_FSP).json()
    assert empty == {
        "linked": False,
        "fsp_id": None,
        "linked_at": None,
        "last_sync_at": None,
        "achievements_count": 0,
        "fsp_score": None,
        "badges": [],
        "has_history": False,
        "message": "Нет данных ФСП. Привяжите ФСП ID, если участвовали в соревнованиях.",
    }
    assert client.get("/api/fsp/achievements", headers=CANDIDATE_NO_FSP).json() == []


def test_matching(client: TestClient) -> None:
    needs = client.get("/api/matching/needs", headers=RECRUITER).json()
    assert {n["company_id"] for n in needs} == {1}
    need_id = needs[-1]["id"]
    categories = client.get(f"/api/matching/needs/{need_id}/categories", headers=RECRUITER).json()
    assert categories[0]["relation"] == "primary"
    matches = client.get(f"/api/matching/needs/{need_id}/candidates", headers=RECRUITER).json()
    assert matches["items"], "подборка не должна быть пустой"
    first = matches["items"][0]
    assert 2 <= len(first["reasons"]) <= 4 or first["reasons"]
    assert abs(sum(b["contribution"] for b in first["breakdown"]) - first["score"]) < 0.01
    scores = [m["score"] for m in matches["items"]]
    assert scores == sorted(scores, reverse=True)
    parsed = client.post(
        "/api/matching/needs/parse",
        json={"text": "нужен сеньор на Go в финтех, удалёнка, 300–400к"},
        headers=RECRUITER,
    ).json()["draft"]
    assert parsed["grade"] == "senior" and parsed["specialization"] == "backend"
    assert parsed["work_format"] == "remote" and parsed["salary_to"] == 400000
    assert "go" in parsed["skills_required"]
    # чужая потребность
    other = next(n for n in fixtures.load("needs") if n["company_id"] != 1)
    assert client.get(f"/api/matching/needs/{other['id']}", headers=RECRUITER).status_code == 404


def test_invitations_state_machine(client: TestClient) -> None:
    mine = client.get("/api/invitations", headers=CANDIDATE).json()
    assert {i["candidate_id"] for i in mine} == {1}
    sent = next(i for i in mine if i["status"] == "sent")
    opened = client.get(f"/api/invitations/{sent['id']}", headers=CANDIDATE).json()
    assert opened["status"] == "viewed" and opened["events"]
    accepted = client.post(f"/api/invitations/{sent['id']}/accept", headers=CANDIDATE).json()
    assert accepted["status"] == "accepted" and accepted["recruiter_contacts"]
    declined = next(i for i in mine if i["status"] == "declined")
    again = client.post(f"/api/invitations/{declined['id']}/accept", headers=CANDIDATE)
    assert again.status_code == 409 and again.json()["code"] == "invalid_transition"
    reason = client.post(
        f"/api/invitations/{sent['id']}/decline",
        json={"reason": "salary_too_low"},
        headers=CANDIDATE,
    ).json()
    assert reason["decline_reason_label"] == "Мала зарплата"
    # чужое приглашение — 404
    foreign = next(i for i in fixtures.load("invitations") if i["candidate_id"] != 1)
    assert client.get(f"/api/invitations/{foreign['id']}", headers=CANDIDATE).status_code == 404
    quota = client.get("/api/invitations/quota", headers=RECRUITER).json()
    assert quota["used"] + quota["left"] == quota["limit"]
    hint = client.get(
        "/api/invitations/market-hint",
        params={"category": "backend:middle", "salary_to": 250000},
        headers=RECRUITER,
    ).json()
    assert hint["message"]


def test_vacancies_and_applications(client: TestClient) -> None:
    feed = client.get("/api/vacancies", headers=CANDIDATE).json()
    assert feed and all(v["status"] == "published" for v in feed)
    assert any(v["my_application_id"] for v in feed)
    own = client.get("/api/vacancies", headers=RECRUITER).json()
    assert {v["company_id"] for v in own} == {1}
    applied = next(v for v in feed if v["my_application_id"])
    dup = client.post(f"/api/vacancies/{applied['id']}/applications", json={}, headers=CANDIDATE)
    assert dup.status_code == 409
    apps = client.get(f"/api/vacancies/{own[0]['id']}/applications", headers=RECRUITER).json()
    assert all(a["candidate_contacts"] for a in apps)
    my_apps = client.get("/api/applications", headers=CANDIDATE).json()
    assert my_apps and all(a["candidate_contacts"] is None for a in my_apps)


def test_tasks(client: TestClient) -> None:
    inbox = client.get("/api/tasks/inbox", headers=CANDIDATE).json()
    assert inbox["active"] is not None
    answer = client.post(
        f"/api/tasks/submissions/{inbox['active']['id']}/answer",
        json={"answer_kind": "text", "answer_text": "Мой подход"},
        headers=CANDIDATE,
    )
    assert answer.json()["status"] == "submitted"
    tasks = client.get("/api/tasks", headers=RECRUITER).json()
    assert tasks and all(t["company_id"] == 1 for t in tasks)
    subs = client.get(f"/api/tasks/{tasks[-1]['id']}/submissions", headers=RECRUITER).json()
    assert all("full_name" not in (s["candidate"] or {}) for s in subs)


def test_admin(client: TestClient) -> None:
    dashboard = client.get("/api/admin/dashboard", headers=ADMIN).json()
    assert dashboard["users_by_role"]["candidate"] == 40
    assert dashboard["leak_flags"]
    users = client.get("/api/admin/users", params={"role": "recruiter"}, headers=ADMIN).json()
    assert users["total"] == 7
    items = client.get("/api/admin/items", params={"leak_flag": "true"}, headers=ADMIN).json()
    assert items["items"] and "preview_variants" not in items["items"][0]
    detail = client.get(f"/api/admin/items/{items['items'][0]['id']}", headers=ADMIN).json()
    assert len(detail["preview_variants"]) == 3
    draft = next(i for i in fixtures.load("items") if i["status"] == "draft")
    approved = client.post(f"/api/admin/items/{draft['id']}/approve", headers=ADMIN).json()
    assert approved["status"] == "pilot"
    assert client.get("/api/admin/companies", headers=ADMIN).json()
    assert client.get("/api/admin/settings", headers=ADMIN).json()["invitation_quota"] == 20
    assert client.get("/api/admin/reports", headers=ADMIN).json()
    assert client.get("/api/admin/audit", headers=ADMIN).json()["total"] > 0
    test = client.post(
        "/api/admin/vacancy-tests",
        json={"text": "Ищем Middle Python-разработчика: FastAPI, PostgreSQL, Redis, транзакции."},
        headers=ADMIN,
    ).json()
    assert test["topics"] and test["explanation"]
    report = client.post(
        "/api/reports",
        json={"company_id": 3, "reason": "spam", "text": "Спамят приглашениями"},
        headers=CANDIDATE,
    )
    assert report.status_code == 201


def test_eval(client: TestClient) -> None:
    overview = client.get("/api/eval/validation").json()
    assert len(overview["charts"]) == len(fixtures.load("validation_charts"))
    csv_body = "need_id,candidate_id,relevant\n1,2,1\n1,3,0\n2,5,1\n"
    result = client.post(
        "/api/eval/matching", files={"file": ("pairs.csv", csv_body.encode(), "text/csv")}
    ).json()
    assert result["pairs_count"] == 3 and result["needs_count"] == 2
    bad = client.post("/api/eval/matching", files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")})
    assert bad.status_code == 422

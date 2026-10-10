"""Профиль кандидата на БД: сохранение, валидация, приватность, согласие на публикацию, грейд."""

from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.catalog.clock import now_msk
from app.common import fixtures
from app.seed.testkit import reseed_sync, sql_sync
from tests.conftest import CANDIDATE, CANDIDATE_NO_FSP, RECRUITER, RECRUITER_C2, as_role

CANDIDATE_3 = as_role("candidate", 3)
CANDIDATE_14 = as_role("candidate", 14)
CANDIDATE_16 = as_role("candidate", 16)

PROFILE: dict[str, Any] = {
    "full_name": "Алексей Смирнов-Тестов",
    "phone": "+7 900 000-00-99",
    "telegram": "@test_alexey",
    "city": "Казань",
    "work_formats": ["remote", "office"],
    "stack": ["go", "python", "postgresql", "docker"],
    "roles_in_team": ["Разработчик"],
    "experience_years": 4.5,
    "soft_skills": ["Коммуникация"],
    "about": "Обновлённый профиль",
    "links": [{"type": "github", "url": "https://github.com/example-test"}],
    "min_salary": 250000,
}

GRADE_STATUS_KEYS = (
    "grade_status",
    "grade_confirmed_at",
    "declared_specialization",
    "declared_grade",
    "declared_at",
)


def without_grade_status(profile: dict[str, Any]) -> dict[str, Any]:
    """Профиль без полей статуса грейда (FTT.4): их нет в фикстурах, проверяются отдельно."""
    assert profile["grade_status"] == ("confirmed" if profile["grade"] else "none")
    return {k: v for k, v in profile.items() if k not in GRADE_STATUS_KEYS}


@pytest.fixture(autouse=True, scope="module")
def _fresh_db_module() -> Iterator[None]:
    reseed_sync()
    yield
    reseed_sync()


@pytest.fixture
def fresh_db() -> None:
    reseed_sync()


def _bank_ids(client: TestClient, headers: dict[str, str] = RECRUITER) -> set[int]:
    """id всех кандидатов банка (с листанием: в демо-базе больше 100 кандидатов)."""
    ids: set[int] = set()
    page = 1
    while True:
        query = {"page_size": 100, "page": page}
        body = client.get("/api/candidates", params=query, headers=headers).json()
        ids |= {c["id"] for c in body["items"]}
        if page * 100 >= body["total"]:
            return ids
        page += 1


def test_profile_read_from_db_equals_fixture(client: TestClient) -> None:
    for headers, cid in ((CANDIDATE, 1), (CANDIDATE_NO_FSP, 26)):
        profile = client.get("/api/candidates/me/profile", headers=headers).json()
        assert without_grade_status(profile) == fixtures.by_id("candidates", cid)


def test_save_profile_persists(client: TestClient, fresh_db: None) -> None:
    saved = client.put("/api/candidates/me/profile", json=PROFILE, headers=CANDIDATE)
    assert saved.status_code == 200, saved.text
    profile = client.get("/api/candidates/me/profile", headers=CANDIDATE).json()
    assert profile["full_name"] == PROFILE["full_name"]
    assert profile["stack"] == PROFILE["stack"]  # порядок сохранён
    assert profile["work_formats"] == ["remote", "office"]
    assert profile["min_salary"] == 250000 and profile["experience_years"] == 4.5
    assert profile["links"] == PROFILE["links"]
    # данные для категории не меняются вручную
    assert profile["category"] == "backend:middle"
    # рекрутер видит новый стек, но не зарплату
    card = client.get("/api/candidates/1", headers=RECRUITER).json()
    assert card["stack"] == PROFILE["stack"] and "min_salary" not in card
    assert str(250000) not in str(client.get("/api/candidates", headers=RECRUITER).json())


def test_profile_validation(client: TestClient, fresh_db: None) -> None:
    bad_skill = client.put(
        "/api/candidates/me/profile",
        json={**PROFILE, "stack": ["python", "cobol"]},
        headers=CANDIDATE,
    )
    assert bad_skill.status_code == 422
    assert bad_skill.json()["code"] == "unknown_skills"
    assert bad_skill.json()["details"]["skills"] == ["cobol"]
    patches: list[dict[str, Any]] = [
        {"work_formats": []},
        {"min_salary": -1},
        {"experience_years": 99},
        {"full_name": "A"},
        {"links": [{"type": "github"}]},
    ]
    for patch in patches:
        response = client.put(
            "/api/candidates/me/profile", json={**PROFILE, **patch}, headers=CANDIDATE
        )
        assert response.status_code == 422, patch
    # ничего не сохранилось
    profile = client.get("/api/candidates/me/profile", headers=CANDIDATE).json()
    assert without_grade_status(profile) == fixtures.by_id("candidates", 1)


def test_privacy_changes_anonymous_profile(client: TestClient, fresh_db: None) -> None:
    before = client.get("/api/candidates/14", headers=RECRUITER).json()
    assert before["city"] == "Томск" and before["experience_years"] is not None
    assert before["links"] is None
    hidden = {
        "show_city": False,
        "show_experience": False,
        "show_links": True,
        "show_fsp_achievements": False,
    }
    settings = client.put("/api/candidates/me/settings/privacy", json=hidden, headers=CANDIDATE_14)
    assert settings.status_code == 200 and settings.json()["privacy"] == hidden
    after = client.get("/api/candidates/14", headers=RECRUITER).json()
    assert after["city"] is None and after["experience_years"] is None
    assert after["links"] is not None
    assert after["fsp_score"] is None and after["fsp_badges"] == []
    category = fixtures.by_id("candidates", 14)["category"]  # type: ignore[index]
    card = next(
        c
        for c in client.get(
            "/api/candidates", params={"category": category, "page_size": 100}, headers=RECRUITER
        ).json()["items"]
        if c["id"] == 14
    )
    assert card["city"] is None
    # фильтр по городу не раскрывает скрытый город
    by_city = client.get("/api/candidates", params={"city": "Томск"}, headers=RECRUITER).json()
    assert 14 not in {c["id"] for c in by_city["items"]}


def test_publication_consent_revoke_and_grant(client: TestClient, fresh_db: None) -> None:
    assert 3 in _bank_ids(client)
    assert client.get("/api/candidates/3", headers=RECRUITER_C2).status_code == 200
    revoked = client.put(
        "/api/candidates/me/settings/publication", json={"granted": False}, headers=CANDIDATE_3
    )
    assert revoked.status_code == 200 and revoked.json()["publication_consent"] is False
    # отзыв действует сразу
    assert 3 not in _bank_ids(client)
    assert 3 not in _bank_ids(client, RECRUITER_C2)
    assert client.get("/api/candidates/3", headers=RECRUITER_C2).status_code == 404
    rows = sql_sync(
        "SELECT granted, revoked_at FROM consents WHERE user_id = 3 AND type = 'publication'"
    )
    assert rows and all(not granted and revoked_at for granted, revoked_at in rows)
    audit = sql_sync(
        "SELECT actor_user_id FROM audit_log WHERE action = 'consent_revoked' AND actor_user_id = 3"
    )
    assert audit
    dashboard = client.get("/api/candidates/me/dashboard", headers=CANDIDATE_3).json()
    assert any("согласие" in h for h in dashboard["hints"])

    granted = client.put(
        "/api/candidates/me/settings/publication", json={"granted": True}, headers=CANDIDATE_3
    )
    assert granted.json()["publication_consent"] is True
    assert 3 in _bank_ids(client)
    active = sql_sync(
        "SELECT version FROM consents WHERE user_id = 3 AND type = 'publication' "
        "AND granted AND revoked_at IS NULL"
    )
    assert [r[0] for r in active] == [fixtures.load("platform_settings")[0]["consent_version"]]


def test_job_search_pause_hides_from_bank(client: TestClient, fresh_db: None) -> None:
    assert 3 in _bank_ids(client)
    client.put("/api/candidates/me/settings/job-search", json={"paused": True}, headers=CANDIDATE_3)
    assert 3 not in _bank_ids(client)
    settings = client.get("/api/candidates/me/settings", headers=CANDIDATE_3).json()
    assert settings["job_search_paused"] is True
    client.put(
        "/api/candidates/me/settings/job-search", json={"paused": False}, headers=CANDIDATE_3
    )
    assert 3 in _bank_ids(client)


def test_bank_filters_and_sort(client: TestClient) -> None:
    body = client.get(
        "/api/candidates",
        params={"specialization": "backend", "skills": ["python"], "sort": "theta"},
        headers=RECRUITER,
    ).json()
    assert body["items"]
    thetas = [c["theta"] for c in body["items"]]
    assert thetas == sorted(thetas, reverse=True)
    for card in body["items"]:
        assert card["specialization"] == "backend" and "python" in card["stack"]
    expected = sum(
        1
        for c in fixtures.load("candidates")
        if c["grade"] and c["publication_consent"] and not c["job_search_paused"]
    )
    blocked_users = {u["id"] for u in fixtures.load("users") if u["blocked"]}
    expected -= sum(
        1
        for c in fixtures.load("candidates")
        if c["user_id"] in blocked_users
        and c["grade"]
        and c["publication_consent"]
        and not c["job_search_paused"]
    )
    assert client.get("/api/candidates", headers=RECRUITER).json()["total"] == expected
    page2 = client.get("/api/candidates", params={"page": 2, "page_size": 5}, headers=RECRUITER)
    assert len(page2.json()["items"]) == 5 and page2.json()["page"] == 2


def test_bank_has_fsp_means_shown_achievements(client: TestClient) -> None:
    """«Есть достижения ФСП» [ТЗ: подтверждённые достижения]: true — есть достижения и они не
    скрыты; привязка без истории (FSP-000031…35) и скрытые достижения — false, причём карточка
    не выдаёт скрытое участие."""

    def bank(has_fsp: str) -> dict[int, dict[str, Any]]:
        body = client.get(
            "/api/candidates",
            params={"has_fsp": has_fsp, "page_size": 100},
            headers=RECRUITER,
        ).json()
        assert body["total"] == len(body["items"])
        return {c["id"]: c for c in body["items"]}

    yes, no = bank("true"), bank("false")
    assert yes and no and not set(yes) & set(no)
    shown = {
        c["id"]
        for c in fixtures.load("candidates")
        if c["fsp_id"]
        and c["fsp_score"] is not None
        and c["privacy"].get("show_fsp_achievements", True)
    }
    assert set(yes) <= shown
    for card in yes.values():
        assert card["has_fsp"] is True and card["fsp_badges"] and card["fsp_score"] is not None
    # 6 — скрыл достижения, 22 — ФСП ID без истории: оба «нет», бейджа участия нет
    for cid in (6, 22):
        assert cid in no
        assert no[cid]["has_fsp"] is False
        assert no[cid]["fsp_badges"] == [] and no[cid]["fsp_score"] is None
    assert all(c["has_fsp"] is False for c in no.values())
    profile = client.get("/api/candidates/6", headers=RECRUITER).json()
    assert profile["has_fsp"] is False and profile["fsp_badges"] == []


def test_dashboard_from_db(client: TestClient) -> None:
    dashboard = client.get("/api/candidates/me/dashboard", headers=CANDIDATE).json()
    unread = [
        i for i in fixtures.load("invitations") if i["candidate_id"] == 1 and i["status"] == "sent"
    ]
    assert dashboard["new_invitations_count"] == len(unread)
    assert (
        dashboard["profile_completeness"]
        == fixtures.by_id("candidates", 1)[  # type: ignore[index]
            "profile_completeness"
        ]
    )


def test_grade_status_first_assignment_is_not_a_change(client: TestClient) -> None:
    grade = client.get("/api/candidates/me/grade", headers=CANDIDATE).json()
    assert grade["grade"] == "middle" and grade["category"] == "backend:middle"
    # первое присвоение грейда сменой не считается — можно сразу пробовать выше и ниже
    assert grade["can_test_higher"] and grade["higher"]["target_grade"] == "senior"
    assert grade["can_test_lower"] and grade["lower"]["target_grade"] == "junior"
    assert grade["higher_available_at"] is None
    assert [h["id"] for h in grade["history"]] == [
        h["id"] for h in fixtures.load("grade_history") if h["candidate_id"] == 1
    ]
    assert grade["tests"] and grade["tests"][0]["result_category"] == "backend:middle"
    # у стажёра нет теста «ниже»
    intern = client.get("/api/candidates/me/grade", headers=CANDIDATE_16).json()
    assert intern["grade"] == "intern" and intern["lower"] is None
    assert intern["can_test_lower"] is False


def test_grade_change_cooldown_90_days(client: TestClient, fresh_db: None) -> None:
    changed = now_msk() - timedelta(days=10)
    sql_sync(
        "INSERT INTO grade_history (candidate_id, at, event, specialization, grade_from, grade_to,"
        " comment) VALUES (1, :at, 'grade_changed', 'backend', 'junior', 'middle', 'тест')",
        {"at": changed},
    )
    grade = client.get("/api/candidates/me/grade", headers=CANDIDATE).json()
    until = (changed + timedelta(days=90)).date().isoformat()
    assert grade["can_test_higher"] is False and grade["can_test_lower"] is False
    assert grade["higher"]["code"] == "grade_change_cooldown"
    assert grade["higher_available_at"].startswith(until)
    assert grade["lower_available_at"].startswith(until)
    # интервал берётся из настроек платформы
    sql_sync(
        "UPDATE platform_settings SET value = '5'::jsonb WHERE key = 'grade_change_cooldown_days'"
    )
    grade = client.get("/api/candidates/me/grade", headers=CANDIDATE).json()
    assert grade["can_test_higher"] is True and grade["grade_change_cooldown_days"] == 5


def test_failed_attempt_retry_cooldown_30_days(client: TestClient, fresh_db: None) -> None:
    failed = now_msk() - timedelta(days=3)
    sql_sync(
        "INSERT INTO test_sessions (candidate_id, specialization, target_grade, kind, status,"
        " started_at, finished_at, items_answered, max_items, passed, topic_scores, engine_state)"
        " VALUES (1, 'backend', 'senior', 'higher', 'finished', :at, :at, 15, 15, false,"
        " '[]'::jsonb, '{}'::jsonb)",
        {"at": failed},
    )
    grade = client.get("/api/candidates/me/grade", headers=CANDIDATE).json()
    assert grade["higher"]["allowed"] is False
    assert grade["higher"]["code"] == "failed_retry_cooldown"
    assert grade["higher_available_at"].startswith((failed + timedelta(days=30)).date().isoformat())
    assert grade["can_test_lower"] is True  # ниже — другой грейд, повтора нет


# ---------- банк кандидатов под потребность [ТЗ: ранжирование по соответствию] ----------


def _bank(client: TestClient, **params: Any) -> dict[str, Any]:
    r = client.get("/api/candidates", params={"page_size": 100, **params}, headers=RECRUITER)
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def test_bank_ranked_by_need(client: TestClient) -> None:
    plain = _bank(client)
    assert all(c["match_score"] is None and c["match_reasons"] == [] for c in plain["items"])
    ranked = _bank(client, need_id=1)  # потребность 1 компании 1: Backend · Middle
    assert ranked["total"] == plain["total"]  # потребность ранжирует, а не фильтрует
    scores = [c["match_score"] for c in ranked["items"]]
    assert scores == sorted(scores, reverse=True)  # по умолчанию — по соответствию
    for card in ranked["items"]:
        assert 0 <= card["match_score"] <= 1
        assert 1 <= len(card["match_reasons"]) <= 3
    # счёт и причины — те же, что в подборке по этой потребности
    matches = client.get("/api/matching/needs/1/candidates", headers=RECRUITER).json()["items"]
    by_id = {c["id"]: c for c in ranked["items"]}
    assert matches
    for m in matches:
        card = by_id[m["candidate"]["id"]]
        assert card["match_score"] == m["score"]
        assert card["match_reasons"] == m["reasons"][:3]
    # страницы по соответствию не пересекаются и идут подряд
    p1 = _bank(client, need_id=1, page_size=5)
    p2 = _bank(client, need_id=1, page_size=5, page=2)
    assert [c["id"] for c in p1["items"] + p2["items"]] == [c["id"] for c in ranked["items"]][:10]


def test_bank_need_with_filters_and_other_sort(client: TestClient) -> None:
    both = _bank(client, need_id=1, specialization="backend", has_fsp="true")
    plain = _bank(client, specialization="backend", has_fsp="true")
    assert {c["id"] for c in both["items"]} == {c["id"] for c in plain["items"]}
    assert all(c["specialization"] == "backend" and c["has_fsp"] for c in both["items"])
    scores = [c["match_score"] for c in both["items"]]
    assert scores == sorted(scores, reverse=True)
    by_theta = _bank(client, need_id=1, sort="theta")
    thetas = [c["theta"] for c in by_theta["items"]]
    assert thetas == sorted(thetas, reverse=True)
    assert all(c["match_score"] is not None for c in by_theta["items"])


def test_bank_need_access_and_validation(client: TestClient) -> None:
    foreign = client.get("/api/candidates", params={"need_id": 3}, headers=RECRUITER)
    assert foreign.status_code == 404  # потребность компании 2
    missing = client.get("/api/candidates", params={"need_id": 9999}, headers=RECRUITER)
    assert missing.status_code == 404
    own = client.get("/api/candidates", params={"need_id": 3}, headers=RECRUITER_C2)
    assert own.status_code == 200 and own.json()["items"][0]["match_score"] is not None
    no_need = client.get("/api/candidates", params={"sort": "match"}, headers=RECRUITER)
    assert no_need.status_code == 422

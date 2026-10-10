"""Вакансии на БД [ТЗ 2.1, 2.2; T8.1, T8.2]: CRUD своей компании, вилка, стек из справочника,
черновик → публикация → снятие (недопустимый переход → 409), лента с фильтрами и пагинацией,
изоляция компаний, счётчики откликов из БД.

Каждый тест начинает с чистого сида — тесты не зависят друг от друга.
"""

from collections import Counter
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.common import fixtures
from app.common.enums import VacancyStatus
from app.seed.testkit import reseed_sync, sql_sync
from app.vacancies.service import VACANCY_TRANSITIONS, can_publish_transition
from tests.conftest import ADMIN, CANDIDATE, RECRUITER, RECRUITER_C2


@pytest.fixture(scope="module", autouse=True)
def _restore_seed_after_module() -> Iterator[None]:
    yield
    reseed_sync()


@pytest.fixture(autouse=True)
def _fresh_db() -> None:
    reseed_sync()


def vacancy_body(**extra: Any) -> dict[str, Any]:
    return {
        "title": "Senior Go-разработчик",
        "description": "Пишем биллинг на Go: высокая нагрузка, PostgreSQL, Kafka.",
        "team_description": "Команда биллинга, 5 человек",
        "specialization": "backend",
        "grade": "senior",
        "skills_required": ["go", "postgresql"],
        "skills_desired": ["kafka"],
        "work_format": "remote",
        "city": "Казань",
        "salary_from": 300000,
        "salary_to": 400000,
        **extra,
    }


def create(client: TestClient, headers: dict[str, str] = RECRUITER, **extra: Any) -> Any:
    response = client.post("/api/vacancies", json=vacancy_body(**extra), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def feed_ids(client: TestClient, **params: Any) -> list[int]:
    response = client.get("/api/vacancies", params=params, headers=CANDIDATE)
    assert response.status_code == 200, response.text
    return [v["id"] for v in response.json()]


# ---------- машина состояний (без БД) ----------


def test_transition_table() -> None:
    s = VacancyStatus
    assert can_publish_transition(s.draft, s.published)
    assert can_publish_transition(s.published, s.unpublished)
    assert can_publish_transition(s.unpublished, s.published)
    assert not can_publish_transition(s.draft, s.unpublished)
    assert not can_publish_transition(s.published, s.published)
    assert set(VACANCY_TRANSITIONS) == set(s)


# ---------- CRUD и публикация ----------


def test_draft_publish_unpublish_flow(client: TestClient) -> None:
    created = create(client)
    assert created["status"] == "draft" and created["published_at"] is None
    assert created["company_id"] == 1 and created["company_name"] == "Северный код"
    assert created["category"] == "backend:senior"
    assert created["category_label"] == "Backend · Senior"
    assert created["team_description"] == "Команда биллинга, 5 человек"
    assert created["applications_count"] == 0
    vid = created["id"]

    # черновик кандидату не виден
    assert vid not in feed_ids(client)
    assert client.get(f"/api/vacancies/{vid}", headers=CANDIDATE).status_code == 404
    # рекрутер видит в своём списке и карточке
    own = client.get("/api/vacancies", headers=RECRUITER).json()
    assert own[0]["id"] == vid, "свои вакансии — новые сверху"
    assert client.get(f"/api/vacancies/{vid}", headers=RECRUITER).json()["status"] == "draft"

    # снять черновик нельзя
    bad = client.post(f"/api/vacancies/{vid}/unpublish", headers=RECRUITER)
    assert bad.status_code == 409 and bad.json()["code"] == "invalid_transition"

    published = client.post(f"/api/vacancies/{vid}/publish", headers=RECRUITER).json()
    assert published["status"] == "published" and published["published_at"]
    assert feed_ids(client)[0] == vid, "лента — свежеопубликованные сверху"
    card = client.get(f"/api/vacancies/{vid}", headers=CANDIDATE).json()
    assert card["my_application_id"] is None and card["company_name"] == "Северный код"

    again = client.post(f"/api/vacancies/{vid}/publish", headers=RECRUITER)
    assert again.status_code == 409
    assert again.json()["details"] == {"from": "published", "to": "published"}

    unpublished = client.post(f"/api/vacancies/{vid}/unpublish", headers=RECRUITER).json()
    assert unpublished["status"] == "unpublished"
    assert vid not in feed_ids(client)
    assert client.get(f"/api/vacancies/{vid}", headers=CANDIDATE).status_code == 404
    assert client.post(f"/api/vacancies/{vid}/unpublish", headers=RECRUITER).status_code == 409

    # снятую можно опубликовать снова
    assert client.post(f"/api/vacancies/{vid}/publish", headers=RECRUITER).status_code == 200
    assert vid in feed_ids(client)


def test_vacancy_is_stored_in_db(client: TestClient) -> None:
    created = create(client)
    rows = sql_sync(
        "SELECT company_id, status, salary_from, salary_to, team_description, skills_required "
        "FROM vacancies WHERE id = :id",
        {"id": created["id"]},
    )
    assert [tuple(r) for r in rows] == [
        (1, "draft", 300000, 400000, "Команда биллинга, 5 человек", ["go", "postgresql"])
    ]


def test_update_own_vacancy(client: TestClient) -> None:
    vid = create(client)["id"]
    body = vacancy_body(
        title="Middle Go-разработчик",
        grade="middle",
        salary_from=200000,
        salary_to=260000,
        city="  ",
        team_description="",
    )
    updated = client.put(f"/api/vacancies/{vid}", json=body, headers=RECRUITER)
    assert updated.status_code == 200, updated.text
    data = updated.json()
    assert data["title"] == "Middle Go-разработчик"
    assert data["category"] == "backend:middle" and data["category_label"] == "Backend · Middle"
    assert data["salary_from"] == 200000 and data["salary_to"] == 260000
    assert data["city"] is None and data["team_description"] == ""
    assert data["status"] == "draft", "правка не меняет статус"


def test_salary_range_is_required_and_ordered(client: TestClient) -> None:
    for field in ("salary_from", "salary_to"):
        body = vacancy_body()
        body.pop(field)
        assert client.post("/api/vacancies", json=body, headers=RECRUITER).status_code == 422
    bad = client.post("/api/vacancies", json=vacancy_body(salary_from=500000), headers=RECRUITER)
    assert bad.status_code == 422
    assert bad.json()["details"]["errors"][0]["type"] == "salary_range_invalid"
    zero = client.post("/api/vacancies", json=vacancy_body(salary_from=0), headers=RECRUITER)
    assert zero.status_code == 422
    equal = create(client, salary_from=350000, salary_to=350000)
    assert equal["salary_from"] == equal["salary_to"] == 350000
    # правка тоже проверяет вилку
    put = client.put(
        f"/api/vacancies/{equal['id']}",
        json=vacancy_body(salary_from=400000, salary_to=100000),
        headers=RECRUITER,
    )
    assert put.status_code == 422


def test_stack_from_catalog_only(client: TestClient) -> None:
    bad = client.post(
        "/api/vacancies",
        json=vacancy_body(skills_required=["go", "cobol_9000"]),
        headers=RECRUITER,
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "unknown_skills"
    assert bad.json()["details"] == {"skills": ["cobol_9000"]}
    # коды нормализуются, желательные без повторов обязательных
    created = create(
        client, skills_required=[" Go ", "go", "postgresql"], skills_desired=["kafka", "go"]
    )
    assert created["skills_required"] == ["go", "postgresql"]
    assert created["skills_desired"] == ["kafka"]


def test_required_fields(client: TestClient) -> None:
    for field in ("title", "description", "specialization", "grade", "work_format"):
        body = vacancy_body()
        body.pop(field)
        response = client.post("/api/vacancies", json=body, headers=RECRUITER)
        assert response.status_code == 422, field
    unknown = client.post("/api/vacancies", json=vacancy_body(extra=1), headers=RECRUITER)
    assert unknown.status_code == 422


# ---------- изоляция и роли ----------


def test_foreign_company_vacancy_is_404(client: TestClient) -> None:
    vid = create(client)["id"]
    for method, path, payload in (
        ("get", f"/api/vacancies/{vid}", None),
        ("put", f"/api/vacancies/{vid}", vacancy_body()),
        ("post", f"/api/vacancies/{vid}/publish", None),
        ("post", f"/api/vacancies/{vid}/unpublish", None),
        ("get", f"/api/vacancies/{vid}/applications", None),
        ("get", "/api/vacancies/1", None),  # опубликованная, но чужая
    ):
        response = client.request(method, path, json=payload, headers=RECRUITER_C2)
        assert response.status_code == 404, (method, path)
        assert response.json()["code"] == "not_found"
    own = client.get("/api/vacancies", headers=RECRUITER_C2).json()
    assert own and {v["company_id"] for v in own} == {2}
    assert {v["status"] for v in own} == {"published", "unpublished"}
    assert client.get("/api/vacancies/999999", headers=RECRUITER).status_code == 404


def test_roles(client: TestClient) -> None:
    assert client.get("/api/vacancies", headers=ADMIN).status_code == 403
    assert client.post("/api/vacancies", json=vacancy_body(), headers=CANDIDATE).status_code == 403
    assert client.post("/api/vacancies/1/unpublish", headers=CANDIDATE).status_code == 403
    assert client.get("/api/vacancies").status_code == 401


# ---------- лента кандидата ----------


def test_feed_only_published(client: TestClient) -> None:
    feed = client.get("/api/vacancies", headers=CANDIDATE).json()
    assert {v["status"] for v in feed} == {"published"}
    assert sorted(v["id"] for v in feed) == [1, 2, 3, 4, 5, 7]  # 6 снята, 8 черновик
    mine = {v["id"]: v["my_application_id"] for v in feed}
    assert mine[1] == 2 and mine[4] == 1, "отклики демо-кандидата из сида"
    assert mine[2] is None


def test_feed_filters(client: TestClient) -> None:
    assert set(feed_ids(client, specialization="data_ml")) == {4, 5}
    assert set(feed_ids(client, grade="middle")) == {1, 4, 7}
    assert set(feed_ids(client, work_format="office")) == {5, 7}
    # все перечисленные навыки — в обязательном или желательном стеке
    assert set(feed_ids(client, skills=["python"])) == {1, 4}
    assert set(feed_ids(client, skills=["python", "kafka"])) == {1}
    assert set(feed_ids(client, skills="python,kafka")) == {1}
    assert feed_ids(client, skills=["python", "kotlin"]) == []
    # зарплата «до» не ниже
    assert set(feed_ids(client, salary_min=300000)) == {2, 4}
    # поиск по названию, описанию и компании
    assert set(feed_ids(client, q="тайга")) == {7}
    assert set(feed_ids(client, q="android")) == {2}
    assert set(feed_ids(client, specialization="data_ml", grade="intern")) == {5}
    bad = client.get("/api/vacancies", params={"grade": "guru"}, headers=CANDIDATE)
    assert bad.status_code == 422


def test_feed_pagination(client: TestClient) -> None:
    full = client.get("/api/vacancies", headers=CANDIDATE)
    assert full.headers["X-Total-Count"] == "6"
    all_ids = [v["id"] for v in full.json()]
    page1 = client.get("/api/vacancies", params={"limit": 4}, headers=CANDIDATE)
    page2 = client.get("/api/vacancies", params={"limit": 4, "offset": 4}, headers=CANDIDATE)
    assert page1.headers["X-Total-Count"] == page2.headers["X-Total-Count"] == "6"
    assert [v["id"] for v in page1.json()] + [v["id"] for v in page2.json()] == all_ids
    assert len(page2.json()) == 2
    filtered = client.get(
        "/api/vacancies", params={"grade": "middle", "limit": 1}, headers=CANDIDATE
    )
    assert filtered.headers["X-Total-Count"] == "3" and len(filtered.json()) == 1
    too_big = client.get("/api/vacancies", params={"limit": 1000}, headers=CANDIDATE)
    assert too_big.status_code == 422


def test_feed_hides_blocked_company(client: TestClient) -> None:
    sql_sync("UPDATE companies SET blocked = true WHERE id = 3")
    assert 7 not in feed_ids(client)
    assert client.get("/api/vacancies/7", headers=CANDIDATE).status_code == 404
    response = client.post("/api/vacancies/7/applications", json={}, headers=CANDIDATE)
    assert response.status_code == 404


def test_candidate_keeps_seeing_vacancy_he_applied_to(client: TestClient) -> None:
    client.post("/api/vacancies/1/unpublish", headers=RECRUITER)
    assert 1 not in feed_ids(client)
    card = client.get("/api/vacancies/1", headers=CANDIDATE)
    assert card.status_code == 200
    assert card.json()["status"] == "unpublished" and card.json()["my_application_id"] == 2


# ---------- счётчики откликов ----------


def test_applications_count_from_db(client: TestClient) -> None:
    own = {
        v["id"]: v["applications_count"]
        for v in client.get("/api/vacancies", headers=RECRUITER).json()
    }
    seed = Counter(a["vacancy_id"] for a in fixtures.load("applications"))
    assert own == {vid: seed[vid] for vid in (1, 2, 3)} == {1: 6, 2: 3, 3: 4}
    client.post("/api/vacancies/2/applications", json={}, headers=CANDIDATE)
    assert client.get("/api/vacancies/2", headers=RECRUITER).json()["applications_count"] == 4
    feed = {v["id"]: v for v in client.get("/api/vacancies", headers=CANDIDATE).json()}
    assert feed[2]["applications_count"] == 4 and feed[2]["my_application_id"]

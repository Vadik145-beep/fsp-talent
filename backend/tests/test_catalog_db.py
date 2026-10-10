"""Справочники на БД: публичные списки, админский CRUD, запреты, настройки платформы."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.common import fixtures
from app.seed.testkit import reseed_sync, sql_sync
from tests.conftest import ADMIN, CANDIDATE, RECRUITER


@pytest.fixture(autouse=True, scope="module")
def _fresh_db_module() -> Iterator[None]:
    reseed_sync()
    yield
    reseed_sync()


@pytest.fixture
def fresh_db() -> None:
    reseed_sync()


def _audit_actions() -> list[str]:
    seeded = len(fixtures.load("audit_log"))
    return [r[0] for r in sql_sync(f"SELECT action FROM audit_log WHERE id > {seeded} ORDER BY id")]


def test_public_lists_from_db(client: TestClient) -> None:
    specs = client.get("/api/catalog/specializations").json()
    assert [s["id"] for s in specs] == [s["id"] for s in fixtures.load("specializations")]
    assert len(client.get("/api/catalog/categories").json()) == 24
    backend = client.get("/api/catalog/categories", params={"specialization": "backend"}).json()
    assert [c["grade"] for c in backend] == ["intern", "junior", "middle", "senior"]
    assert len(client.get("/api/catalog/topics").json()) == len(fixtures.load("topics"))
    skills = client.get("/api/catalog/skills").json()
    assert {s["id"] for s in skills} == {s["id"] for s in fixtures.load("skills")}
    found = client.get("/api/catalog/skills", params={"q": "post"}).json()
    assert "postgresql" in {s["id"] for s in found}


def test_skill_crud_and_in_use(client: TestClient, fresh_db: None) -> None:
    body = {"id": "rust", "label": "Rust", "specializations": ["backend"]}
    created = client.post("/api/admin/catalog/skills", json=body, headers=ADMIN)
    assert created.status_code == 201 and created.json() == body
    assert "rust" in {
        s["id"]
        for s in client.get("/api/catalog/skills", params={"specialization": "backend"}).json()
    }
    dup = client.post("/api/admin/catalog/skills", json=body, headers=ADMIN)
    assert dup.status_code == 409 and dup.json()["code"] == "skill_exists"
    updated = client.put(
        "/api/admin/catalog/skills/rust",
        json={**body, "label": "Rust lang", "specializations": ["backend", "devops"]},
        headers=ADMIN,
    ).json()
    assert updated["label"] == "Rust lang" and updated["specializations"] == ["backend", "devops"]
    assert client.delete("/api/admin/catalog/skills/rust", headers=ADMIN).status_code == 204
    assert "rust" not in {s["id"] for s in client.get("/api/catalog/skills").json()}
    in_use = client.delete("/api/admin/catalog/skills/python", headers=ADMIN)
    assert in_use.status_code == 409 and in_use.json()["code"] == "skill_in_use"
    assert in_use.json()["details"]["usage"]["candidates"] > 0
    assert client.delete("/api/admin/catalog/skills/nope", headers=ADMIN).status_code == 404
    assert _audit_actions() == ["catalog_created", "catalog_updated", "catalog_deleted"]
    # кандидат и рекрутер в админку не ходят
    assert client.post("/api/admin/catalog/skills", json=body, headers=CANDIDATE).status_code == 403


def test_specialization_rules(client: TestClient, fresh_db: None) -> None:
    in_use = client.delete("/api/admin/catalog/specializations/backend", headers=ADMIN)
    assert in_use.status_code == 409 and in_use.json()["code"] == "specialization_in_use"
    assert in_use.json()["details"]["usage"]["candidates"] > 0
    exists = client.post(
        "/api/admin/catalog/specializations", json={"id": "qa", "label": "QA"}, headers=ADMIN
    )
    assert exists.status_code == 409
    unknown = client.post(
        "/api/admin/catalog/specializations", json={"id": "gamedev", "label": "G"}, headers=ADMIN
    )
    assert unknown.status_code == 422  # коды специализаций фиксированы
    patched = client.patch(
        "/api/admin/catalog/specializations/backend",
        json={"label": "Бэкенд", "active": False},
        headers=ADMIN,
    ).json()
    assert patched["label"] == "Бэкенд" and patched["active"] is False
    cats = client.get("/api/catalog/categories", params={"specialization": "backend"}).json()
    assert cats[2]["label"] == "Бэкенд · Middle"
    # подпись категории видна и в профиле кандидата
    profile = client.get("/api/candidates/me/profile", headers=CANDIDATE).json()
    assert profile["category_label"] == "Бэкенд · Middle"


def test_specialization_delete_and_restore(client: TestClient, fresh_db: None) -> None:
    # освобождаем специализацию mobile от данных, чтобы проверить успешное удаление
    for statement in (
        "DELETE FROM invitations WHERE category LIKE 'mobile:%'",
        "DELETE FROM regular_tasks WHERE category LIKE 'mobile:%'",
        "DELETE FROM candidate_profiles WHERE specialization = 'mobile'",
        "DELETE FROM vacancies WHERE specialization = 'mobile'",
        "DELETE FROM needs WHERE specialization = 'mobile'",
        "DELETE FROM items WHERE specialization = 'mobile'",
    ):
        sql_sync(statement)
    deleted = client.delete("/api/admin/catalog/specializations/mobile", headers=ADMIN)
    assert deleted.status_code == 204, deleted.text
    assert "mobile" not in {s["id"] for s in client.get("/api/catalog/specializations").json()}
    assert not client.get("/api/catalog/categories", params={"specialization": "mobile"}).json()
    restored = client.post(
        "/api/admin/catalog/specializations",
        json={"id": "mobile", "label": "Mobile", "description": "Мобильная разработка"},
        headers=ADMIN,
    )
    assert restored.status_code == 201
    cats = client.get("/api/catalog/categories", params={"specialization": "mobile"}).json()
    assert len(cats) == 4 and cats[0]["label"] == "Mobile · Стажёр"


def test_grade_category_topic_crud(client: TestClient, fresh_db: None) -> None:
    grade = client.patch(
        "/api/admin/catalog/grades/intern", json={"label": "Интерн"}, headers=ADMIN
    ).json()
    assert grade == {"id": "intern", "label": "Интерн", "order": 0}
    cat = client.get("/api/catalog/categories", params={"specialization": "qa"}).json()[0]
    assert cat["label"] == "QA · Интерн"
    renamed = client.patch(
        "/api/admin/catalog/categories/qa:intern", json={"label": "QA-стажёр"}, headers=ADMIN
    ).json()
    assert renamed["label"] == "QA-стажёр"
    missing = client.patch(
        "/api/admin/catalog/categories/qa:guru", json={"label": "x"}, headers=ADMIN
    )
    assert missing.status_code == 404

    topic = {"id": "backend.caching", "specialization": "backend", "label": "Кэширование"}
    assert client.post("/api/admin/catalog/topics", json=topic, headers=ADMIN).status_code == 201
    assert client.post("/api/admin/catalog/topics", json=topic, headers=ADMIN).status_code == 409
    wrong = client.post(
        "/api/admin/catalog/topics", json={**topic, "id": "qa.caching"}, headers=ADMIN
    )
    assert wrong.status_code == 422 and wrong.json()["code"] == "topic_code_invalid"
    patched = client.patch(
        "/api/admin/catalog/topics/backend.caching", json={"label": "Кэш"}, headers=ADMIN
    ).json()
    assert patched["label"] == "Кэш"
    used = client.delete("/api/admin/catalog/topics/backend.http_api", headers=ADMIN)
    assert used.status_code == 409 and used.json()["code"] == "topic_in_use"
    assert (
        client.delete("/api/admin/catalog/topics/backend.caching", headers=ADMIN).status_code == 204
    )
    assert "backend.caching" not in {t["id"] for t in client.get("/api/catalog/topics").json()}


def test_settings_update_and_effect(client: TestClient, fresh_db: None) -> None:
    current = client.get("/api/admin/settings", headers=ADMIN).json()
    assert current["invitation_quota"] == 20
    updated = client.put("/api/admin/settings", json={"invitation_quota": 25}, headers=ADMIN)
    assert updated.status_code == 200 and updated.json()["invitation_quota"] == 25
    assert client.get("/api/admin/settings", headers=ADMIN).json()["invitation_quota"] == 25
    # квота сразу видна рекрутеру
    dashboard = client.get("/api/companies/my/dashboard", headers=RECRUITER).json()
    assert dashboard["quota"]["limit"] == 25
    seeded = len(fixtures.load("audit_log"))
    audit = sql_sync(
        "SELECT summary, details FROM audit_log "
        f"WHERE action = 'settings_updated' AND id > {seeded}"
    )
    assert audit and audit[0][1] == {"invitation_quota": [20, 25]}
    assert "20 → 25" in audit[0][0]

    bad = [
        {"specialization": "backend", "junior_from": 0.5, "middle_from": 0.0, "senior_from": 1.0}
    ]
    response = client.put("/api/admin/settings", json={"grade_thresholds": bad}, headers=ADMIN)
    assert response.status_code == 422 and response.json()["code"] == "invalid_thresholds"
    zero = {k: 0 for k in current["ranking_weights"]}
    response = client.put("/api/admin/settings", json={"ranking_weights": zero}, headers=ADMIN)
    assert response.status_code == 422 and response.json()["code"] == "invalid_weights"
    assert (
        client.put("/api/admin/settings", json={"invitation_quota": 0}, headers=ADMIN).status_code
        == 422
    )

"""Тест из текста вакансии (T4.8): темы, шаблоны банка, черновики с item_id, список."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.nlp.vacancy_topics import BANK_TO_CATALOG, TOPICS
from app.nlp.validation import SAMPLES, vacancy_rows
from app.seed.testkit import sql_sync
from app.testing.engine.bank import bank_registry
from tests.conftest import ADMIN, CANDIDATE

VACANCIES = sorted((SAMPLES / "vacancies").glob("*.md"))


def test_every_bank_topic_is_mapped_to_catalog() -> None:
    catalog = {
        t["id"] for t in json.loads((SAMPLES.parent / "seed" / "topics.json").read_text("utf-8"))
    }
    pairs = {(t.specialization, t.topic) for t in bank_registry()}
    assert pairs <= set(BANK_TO_CATALOG), pairs - set(BANK_TO_CATALOG)
    assert set(BANK_TO_CATALOG.values()) <= catalog
    for topic in TOPICS:
        for spec in topic.specs:
            assert topic.catalog_topic(spec) in catalog, (topic.id, spec)
        assert topic.bank or topic.draft, topic.id  # без шаблонов — должна быть заготовка


def test_samples_spec_grade_and_expected_topics() -> None:
    rows = vacancy_rows()
    assert len(rows) == 5
    assert all(r.spec_ok for r in rows) and all(r.grade_ok for r in rows)
    covered = sum(sum(r.covered_expected) for r in rows)
    total = sum(len(r.expected_topics) for r in rows)
    assert covered / total >= 0.8
    assert all(len(r.items) >= 5 for r in rows)


@pytest.mark.parametrize("path", VACANCIES, ids=lambda p: p.name)
def test_build_from_sample(client: TestClient, path: Path) -> None:
    meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    resp = client.post(
        "/api/admin/vacancy-tests", json={"text": path.read_text(encoding="utf-8")}, headers=ADMIN
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["specialization"] == meta["specialization"] and body["grade"] == meta["grade"]
    assert body["parser"] == "rules" and body["id"] > 0
    assert body["vacancy_title"] == meta["title"]
    assert len(body["items"]) >= 5 and body["explanation"]
    for topic in body["topics"]:
        assert 0 < topic["confidence"] <= 1 and topic["matched_by"]
    for item in body["items"]:
        assert item["reason"] and item["template_id"]
        row = sql_sync(
            "SELECT generator, status FROM items WHERE id = :id", {"id": item["item_id"]}
        )
        assert row and row[0][0] == item["template_id"]
    for draft in body["drafts"]:
        assert draft["status"] == "draft" and draft["item_id"]
        assert draft["origin"] == "vocabulary"
        row = sql_sync(
            "SELECT status, source, topic FROM items WHERE id = :id", {"id": draft["item_id"]}
        )
        assert row and row[0][0] == "draft" and row[0][1] == "llm_vacancy"


def test_drafts_are_not_duplicated_and_list_shows_built(client: TestClient) -> None:
    text = VACANCIES[0].read_text(encoding="utf-8")
    first = client.post("/api/admin/vacancy-tests", json={"text": text}, headers=ADMIN).json()
    second = client.post("/api/admin/vacancy-tests", json={"text": text}, headers=ADMIN).json()
    assert first["drafts"] and [d["item_id"] for d in first["drafts"]] == [
        d["item_id"] for d in second["drafts"]
    ]
    assert all(d["reused"] for d in second["drafts"])
    assert [i["item_id"] for i in first["items"]] == [i["item_id"] for i in second["items"]]
    listed = client.get("/api/admin/vacancy-tests", headers=ADMIN).json()
    assert listed[0]["id"] == second["id"] and listed[1]["id"] == first["id"]
    assert listed[0]["drafts"][0]["item_id"] == second["drafts"][0]["item_id"]


def test_specialization_override_and_access(client: TestClient) -> None:
    body = client.post(
        "/api/admin/vacancy-tests",
        json={
            "text": "Ищем инженера: Docker, Kubernetes, Linux, мониторинг.",
            "specialization": "devops",
        },
        headers=ADMIN,
    ).json()
    assert body["specialization"] == "devops"
    assert {t["topic"] for t in body["topics"]} >= {"devops.containers", "devops.kubernetes"}
    assert (
        client.post(
            "/api/admin/vacancy-tests", json={"text": "x" * 30}, headers=CANDIDATE
        ).status_code
        == 403
    )

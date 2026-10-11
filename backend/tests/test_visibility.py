"""Правила видимости [ТЗ 2.1, 2.2 п.2]: рекрутер не видит ФИО и контакты до принятия/отклика."""

import json

from fastapi.testclient import TestClient

from app.common import fixtures
from tests.conftest import RECRUITER, RECRUITER_C2

PRIVATE_KEYS = {"full_name", "email", "phone", "telegram", "min_salary", "fsp_id", "user_id"}


def _private_values(candidate_id: int) -> list[str]:
    cand = fixtures.by_id("candidates", candidate_id)
    assert cand is not None
    return [v for v in (cand["full_name"], cand["email"], cand["phone"], cand["telegram"]) if v]


def test_anonymous_profile_has_no_name_or_contacts(client: TestClient) -> None:
    # кандидат 14: у компании 1 только «просмотренное» приглашение, отклика нет — контакты закрыты
    response = client.get("/api/candidates/14", headers=RECRUITER)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["contacts_visible"] is False
    assert body["contacts"] is None
    assert not PRIVATE_KEYS & set(body)
    raw = json.dumps(body, ensure_ascii=False)
    for value in _private_values(14):
        assert value not in raw
    assert body["pseudonym"].startswith("Кандидат #")


def test_contacts_open_after_accepted_invitation(client: TestClient) -> None:
    # кандидат 5 принял приглашение компании 1 (приглашение 8)
    body = client.get("/api/candidates/5", headers=RECRUITER).json()
    assert body["contacts_visible"] is True
    assert body["contacts"]["full_name"] == _private_values(5)[0]


def test_contacts_closed_for_other_company(client: TestClient) -> None:
    # компания 2: у кандидата 1 есть отклик на её вакансию — контакты открыты;
    # кандидат 3 с компанией 2 не связан — закрыты
    assert client.get("/api/candidates/1", headers=RECRUITER_C2).json()["contacts_visible"] is True
    body = client.get("/api/candidates/3", headers=RECRUITER_C2).json()
    assert body["contacts"] is None


def test_search_results_are_anonymous(client: TestClient) -> None:
    body = client.get("/api/candidates", params={"page_size": 100}, headers=RECRUITER).json()
    assert body["total"] > 0
    raw = json.dumps(body, ensure_ascii=False)
    for item in body["items"]:
        assert not PRIVATE_KEYS & set(item)
        for value in _private_values(item["id"]):
            assert value not in raw


def test_hidden_candidates_not_in_search(client: TestClient) -> None:
    # 37 — отозвал согласие на публикацию, 38 — пауза поиска, 39/40 — без теста
    ids: set[int] = set()
    for page in (1, 2, 3):
        body = client.get(
            "/api/candidates", params={"page_size": 100, "page": page}, headers=RECRUITER
        ).json()
        ids |= {c["id"] for c in body["items"]}
    assert len(ids) == body["total"]
    assert not ids & {37, 38, 39, 40}
    assert client.get("/api/candidates/37", headers=RECRUITER).status_code == 404


def test_invitation_contacts_only_when_accepted(client: TestClient) -> None:
    items = client.get("/api/invitations", headers=RECRUITER).json()
    assert items
    for inv in items:
        assert inv["candidate"] is not None
        assert not PRIVATE_KEYS & set(inv["candidate"])
        if inv["status"] == "accepted":
            assert inv["candidate_contacts"] is not None
        else:
            assert inv["candidate_contacts"] is None
        assert inv["recruiter_contacts"] is None

"""Код приглашения рекрутеров в компанию: только администратору компании (`GET /companies/my`)."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.seed.testkit import reseed_sync, sql_sync
from tests.conftest import RECRUITER, RECRUITER_C2, as_role

RECRUITER_NOT_ADMIN = as_role("recruiter", 42)  # рекрутер компании 1 без прав администратора


@pytest.fixture(scope="module", autouse=True)
def _fresh_db() -> Iterator[None]:
    reseed_sync()
    yield
    reseed_sync()


def test_invite_code_only_for_company_admin(client: TestClient) -> None:
    mine = client.get("/api/companies/my", headers=RECRUITER).json()
    code = mine["invite_code"]
    assert code and len(code) == 8
    assert sql_sync("SELECT invite_code FROM companies WHERE id = 1")[0][0] == code
    assert client.get("/api/companies/my", headers=RECRUITER).json()["invite_code"] == code
    other = client.get("/api/companies/my", headers=RECRUITER_C2).json()
    assert other["invite_code"] and other["invite_code"] != code
    assert (
        client.get("/api/companies/my", headers=RECRUITER_NOT_ADMIN).json()["invite_code"] is None
    )


def test_regenerate_and_register_by_code(client: TestClient) -> None:
    old = client.get("/api/companies/my", headers=RECRUITER).json()["invite_code"]
    forbidden = client.post("/api/companies/my/invite-code", headers=RECRUITER_NOT_ADMIN)
    assert forbidden.status_code == 403
    new = client.post("/api/companies/my/invite-code", headers=RECRUITER)
    assert new.status_code == 200 and new.json()["invite_code"] not in (None, old)
    audit = sql_sync("SELECT count(*) FROM audit_log WHERE action = 'company_invite_code_changed'")
    assert audit[0][0] == 1
    body = {
        "email": "new.recruiter@example.com",
        "password": "S3cure-pass",
        "full_name": "Новый Рекрутер",
        "role": "recruiter",
        "consent_processing": True,
        "company": {"invite_code": new.json()["invite_code"]},
    }
    assert client.post("/api/auth/register", json=body).status_code == 201
    row = sql_sync(
        "SELECT r.company_id, r.is_company_admin FROM recruiters r "
        "JOIN users u ON u.id = r.user_id WHERE u.email = :e",
        {"e": body["email"]},
    )
    assert row == [(1, False)]


def test_update_keeps_invite_code_for_admin(client: TestClient) -> None:
    current = client.get("/api/companies/my", headers=RECRUITER).json()
    payload = {
        k: current[k]
        for k in (
            "name",
            "description",
            "industry",
            "website",
            "city",
            "contact_email",
            "contact_phone",
        )
    }
    saved = client.put("/api/companies/my", json=payload, headers=RECRUITER)
    assert saved.status_code == 200 and saved.json()["invite_code"] == current["invite_code"]

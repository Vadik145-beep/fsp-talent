"""Зарплата от–до обязательна и от ≤ до: приглашение, вакансия, потребность [ТЗ 2.2 п.1]."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.invitations.schemas import InvitationCreate
from app.matching.schemas import NEED_CREATE_EXAMPLE, NeedCreate
from tests.conftest import RECRUITER

INVITATION = {
    "candidate_id": 10,
    "description": "Приглашаем в команду платёжного шлюза.",
    "salary_from": 200000,
    "salary_to": 500000,
    "contact_method": {"type": "telegram", "value": "@hr_example"},
}
VACANCY = {
    "title": "Middle Python",
    "description": "Описание вакансии для теста.",
    "specialization": "backend",
    "grade": "middle",
    "work_format": "remote",
    "salary_from": 200000,
    "salary_to": 280000,
}


def test_schema_rejects_from_greater_than_to() -> None:
    with pytest.raises(ValidationError) as exc:
        InvitationCreate.model_validate({**INVITATION, "salary_from": 300000, "salary_to": 200000})
    assert exc.value.errors()[0]["type"] == "salary_range_invalid"
    with pytest.raises(ValidationError):
        NeedCreate.model_validate({**NEED_CREATE_EXAMPLE, "salary_from": 500000})


def test_equal_bounds_are_allowed() -> None:
    model = InvitationCreate.model_validate(
        {**INVITATION, "salary_from": 250000, "salary_to": 250000}
    )
    assert model.salary_from == model.salary_to


@pytest.mark.parametrize("field", ["salary_from", "salary_to"])
def test_salary_is_required(client: TestClient, field: str) -> None:
    body = {k: v for k, v in INVITATION.items() if k != field}
    response = client.post("/api/invitations", json=body, headers=RECRUITER)
    assert response.status_code == 422


def test_api_rejects_invalid_range(client: TestClient) -> None:
    bad = {"salary_from": 300000, "salary_to": 100000}
    for path, body in (
        ("/api/invitations", {**INVITATION, **bad}),
        ("/api/vacancies", {**VACANCY, **bad}),
        ("/api/matching/needs", {**NEED_CREATE_EXAMPLE, **bad}),
    ):
        response = client.post(path, json=body, headers=RECRUITER)
        assert response.status_code == 422, path
        assert response.json()["details"]["errors"][0]["type"] == "salary_range_invalid"


def test_below_candidate_minimum_is_rejected_without_amount(client: TestClient) -> None:
    body = {**INVITATION, "salary_from": 10000, "salary_to": 20000}
    response = client.post("/api/invitations", json=body, headers=RECRUITER)
    assert response.status_code == 422
    error = response.json()
    assert error["code"] == "salary_below_expectations"
    assert error["details"] == {}


def test_valid_invitation_is_created(client: TestClient) -> None:
    response = client.post("/api/invitations", json=INVITATION, headers=RECRUITER)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "sent"
    assert body["candidate_contacts"] is None

"""Общие фикстуры тестов API. Нужен PostgreSQL (DATABASE_URL); перед сессией заливается сид."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _seeded_db() -> None:
    """Одна и та же исходная база для всех тестов, независимо от порядка файлов."""
    from app.seed.testkit import reseed_sync

    reseed_sync()


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def as_role(role: str, user_id: int | None = None) -> dict[str, str]:
    headers = {"X-Demo-Role": role}
    if user_id is not None:
        headers["X-Demo-User-Id"] = str(user_id)
    return headers


CANDIDATE = as_role("candidate")  # демо-соискатель: кандидат 1, с ФСП
CANDIDATE_NO_FSP = as_role("candidate", 26)  # кандидат 26, без ФСП
RECRUITER = as_role("recruiter")  # рекрутер 1, компания 1
RECRUITER_C2 = as_role("recruiter", 44)  # рекрутер компании 2
ADMIN = as_role("admin")

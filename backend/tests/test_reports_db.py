"""Жалобы на работодателей и блокировка компании (T10.6, T12.1) — на БД."""

import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.common import fixtures
from app.companies.antifraud import active_company_ids, ensure_company_active
from app.core.config import get_settings
from app.core.errors import AppError
from app.seed.testkit import reseed_sync, sql_sync
from tests.conftest import ADMIN, CANDIDATE, RECRUITER, as_role

RECRUITER_C3 = as_role("recruiter", 46)  # администратор компании 3
TASK = {
    "title": "Проверка блокировки",
    "statement": "Опишите, как устроен деплой без простоя.",
    "category": "devops:middle",
}


@pytest.fixture(autouse=True)
def _fresh_db() -> Iterator[None]:
    reseed_sync()
    yield


@pytest.fixture(scope="module", autouse=True)
def _restore_db() -> Iterator[None]:
    yield
    reseed_sync()


def companies(client: TestClient) -> dict[int, dict[str, object]]:
    return {c["id"]: c for c in client.get("/api/admin/companies", headers=ADMIN).json()}


def no_contact_candidate(company_id: int) -> int:
    """Кандидат без приглашений, откликов и заданий от компании."""
    contacted = {
        i["candidate_id"] for i in fixtures.load("invitations") if i["company_id"] == company_id
    }
    vacancies = {v["id"] for v in fixtures.load("vacancies") if v["company_id"] == company_id}
    contacted |= {
        a["candidate_id"] for a in fixtures.load("applications") if a["vacancy_id"] in vacancies
    }
    tasks = {t["id"] for t in fixtures.load("regular_tasks") if t["company_id"] == company_id}
    contacted |= {
        s["candidate_id"] for s in fixtures.load("task_submissions") if s["task_id"] in tasks
    }
    return next(c["id"] for c in fixtures.load("candidates") if c["id"] not in contacted)


def test_candidate_creates_report(client: TestClient) -> None:
    res = client.post(
        "/api/reports",
        json={
            "company_id": 3,
            "invitation_id": 3,
            "reason": "fake_vacancy",
            "text": "Просили оплатить курс",
        },
        headers=CANDIDATE,
    )
    assert res.status_code == 201, res.text
    report = res.json()
    assert report["status"] == "new" and report["company_name"] == "Облачные системы «Тайга»"
    assert report["reporter_candidate_id"] == 1 and report["invitation_id"] == 3
    row = sql_sync("SELECT status, reason FROM reports WHERE id = :i", {"i": report["id"]})
    assert row == [("new", "fake_vacancy")]
    audit = sql_sync(
        "SELECT action FROM audit_log WHERE target_type = 'report' AND target_id = :i",
        {"i": report["id"]},
    )
    assert audit == [("report_created",)]
    dup = client.post(
        "/api/reports",
        json={"company_id": 3, "reason": "spam", "text": "Снова спам"},
        headers=CANDIDATE,
    )
    assert dup.status_code == 409 and dup.json()["code"] == "report_exists"


def test_report_requires_contact_and_own_invitation(client: TestClient) -> None:
    stranger = no_contact_candidate(3)
    user_id = fixtures.by_id("candidates", stranger)["user_id"]  # type: ignore[index]
    res = client.post(
        "/api/reports",
        json={"company_id": 3, "reason": "spam", "text": "Не знаю их, но жалуюсь"},
        headers=as_role("candidate", user_id),
    )
    assert res.status_code == 403 and res.json()["code"] == "no_contact_with_company"
    foreign_inv = client.post(
        "/api/reports",
        json={"company_id": 3, "invitation_id": 14, "reason": "spam", "text": "Чужое приглашение"},
        headers=CANDIDATE,
    )
    assert foreign_inv.status_code == 404
    assert (
        client.post(
            "/api/reports",
            json={"company_id": 99, "reason": "spam", "text": "Нет такой"},
            headers=CANDIDATE,
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/reports", json={"company_id": 3, "reason": "spam", "text": "x"}, headers=CANDIDATE
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/reports",
            json={"company_id": 3, "reason": "spam", "text": "Рекрутер"},
            headers=RECRUITER,
        ).status_code
        == 403
    )


def test_admin_queue_order_and_filter(client: TestClient) -> None:
    queue = client.get("/api/admin/reports", headers=ADMIN).json()
    assert len(queue) == len(fixtures.load("reports"))
    order = {"new": 0, "in_review": 1, "resolved": 2, "rejected": 3}
    assert [order[r["status"]] for r in queue] == sorted(order[r["status"]] for r in queue)
    new = client.get("/api/admin/reports", params={"status": "new"}, headers=ADMIN).json()
    assert new and all(r["status"] == "new" for r in new)


def test_resolve_with_block(client: TestClient) -> None:
    before = companies(client)[3]["trust_score"]
    taken = client.patch("/api/admin/reports/1", json={"status": "in_review"}, headers=ADMIN)
    assert taken.status_code == 200 and taken.json()["status"] == "in_review"
    assert taken.json()["resolved_at"] is None
    bad = client.patch(
        "/api/admin/reports/1", json={"status": "rejected", "block_company": True}, headers=ADMIN
    )
    assert bad.status_code == 422 and bad.json()["code"] == "block_requires_resolve"
    done = client.patch(
        "/api/admin/reports/1",
        json={
            "status": "resolved",
            "resolution": "Подтвердили: просили деньги",
            "block_company": True,
        },
        headers=ADMIN,
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "resolved" and done.json()["resolved_at"]
    assert done.json()["resolution"] == "Подтвердили: просили деньги"
    after = companies(client)[3]
    assert after["blocked"] is True and after["trust_score"] < before
    assert sql_sync("SELECT resolved_by FROM reports WHERE id = 1")[0][0] == 48
    actions = [
        r[0]
        for r in sql_sync(
            "SELECT action FROM audit_log WHERE action IN "
            "('report_in_review', 'report_resolved', 'company_blocked') ORDER BY id"
        )
    ]
    assert actions == ["report_in_review", "report_resolved", "company_blocked"]
    again = client.patch("/api/admin/reports/1", json={"status": "rejected"}, headers=ADMIN)
    assert again.status_code == 409 and again.json()["code"] == "invalid_transition"
    assert (
        client.patch(
            "/api/admin/reports/999", json={"status": "rejected"}, headers=ADMIN
        ).status_code
        == 404
    )

    # блокировка действует: задания создавать нельзя, функция проверки бросает 403
    blocked = client.post("/api/tasks", json=TASK, headers=RECRUITER_C3)
    assert blocked.status_code == 403 and blocked.json()["code"] == "company_blocked"

    async def check() -> tuple[str, set[int]]:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine)() as session:
                await ensure_company_active(session, 1)  # не заблокирована — без ошибки
                active = set((await session.scalars(active_company_ids())).all())
                try:
                    await ensure_company_active(session, 3)
                except AppError as exc:
                    return exc.code, active
                return "no error", active
        finally:
            await engine.dispose()

    code, active = asyncio.run(check())
    assert code == "company_blocked" and active == {1, 2}

    # админ разблокировал — снова можно
    assert (
        client.patch("/api/admin/companies/3", json={"blocked": False}, headers=ADMIN).status_code
        == 200
    )
    assert client.post("/api/tasks", json=TASK, headers=RECRUITER_C3).status_code == 201


def test_reject_does_not_lower_score(client: TestClient) -> None:
    before = companies(client)[3]["trust_score"]
    res = client.patch(
        "/api/admin/reports/2",
        json={"status": "rejected", "resolution": "Не подтвердилось"},
        headers=ADMIN,
    )
    assert res.status_code == 200 and res.json()["status"] == "rejected"
    after = companies(client)[3]
    # жалоба «в работе» снижала на 5, отклонённая — не учитывается
    assert after["trust_score"] == pytest.approx(min(100, float(before) + 5))
    assert after["blocked"] is False

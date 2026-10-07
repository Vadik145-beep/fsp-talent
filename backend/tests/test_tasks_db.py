"""Регулярные задания на БД (E9): раздача, ответ, оценка 0–3, свежесть, сроки, планировщик."""

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.catalog.clock import now_msk
from app.common import fixtures
from app.core.config import get_settings
from app.seed.testkit import reseed_sync, sql_sync
from app.tasks.jobs import run_job
from app.tasks.service import TaskService
from tests.conftest import ADMIN, CANDIDATE, RECRUITER, RECRUITER_C2, as_role

TASK = {
    "title": "Очередь без потерь",
    "statement": "Как гарантировать, что сообщение из очереди обработано ровно один раз?",
    "category": "backend:junior",
    "deadline_days": 5,
}


def candidate(cid: int) -> dict[str, str]:
    cand = fixtures.by_id("candidates", cid)
    assert cand is not None
    return as_role("candidate", int(cand["user_id"]))


def run_db[T](fn: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def go() -> T:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                return await fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(go())


def freshness(cid: int) -> float:
    return float(
        sql_sync("SELECT freshness FROM candidate_profiles WHERE id = :i", {"i": cid})[0][0]
    )


@pytest.fixture(autouse=True)
def _fresh_db() -> Iterator[None]:
    reseed_sync()
    # сроки фикстур — реальные даты; сдвигаем активные задания в будущее, чтобы тесты не старели
    sql_sync(
        "UPDATE task_submissions SET due_at = now() + interval '5 days' WHERE status = 'assigned'"
    )
    yield


@pytest.fixture(scope="module", autouse=True)
def _restore_db() -> Iterator[None]:
    yield
    reseed_sync()


def eligible(category: str) -> set[int]:
    rows = sql_sync(
        """
        SELECT cp.id FROM candidate_profiles cp JOIN users u ON u.id = cp.user_id
        WHERE cp.category = :c AND NOT cp.job_search_paused AND NOT u.blocked
          AND cp.id NOT IN (SELECT candidate_id FROM task_submissions WHERE status = 'assigned')
        """,
        {"c": category},
    )
    return {r[0] for r in rows}


def test_inbox_from_db(client: TestClient) -> None:
    inbox = client.get("/api/tasks/inbox", headers=CANDIDATE)
    assert inbox.status_code == 200
    body = inbox.json()
    mine = [s for s in fixtures.load("task_submissions") if s["candidate_id"] == 1]
    assert body["active"]["id"] == next(s["id"] for s in mine if s["status"] == "assigned")
    assert {s["id"] for s in body["history"]} == {s["id"] for s in mine} - {body["active"]["id"]}
    assert body["freshness"] == fixtures.by_id("candidates", 1)["freshness"]  # type: ignore[index]
    assert body["active"]["company_name"] == "Северный код"


def test_new_candidate_without_fixtures_has_empty_inbox(client: TestClient) -> None:
    body = {
        "email": "tasks.newbie@example.com",
        "password": "S3cure-pass",
        "full_name": "Новичок Заданий",
        "role": "candidate",
        "consent_processing": True,
    }
    assert client.post("/api/auth/register", json=body).status_code == 201
    uid = sql_sync("SELECT id FROM users WHERE email = :e", {"e": body["email"]})[0][0]
    inbox = client.get("/api/tasks/inbox", headers=as_role("candidate", uid))
    assert inbox.status_code == 200, inbox.text
    assert inbox.json() == {"active": None, "history": [], "freshness": 0.0}


def test_create_distribute_answer_grade(client: TestClient) -> None:
    expected = eligible("backend:junior")
    assert expected, "в фикстурах должны быть свободные Backend · Junior"
    created = client.post("/api/tasks", json=TASK, headers=RECRUITER)
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["company_id"] == 1 and task["category_label"] == "Backend · Junior"
    assert task["submissions_count"] == len(expected)
    got = sql_sync(
        "SELECT candidate_id FROM task_submissions WHERE task_id = :t", {"t": task["id"]}
    )
    assert {r[0] for r in got} == expected

    cid = min(expected)
    headers = candidate(cid)
    inbox = client.get("/api/tasks/inbox", headers=headers).json()
    active = inbox["active"]
    assert active["task_id"] == task["id"] and active["status"] == "assigned"
    assert active["statement"] == TASK["statement"]
    assert active["due_at"] > active["assigned_at"]

    before = freshness(cid)
    answer = client.post(
        f"/api/tasks/submissions/{active['id']}/answer",
        json={"answer_kind": "approach", "answer_text": "  Идемпотентный ключ и outbox  "},
        headers=headers,
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["status"] == "submitted"
    assert answer.json()["answer_text"] == "Идемпотентный ключ и outbox"
    assert freshness(cid) == pytest.approx(min(1.0, before + 0.08), abs=1e-3)
    again = client.post(
        f"/api/tasks/submissions/{active['id']}/answer",
        json={"answer_kind": "text", "answer_text": "ещё раз"},
        headers=headers,
    )
    assert again.status_code == 409 and again.json()["code"] == "invalid_transition"
    # чужое задание кандидату не видно
    foreign = client.post(
        f"/api/tasks/submissions/{active['id']}/answer",
        json={"answer_kind": "text", "answer_text": "x"},
        headers=CANDIDATE,
    )
    assert foreign.status_code == 404

    tasks = client.get("/api/tasks", headers=RECRUITER).json()
    assert tasks[0]["id"] == task["id"] and all(t["company_id"] == 1 for t in tasks)
    subs = client.get(f"/api/tasks/{task['id']}/submissions", headers=RECRUITER).json()
    assert subs[0]["id"] == active["id"] and subs[0]["status"] == "submitted"
    assert all("full_name" not in (s["candidate"] or {}) for s in subs)
    assert all("email" not in (s["candidate"] or {}) for s in subs)
    # изоляция: рекрутер другой компании не видит и не оценивает
    assert (
        client.get(f"/api/tasks/{task['id']}/submissions", headers=RECRUITER_C2).status_code == 404
    )
    other = client.post(
        f"/api/tasks/submissions/{active['id']}/grade", json={"score": 3}, headers=RECRUITER_C2
    )
    assert other.status_code == 404

    mid = freshness(cid)
    graded = client.post(
        f"/api/tasks/submissions/{active['id']}/grade",
        json={"score": 3, "comment": "Чётко"},
        headers=RECRUITER,
    )
    assert graded.status_code == 200, graded.text
    g = graded.json()
    assert g["status"] == "graded" and g["score"] == 3 and g["grader_comment"] == "Чётко"
    assert freshness(cid) == pytest.approx(min(1.0, mid + 0.04 + 0.09), abs=1e-3)
    assert g["candidate"]["freshness"] == pytest.approx(freshness(cid), abs=1e-3)
    # переоценка меняет свежесть на разницу баллов
    after3 = freshness(cid)
    client.post(
        f"/api/tasks/submissions/{active['id']}/grade", json={"score": 1}, headers=RECRUITER
    )
    assert freshness(cid) == pytest.approx(after3 - 0.06, abs=1e-3)
    bad = client.post(
        f"/api/tasks/submissions/{active['id']}/grade", json={"score": 4}, headers=RECRUITER
    )
    assert bad.status_code == 422
    history = client.get("/api/tasks/inbox", headers=headers).json()
    assert history["active"] is None and history["history"][0]["score"] == 1


def test_grade_only_submitted(client: TestClient) -> None:
    assigned = next(
        s
        for s in fixtures.load("task_submissions")
        if s["status"] == "assigned" and s["task_id"] == 1
    )
    res = client.post(
        f"/api/tasks/submissions/{assigned['id']}/grade", json={"score": 2}, headers=RECRUITER
    )
    assert res.status_code == 409 and res.json()["code"] == "invalid_transition"


def test_expired_submission(client: TestClient) -> None:
    sql_sync("UPDATE task_submissions SET due_at = now() - interval '1 hour' WHERE id = 3")
    late = client.post(
        "/api/tasks/submissions/3/answer",
        json={"answer_kind": "text", "answer_text": "Поздно"},
        headers=CANDIDATE,
    )
    assert late.status_code == 409 and late.json()["code"] == "submission_expired"
    assert sql_sync("SELECT status FROM task_submissions WHERE id = 3")[0][0] == "expired"
    inbox = client.get("/api/tasks/inbox", headers=CANDIDATE).json()
    assert inbox["active"] is None and any(s["id"] == 3 for s in inbox["history"])


def test_inbox_expires_overdue(client: TestClient) -> None:
    sql_sync("UPDATE task_submissions SET due_at = now() - interval '1 hour' WHERE id = 3")
    inbox = client.get("/api/tasks/inbox", headers=CANDIDATE).json()
    assert inbox["active"] is None
    assert next(s for s in inbox["history"] if s["id"] == 3)["status"] == "expired"


def test_validation_and_roles(client: TestClient) -> None:
    unknown = client.post(
        "/api/tasks", json={**TASK, "category": "backend:guru"}, headers=RECRUITER
    )
    assert unknown.status_code == 422 and unknown.json()["code"] == "unknown_category"
    short = client.post("/api/tasks", json={**TASK, "statement": "коротко"}, headers=RECRUITER)
    assert short.status_code == 422
    assert client.post("/api/tasks", json=TASK, headers=CANDIDATE).status_code == 403
    assert client.get("/api/tasks/inbox", headers=RECRUITER).status_code == 403
    assert client.post("/api/tasks/jobs/run", headers=RECRUITER).status_code == 403


def test_one_active_task_per_candidate(client: TestClient) -> None:
    # кандидат с активным заданием новое не получает, после ответа — получает при раздаче
    task = client.post("/api/tasks", json={**TASK, "category": "backend:middle"}, headers=RECRUITER)
    subs = sql_sync(
        "SELECT candidate_id FROM task_submissions WHERE task_id = :t", {"t": task.json()["id"]}
    )
    assert 1 not in {r[0] for r in subs}  # у демо-кандидата уже есть активное задание №3
    client.post(
        "/api/tasks/submissions/3/answer",
        json={"answer_kind": "text", "answer_text": "Готово"},
        headers=CANDIDATE,
    )
    again = client.post(f"/api/tasks/{task.json()['id']}/distribute", headers=RECRUITER)
    assert again.status_code == 200 and again.json()["assigned"] == 1
    inbox = client.get("/api/tasks/inbox", headers=CANDIDATE).json()
    assert inbox["active"]["task_id"] == task.json()["id"]
    # повторно то же задание не выдаётся
    assert client.post(f"/api/tasks/{task.json()['id']}/distribute", headers=RECRUITER).json() == {
        "assigned": 0
    }
    assert (
        client.post(f"/api/tasks/{task.json()['id']}/distribute", headers=RECRUITER_C2).status_code
        == 404
    )


def test_scheduler_distributes_and_skips_blocked(client: TestClient) -> None:
    # освободили кандидата 1 — планировщик выдаёт ему задание его категории
    sql_sync("UPDATE task_submissions SET status = 'submitted' WHERE id = 3")
    for company_id, recruiter_id in ((3, 6), (2, 4)):
        sql_sync(
            "INSERT INTO regular_tasks (company_id, recruiter_id, title, statement, category, "
            "deadline_days, status) VALUES (:c, :r, 'Новое', 'Задание для планировщика', "
            "'backend:middle', 7, 'active')",
            {"c": company_id, "r": recruiter_id},
        )
    sql_sync("UPDATE companies SET blocked = true WHERE id = 3")
    result = client.post("/api/tasks/jobs/run", params={"job": "distribute"}, headers=ADMIN)
    assert result.status_code == 200, result.text
    assert result.json()["assigned"] >= 1
    rows = sql_sync(
        "SELECT t.company_id FROM task_submissions s JOIN regular_tasks t ON t.id = s.task_id "
        "WHERE s.candidate_id = 1 AND s.status = 'assigned'"
    )
    assert rows == [(2,)]  # задание заблокированной компании 3 не раздаётся


def test_company_blocked_cannot_create_task(client: TestClient) -> None:
    sql_sync("UPDATE companies SET blocked = true WHERE id = 1")
    res = client.post("/api/tasks", json=TASK, headers=RECRUITER)
    assert res.status_code == 403 and res.json()["code"] == "company_blocked"
    assert client.post("/api/tasks/1/distribute", headers=RECRUITER).status_code == 403


def test_freshness_decay(client: TestClient) -> None:
    before = {r[0]: r[1] for r in sql_sync("SELECT id, freshness FROM candidate_profiles")}
    now = now_msk()

    async def job(session: AsyncSession, at: Any) -> Any:
        return await run_job(session, "daily", at)

    first = run_db(lambda s: job(s, now))  # первый запуск — как будто прошли сутки
    assert first["freshness_factor"] == pytest.approx(0.5 ** (1 / 30), abs=1e-3)
    month = run_db(lambda s: job(s, now + timedelta(days=30)))
    assert month["freshness_factor"] == pytest.approx(0.5, abs=1e-3)
    after = {r[0]: r[1] for r in sql_sync("SELECT id, freshness FROM candidate_profiles")}
    for cid, value in before.items():
        assert after[cid] == pytest.approx(value * 0.5 ** (31 / 30), abs=2e-3)
    # повторный запуск в тот же момент ничего не меняет
    same = run_db(lambda s: TaskService(s).decay_freshness(now + timedelta(days=30)))
    assert same["factor"] == 1.0
    log = sql_sync("SELECT count(*) FROM audit_log WHERE action = 'freshness_decayed'")
    assert log[0][0] == 2


def test_job_endpoint_tick(client: TestClient) -> None:
    sql_sync("UPDATE task_submissions SET due_at = now() - interval '1 day' WHERE id = 7")
    res = client.post("/api/tasks/jobs/run", headers=ADMIN).json()
    assert res["job"] == "tick" and res["expired"] >= 1
    assert 0 < res["freshness_factor"] <= 1
    assert sql_sync("SELECT status FROM task_submissions WHERE id = 7")[0][0] == "expired"

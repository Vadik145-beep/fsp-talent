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
from app.tasks.service import TaskService, due_at, week_start
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
    # сроки фикстур — реальные даты; сдвигаем активные задания в будущее, а ответы — в прошлые
    # недели, чтобы тесты не зависели от дня недели и не старели
    sql_sync(
        "UPDATE task_submissions SET due_at = now() + interval '5 days' WHERE status = 'assigned'"
    )
    sql_sync(
        "UPDATE task_submissions SET submitted_at = now() - interval '14 days' "
        "WHERE submitted_at IS NOT NULL"
    )
    yield


@pytest.fixture(scope="module", autouse=True)
def _restore_db() -> Iterator[None]:
    yield
    reseed_sync()


def eligible(category: str) -> set[int]:
    """Кандидаты категории, которым раздача может предложить задачу."""
    rows = sql_sync(
        """
        SELECT cp.id FROM candidate_profiles cp JOIN users u ON u.id = cp.user_id
        WHERE cp.category = :c AND NOT cp.job_search_paused AND NOT u.blocked
        """,
        {"c": category},
    )
    return {r[0] for r in rows}


def offers_of(cid: int) -> list[tuple[int, int]]:
    """(id задания, id компании) активных предложений кандидата."""
    rows = sql_sync(
        "SELECT s.task_id, t.company_id FROM task_submissions s "
        "JOIN regular_tasks t ON t.id = s.task_id "
        "WHERE s.candidate_id = :c AND s.status = 'assigned' ORDER BY s.task_id",
        {"c": cid},
    )
    return [(r[0], r[1]) for r in rows]


def distribute(client: TestClient) -> int:
    res = client.post("/api/tasks/jobs/run", params={"job": "distribute"}, headers=ADMIN)
    assert res.status_code == 200, res.text
    return int(res.json()["assigned"])


def clear_offers(cid: int) -> None:
    sql_sync(
        "UPDATE task_submissions SET status = 'expired' "
        "WHERE candidate_id = :c AND status = 'assigned'",
        {"c": cid},
    )


def recruiter_of(task_id: int) -> dict[str, str]:
    company = sql_sync("SELECT company_id FROM regular_tasks WHERE id = :t", {"t": task_id})[0][0]
    user = sql_sync(
        "SELECT user_id FROM recruiters WHERE company_id = :c ORDER BY id LIMIT 1", {"c": company}
    )[0][0]
    return {1: RECRUITER, 2: RECRUITER_C2}.get(company) or as_role("recruiter", int(user))


def test_inbox_from_db(client: TestClient) -> None:
    inbox = client.get("/api/tasks/inbox", headers=CANDIDATE)
    assert inbox.status_code == 200
    body = inbox.json()
    mine = [s for s in fixtures.load("task_submissions") if s["candidate_id"] == 1]
    assert [o["id"] for o in body["offers"]] == [s["id"] for s in mine if s["status"] == "assigned"]
    assert {s["id"] for s in body["history"]} == {
        s["id"] for s in mine if s["status"] in ("submitted", "graded")
    }
    assert body["answered_this_week"] is False
    assert body["freshness"] == fixtures.by_id("candidates", 1)["freshness"]  # type: ignore[index]
    assert body["offers"][0]["company_name"] == "Северный код"


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
    assert inbox.json() == {
        "offers": [],
        "history": [],
        "answered_this_week": False,
        "freshness": 0.0,
    }


def test_create_distribute_answer_grade(client: TestClient) -> None:
    # категория без задач других компаний — новое задание получают все кандидаты категории
    sql_sync("DELETE FROM regular_tasks WHERE category = 'backend:junior'")
    expected = eligible("backend:junior")
    assert expected, "в фикстурах должны быть Backend · Junior"
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
    active = inbox["offers"][0]
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
    assert history["offers"] == [] and history["history"][0]["score"] == 1
    assert history["answered_this_week"] is True


def test_three_offers_from_different_companies(client: TestClient) -> None:
    clear_offers(1)
    solved = {
        s["task_id"]
        for s in fixtures.load("task_submissions")
        if s["candidate_id"] == 1 and s["status"] in ("submitted", "graded")
    }
    assert distribute(client) > 0
    offers = offers_of(1)
    # единственное задание «Северного кода» в Backend · Middle кандидат уже решил — не повторяем
    assert {c for _, c in offers} == {2, 3}
    assert not {t for t, _ in offers} & solved
    # новое задание компании 1 дополняет тройку сразу при создании
    created = client.post(
        "/api/tasks", json={**TASK, "category": "backend:middle"}, headers=RECRUITER
    )
    assert created.status_code == 201, created.text
    offers = offers_of(1)
    assert len(offers) == 3 and {c for _, c in offers} == {1, 2, 3}
    assert created.json()["id"] in {t for t, _ in offers}
    # повторная раздача ничего не добавляет — тройка полная
    before = offers_of(1)
    distribute(client)
    assert offers_of(1) == before
    inbox = client.get("/api/tasks/inbox", headers=CANDIDATE).json()
    assert len(inbox["offers"]) == 3
    dashboard = client.get("/api/candidates/me/dashboard", headers=CANDIDATE).json()
    assert len(dashboard["task_offers"]) == 3
    assert dashboard["active_task"] == dashboard["task_offers"][0]


def test_hiring_company_first(client: TestClient) -> None:
    # Backend · Middle ищет только «Северный код» (потребность активна) — при одном месте
    # в тройке кандидат получает его задачу, а не случайную
    hiring = {
        n["company_id"]
        for n in fixtures.load("needs")
        if n["category"] == "backend:middle" and n["status"] == "active"
    }
    assert hiring == {1}
    clear_offers(1)
    sql_sync(
        "INSERT INTO regular_tasks (company_id, recruiter_id, title, statement, category, "
        "deadline_days, status) VALUES (1, 1, 'Новое', 'Задание нанимающей компании', "
        "'backend:middle', 7, 'active')"
    )

    async def one_slot(session: AsyncSession) -> dict[int, int]:
        service = TaskService(session)
        service.settings = service.settings.model_copy(update={"offers_per_week": 1})
        result = await service.distribute_category("backend:middle")
        await session.commit()
        return result

    run_db(one_slot)
    assert [c for _, c in offers_of(1)] == [1]


def test_answer_one_skips_others_and_weekly_limit(client: TestClient) -> None:
    clear_offers(1)
    client.post("/api/tasks", json={**TASK, "category": "backend:middle"}, headers=RECRUITER)
    inbox = client.get("/api/tasks/inbox", headers=CANDIDATE).json()
    assert len(inbox["offers"]) == 3
    chosen, *rest = inbox["offers"]
    res = client.post(
        f"/api/tasks/submissions/{chosen['id']}/answer",
        json={"answer_kind": "text", "answer_text": "Выбрал эту"},
        headers=CANDIDATE,
    )
    assert res.status_code == 200, res.text
    statuses = sql_sync(
        "SELECT status FROM task_submissions WHERE id = ANY(:ids)",
        {"ids": [o["id"] for o in rest]},
    )
    assert {r[0] for r in statuses} == {"skipped"}
    after = client.get("/api/tasks/inbox", headers=CANDIDATE).json()
    assert after["offers"] == [] and after["answered_this_week"] is True
    history_ids = {s["id"] for s in after["history"]}
    assert chosen["id"] in history_ids and not history_ids & {o["id"] for o in rest}
    # снятые задачи рекрутер не видит в ответах
    for o in rest:
        own = client.get(
            f"/api/tasks/{o['task_id']}/submissions", headers=recruiter_of(o["task_id"])
        )
        assert own.status_code == 200, own.text
        assert o["id"] not in {s["id"] for s in own.json()}
    # на этой неделе новых задач нет — ни по расписанию, ни при новом задании
    distribute(client)
    client.post("/api/tasks", json={**TASK, "category": "backend:middle"}, headers=RECRUITER_C2)
    assert offers_of(1) == []
    # неделя прошла — решённая задача не возвращается, невыбранные могут прийти снова
    sql_sync(
        "UPDATE task_submissions SET submitted_at = submitted_at - interval '8 days' "
        "WHERE candidate_id = 1 AND submitted_at IS NOT NULL"
    )
    distribute(client)
    offers = offers_of(1)
    assert len(offers) >= 2 and chosen["task_id"] not in {t for t, _ in offers}
    assert len({c for _, c in offers}) == len(offers)  # по одной задаче от компании


def test_offer_deadline_and_week_helpers() -> None:
    at = now_msk().replace(year=2026, month=10, day=12, hour=3, minute=30, second=7)  # пн
    assert due_at(at, 7) == at.replace(day=19, hour=3, minute=0, second=0, microsecond=0)
    assert due_at(at, 7) < at + timedelta(days=7)  # раздача через неделю видит его просроченным
    assert week_start(at) == at.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = at.replace(day=18, hour=23)
    assert week_start(sunday) == week_start(at)
    assert week_start(sunday + timedelta(hours=1)) == week_start(at) + timedelta(days=7)


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
    assert inbox["offers"] == [] and all(s["id"] != 3 for s in inbox["history"])


def test_inbox_expires_overdue(client: TestClient) -> None:
    sql_sync("UPDATE task_submissions SET due_at = now() - interval '1 hour' WHERE id = 3")
    inbox = client.get("/api/tasks/inbox", headers=CANDIDATE).json()
    assert inbox["offers"] == []
    assert sql_sync("SELECT status FROM task_submissions WHERE id = 3")[0][0] == "expired"


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


def test_scheduler_skips_blocked_company(client: TestClient) -> None:
    clear_offers(1)
    sql_sync("UPDATE companies SET blocked = true WHERE id = 3")
    assert distribute(client) >= 1
    companies = {c for _, c in offers_of(1)}
    assert companies and 3 not in companies  # задания заблокированной компании не раздаются


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

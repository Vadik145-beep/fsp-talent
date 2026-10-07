"""Дашборд администратора на БД (T10.1): числа сверяются с SQL-запросами к той же базе."""

from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.catalog.clock import now_msk
from app.seed.testkit import reseed_sync, sql_sync
from tests.conftest import ADMIN, CANDIDATE, RECRUITER


@pytest.fixture(autouse=True)
def _fresh_db() -> Iterator[None]:
    reseed_sync()
    yield


@pytest.fixture(scope="module", autouse=True)
def _restore_db() -> Iterator[None]:
    yield
    reseed_sync()


def effective_invitations() -> dict[str, int]:
    rows = sql_sync(
        """
        SELECT CASE WHEN status IN ('sent', 'viewed') AND expires_at < now() THEN 'expired'
                    ELSE status END AS s, count(*)
        FROM invitations GROUP BY s
        """
    )
    return dict(rows)


def test_dashboard_matches_db(client: TestClient) -> None:
    res = client.get("/api/admin/dashboard", headers=ADMIN)
    assert res.status_code == 200, res.text
    body = res.json()

    roles = dict(sql_sync("SELECT role, count(*) FROM users WHERE email_verified GROUP BY role"))
    assert body["users_by_role"] == {
        r: roles.get(r, 0) for r in ("candidate", "recruiter", "admin")
    }

    finished = sql_sync("SELECT count(*) FROM test_sessions WHERE status = 'finished'")[0][0]
    assert body["tests_total"] == finished > 0
    assert sum(d["count"] for d in body["tests_by_day"]) == finished
    dates = [d["date"] for d in body["tests_by_day"]]
    assert dates == sorted(dates)

    invs = effective_invitations()
    expected = {
        s: invs.get(s, 0)
        for s in ("sent", "viewed", "accepted", "declined", "expired", "withdrawn")
    }
    assert body["invitations_by_status"] == expected
    base = sum(expected.values()) - expected["withdrawn"]
    assert body["invite_to_accept_conversion"] == round(expected["accepted"] / base, 3)

    leaks = sql_sync("SELECT id FROM items WHERE leak_flag ORDER BY leak_score DESC, id")
    assert [x["item_id"] for x in body["leak_flags"]] == [r[0] for r in leaks]
    assert body["leak_flags"], "в сиде есть шаблоны с флагом утечки"

    open_reports = sql_sync("SELECT count(*) FROM reports WHERE status IN ('new', 'in_review')")
    assert body["open_reports"] == open_reports[0][0]


def test_dashboard_reacts_to_changes(client: TestClient) -> None:
    before = client.get("/api/admin/dashboard", headers=ADMIN).json()
    # новая жалоба → открытых больше; принятое приглашение → конверсия растёт
    client.post(
        "/api/reports",
        json={"company_id": 3, "reason": "spam", "text": "Спамят приглашениями"},
        headers=CANDIDATE,
    )
    sql_sync("UPDATE invitations SET status = 'accepted' WHERE id = 2")
    sql_sync(
        "INSERT INTO test_sessions (candidate_id, specialization, target_grade, kind, status, "
        "started_at, finished_at, items_answered, max_items, topic_scores, engine_state) "
        "VALUES (2, 'devops', 'junior', 'placement', 'finished', now(), now(), 10, 15, '[]', '{}')"
    )
    after = client.get("/api/admin/dashboard", headers=ADMIN).json()
    assert after["open_reports"] == before["open_reports"] + 1
    assert after["invite_to_accept_conversion"] > before["invite_to_accept_conversion"]
    assert (
        after["invitations_by_status"]["accepted"]
        == before["invitations_by_status"]["accepted"] + 1
    )
    assert after["tests_total"] == before["tests_total"] + 1
    today = now_msk().date().isoformat()
    assert after["tests_by_day"][-1]["date"] == today


def test_dashboard_periods(client: TestClient) -> None:
    sql_sync(
        "INSERT INTO test_sessions (candidate_id, specialization, target_grade, kind, status, "
        "started_at, finished_at, items_answered, max_items, topic_scores, engine_state) "
        "VALUES (2, 'devops', 'junior', 'placement', 'finished', now(), now(), 10, 15, '[]', '{}')"
    )
    totals = {}
    for period in ("7d", "30d", "all"):
        body = client.get("/api/admin/dashboard", params={"period": period}, headers=ADMIN).json()
        totals[period] = body["tests_total"]
        if period != "all":
            days = int(period[:-1])
            border = now_msk().date() - timedelta(days=days)
            assert all(date.fromisoformat(d["date"]) >= border for d in body["tests_by_day"])
    assert 1 <= totals["7d"] <= totals["30d"] <= totals["all"]
    week = sql_sync(
        "SELECT count(*) FROM test_sessions WHERE status = 'finished' "
        "AND finished_at >= now() - interval '7 days'"
    )[0][0]
    assert totals["7d"] == week
    assert (
        client.get("/api/admin/dashboard", params={"period": "year"}, headers=ADMIN).status_code
        == 422
    )


def test_dashboard_only_for_admin(client: TestClient) -> None:
    assert client.get("/api/admin/dashboard", headers=RECRUITER).status_code == 403
    assert client.get("/api/admin/dashboard").status_code == 401

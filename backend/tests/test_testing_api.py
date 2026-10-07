"""Тест кандидата на БД и движке (трек 3a): опрос, сессия, итог, утечки, калибровка."""

import random
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.seed.testkit import reseed_sync, sql_sync
from app.testing.bank import registry
from app.testing.formats import answer_payload
from app.testing.settings import get_testing_settings
from tests.conftest import ADMIN, CANDIDATE, RECRUITER, as_role

CAND_26 = as_role("candidate", 26)  # Frontend · Junior, без ФСП
CAND_27 = as_role("candidate", 27)
CAND_40 = as_role("candidate", 40)  # без категории и без сессий
ITEM_VIEW_KEYS = {
    "instance_id",
    "format",
    "topic",
    "topic_label",
    "prompt",
    "code",
    "code_language",
    "options",
    "steps",
    "unit",
    "time_limit_sec",
}
WRONG = {"choice_ids": ["zz"], "text": "###", "line": 9999, "order": ["zz"]}


@pytest.fixture(autouse=True)
def fresh_db() -> Iterator[None]:
    reseed_sync()
    yield


def pending(session_id: int) -> tuple[int, str, int]:
    """Текущий показ сессии: (id строки, код шаблона, seed) — то, что знает только сервер."""
    rows = sql_sync(
        "SELECT ta.id, i.code, ta.seed FROM test_answers ta JOIN items i ON i.id = ta.item_id"
        " WHERE ta.session_id = :s AND ta.answered_at IS NULL",
        {"s": session_id},
    )
    assert len(rows) == 1
    return rows[0][0], rows[0][1], rows[0][2]


def correct_answer(session_id: int) -> dict[str, Any]:
    _, code, seed = pending(session_id)
    return answer_payload(registry().get(code).generate(seed))


def start(
    client: TestClient, headers: dict[str, str], spec: str, grade: str, kind: str = "placement"
) -> dict[str, Any]:
    r = client.post(
        "/api/testing/sessions",
        json={"specialization": spec, "target_grade": grade, "kind": kind},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


def run_to_end(
    client: TestClient, headers: dict[str, str], state: dict[str, Any], *, right: bool
) -> list[dict[str, Any]]:
    sid = state["session"]["id"]
    item = state["current_item"]
    shown = []
    while item is not None:
        assert set(item) == ITEM_VIEW_KEYS
        shown.append(item)
        answer = correct_answer(sid) if right else WRONG
        r = client.post(
            f"/api/testing/sessions/{sid}/answers",
            json={"instance_id": item["instance_id"], "answer": answer},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        ack = r.json()
        assert "correct" not in ack
        item = ack["next_item"]
    return shown


# ---------------------------------------------------------------- опрос


def test_survey_rules(client: TestClient) -> None:
    survey = client.get("/api/testing/survey", headers=CAND_26).json()
    assert {q["id"] for q in survey} >= {"q1", "q2", "q4"}
    body = {
        "answers": [
            {"question_id": "q1", "option_ids": ["q1_infra"]},
            {"question_id": "q2", "option_ids": ["q2_ops", "q2_python"]},
            {"question_id": "q3", "option_ids": ["q3_deploy"]},
            {"question_id": "q4", "option_ids": ["q4_3"]},
            {"question_id": "q8", "text": "Перевели сервисы в Kubernetes, писали Terraform"},
        ]
    }
    res = client.post("/api/testing/survey", json=body, headers=CAND_26).json()
    assert res["recommended_specialization"] == "devops"
    assert res["suggested_grade"] == "middle"
    assert res["topics"] and all(t.startswith("devops.") for t in res["topics"])
    # темы по весам ответов: q1 (3) → linux, q3 (2) → ci_cd, затем стек и слова из текста
    assert res["topics"][:2] == ["devops.linux", "devops.ci_cd"]
    assert res["alternatives"][0]["specialization"] == "devops"
    history = client.get("/api/testing/grade", headers=CAND_26).json()["history"]
    assert history[-1]["event"] == "survey" and history[-1]["specialization"] == "devops"


# ---------------------------------------------------------------- полный проход


def test_full_pass_updates_profile_and_hides_key(client: TestClient) -> None:
    state = start(client, CAND_26, "frontend", "middle", "higher")
    assert state["session"]["max_items"] == 20 and state["item_number"] == 1
    assert 0 < state["time_left_sec"] <= state["current_item"]["time_limit_sec"]
    shown = run_to_end(client, CAND_26, state, right=True)
    assert 6 <= len(shown) <= 20
    # ключ, шаблон и seed не уходят клиенту
    codes = {r[0] for r in sql_sync("SELECT code FROM items")}
    seeds = {str(r[0]) for r in sql_sync("SELECT seed FROM test_answers WHERE seed > 99999")}
    for item in shown:
        assert item["instance_id"] not in codes and item["instance_id"] not in seeds
        assert "correct_answer" not in item and "seed" not in item
    sid = state["session"]["id"]
    res = client.get(f"/api/testing/sessions/{sid}/result", headers=CAND_26).json()
    assert res["passed"] and res["outcome"] in {"passed_claimed", "suggest_higher"}
    assert res["ci_low"] < res["theta"] < res["ci_high"]
    assert res["topic_scores"] and "correct_answer" not in str(res)
    profile = client.get("/api/candidates/me/profile", headers=CAND_26).json()
    assert profile["category"] == "frontend:middle" and profile["theta"] == res["theta"]
    grade = client.get("/api/testing/grade", headers=CAND_26).json()
    same = client.get("/api/candidates/me/grade", headers=CAND_26).json()
    assert grade == same
    assert grade["grade"] == "middle"
    events = [h["event"] for h in grade["history"] if h["test_session_id"] == sid]
    assert events[:2] == ["test_passed", "grade_changed"]
    assert grade["tests"][0]["id"] == sid and grade["tests"][0]["result_category"]
    # показы видны в админке
    bank = client.get("/api/admin/items", params={"page_size": 200}, headers=ADMIN).json()
    assert sum(i["exposures"] for i in bank["items"] if i["id"] > 30) == len(shown)


def test_failed_attempt_keeps_grade_and_blocks_retry(client: TestClient) -> None:
    state = start(client, CAND_26, "frontend", "middle", "higher")
    run_to_end(client, CAND_26, state, right=False)
    sid = state["session"]["id"]
    res = client.get(f"/api/testing/sessions/{sid}/result", headers=CAND_26).json()
    assert not res["passed"] and res["outcome"] == "suggest_lower"
    assert res["recommendation"]["action"] == "offer_lower"
    profile = client.get("/api/candidates/me/profile", headers=CAND_26).json()
    assert profile["category"] == "frontend:junior"  # принудительно не понижаем
    again = client.post(
        "/api/testing/sessions",
        json={"specialization": "frontend", "target_grade": "middle", "kind": "higher"},
        headers=CAND_26,
    )
    assert again.status_code == 409 and again.json()["code"] == "cooldown_active"
    assert again.json()["details"]["reason_code"] == "failed_retry_cooldown"


def test_grade_change_cooldown_after_pass(client: TestClient) -> None:
    run_to_end(client, CAND_26, start(client, CAND_26, "frontend", "middle", "higher"), right=True)
    higher = client.post(
        "/api/testing/sessions",
        json={"specialization": "frontend", "target_grade": "senior", "kind": "higher"},
        headers=CAND_26,
    )
    assert higher.status_code == 409
    assert higher.json()["details"]["reason_code"] == "grade_change_cooldown"


def test_two_active_sessions_forbidden(client: TestClient) -> None:
    first = start(client, CAND_27, "backend", "junior")
    second = client.post(
        "/api/testing/sessions",
        json={"specialization": "backend", "target_grade": "junior"},
        headers=CAND_27,
    )
    assert second.status_code == 409 and second.json()["code"] == "session_in_progress"
    assert second.json()["details"]["session_id"] == first["session"]["id"]


def test_wrong_kind_and_wrong_item(client: TestClient) -> None:
    bad = client.post(
        "/api/testing/sessions",
        json={"specialization": "frontend", "target_grade": "middle", "kind": "lower"},
        headers=CAND_26,
    )
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_kind"
    state = start(client, CAND_26, "frontend", "junior")
    sid = state["session"]["id"]
    wrong = client.post(
        f"/api/testing/sessions/{sid}/answers",
        json={"instance_id": "nope", "answer": WRONG},
        headers=CAND_26,
    )
    assert wrong.status_code == 409 and wrong.json()["code"] == "wrong_item"
    other = client.get(f"/api/testing/sessions/{sid}", headers=CANDIDATE)
    assert other.status_code == 404


def test_answer_after_time_limit_is_wrong(client: TestClient) -> None:
    state = start(client, CAND_26, "frontend", "junior")
    sid = state["session"]["id"]
    item = state["current_item"]
    row_id, _, _ = pending(sid)
    answer = correct_answer(sid)
    sql_sync(
        "UPDATE test_answers SET shown_at = shown_at - make_interval(secs => :s) WHERE id = :id",
        {"s": item["time_limit_sec"] + 5, "id": row_id},
    )
    view = client.get(f"/api/testing/sessions/{sid}", headers=CAND_26).json()
    assert view["time_left_sec"] == 0
    ack = client.post(
        f"/api/testing/sessions/{sid}/answers",
        json={"instance_id": item["instance_id"], "answer": answer},
        headers=CAND_26,
    ).json()
    assert ack["time_expired"] is True
    correct, timed_out = sql_sync(
        "SELECT correct, timed_out FROM test_answers WHERE id = :id", {"id": row_id}
    )[0]
    assert correct is False and timed_out is True


def test_abandoned_session_expires_and_counts_as_attempt(client: TestClient) -> None:
    state = start(client, CAND_26, "frontend", "junior")
    sid = state["session"]["id"]
    row_id, _, _ = pending(sid)
    sql_sync(
        "UPDATE test_answers SET shown_at = shown_at - interval '2 hours' WHERE id = :id",
        {"id": row_id},
    )
    view = client.get(f"/api/testing/sessions/{sid}", headers=CAND_26).json()
    assert view["session"]["status"] == "abandoned" and view["current_item"] is None
    res = client.get(f"/api/testing/sessions/{sid}/result", headers=CAND_26).json()
    assert res["outcome"] == "abandoned" and res["recommendation"]["action"] == "retry_later"
    profile = client.get("/api/candidates/me/profile", headers=CAND_26).json()
    assert profile["category"] == "frontend:junior"
    retry = client.post(
        "/api/testing/sessions",
        json={"specialization": "frontend", "target_grade": "junior"},
        headers=CAND_26,
    )
    assert retry.status_code == 409 and retry.json()["code"] == "cooldown_active"


def test_pilot_item_does_not_change_theta(client: TestClient) -> None:
    # один шаблон backend делаем пилотным: движок вставит его в 1–2 позиции из первых шести
    client.get("/api/admin/items", headers=ADMIN)  # синхронизация банка после пересева
    pilot_id = sql_sync(
        "SELECT id FROM items WHERE code LIKE 'backend.%' AND status = 'active' ORDER BY id LIMIT 1"
    )
    sql_sync("UPDATE items SET status = 'pilot' WHERE id = :id", {"id": pilot_id[0][0]})
    state = start(client, CAND_27, "backend", "junior")
    sid = state["session"]["id"]
    run_to_end(client, CAND_27, state, right=True)
    rows = sql_sync(
        "SELECT position, is_scored, theta_after, item_id FROM test_answers"
        " WHERE session_id = :s ORDER BY position",
        {"s": sid},
    )
    pilots = [r for r in rows if not r[1]]
    assert pilots and all(r[3] == pilot_id[0][0] for r in pilots)
    for pos, _, theta, _ in pilots:
        before = next(r[2] for r in rows if r[0] == pos - 1)
        assert theta == before  # верный ответ на пилотную задачу не сдвинул θ
    scored = [r for r in rows if r[1]]
    assert len(scored) <= 20


def test_fixture_sessions_visible_in_history(client: TestClient) -> None:
    sessions = client.get("/api/testing/sessions", headers=CANDIDATE).json()
    assert 1 in {s["id"] for s in sessions}
    res = client.get("/api/testing/sessions/1/result", headers=CANDIDATE).json()
    assert res["category"] == "backend:middle" and res["passed"]


def test_first_pass_above_claimed_shows_assigned_category(client: TestClient) -> None:
    """Первый тест на Middle с θ выше Senior: везде присвоенная Middle, Senior — только совет."""
    state = start(client, CAND_40, "backend", "middle")
    run_to_end(client, CAND_40, state, right=True)
    sid = state["session"]["id"]
    res = client.get(f"/api/testing/sessions/{sid}/result", headers=CAND_40).json()
    assert res["passed"] and res["outcome"] == "suggest_higher"
    assert res["result_grade"] == "middle"
    assert res["category"] == "backend:middle" and res["category_label"] == "Backend · Middle"
    rec = res["recommendation"]
    assert rec["action"] == "offer_higher" and rec["target_grade"] == "senior"
    decision = sql_sync(
        "SELECT engine_state->'decision', result_grade FROM test_sessions WHERE id = :id",
        {"id": sid},
    )[0]
    assert decision[0]["estimated_grade"] == "senior" and decision[0]["granted_grade"] == "middle"
    assert decision[1] == "middle"

    profile = client.get("/api/candidates/me/profile", headers=CAND_40).json()
    assert profile["category"] == "backend:middle"
    assert profile["grade_changed_at"] is None  # первое присвоение — не смена грейда
    grade = client.get("/api/testing/grade", headers=CAND_40).json()
    session = next(s for s in grade["tests"] if s["id"] == sid)
    assert session["result_grade"] == "middle" and session["result_category"] == "backend:middle"
    events = [(h["event"], h["grade_from"], h["grade_to"]) for h in grade["history"]]
    assert ("grade_changed", None, "middle") in events
    assert ("offer_higher", "middle", "senior") in events
    seen = client.get("/api/candidates/40", headers=RECRUITER).json()
    assert seen["category"] == "backend:middle"
    assert [h["category"] for h in seen["test_history"]] == ["backend:middle"]


def test_old_session_with_theta_grade_shows_granted(client: TestClient) -> None:
    """Сессии до исправления хранили в result_grade уровень по θ — показываем присвоенный."""
    state = start(client, CAND_40, "backend", "middle")
    run_to_end(client, CAND_40, state, right=True)
    sid = state["session"]["id"]
    sql_sync("UPDATE test_sessions SET result_grade = 'senior' WHERE id = :id", {"id": sid})
    res = client.get(f"/api/testing/sessions/{sid}/result", headers=CAND_40).json()
    assert res["category"] == "backend:middle"
    seen = client.get("/api/candidates/40", headers=RECRUITER).json()
    assert [h["category"] for h in seen["test_history"]] == ["backend:middle"]


def test_failed_session_keeps_theta_grade(client: TestClient) -> None:
    state = start(client, CAND_40, "backend", "middle")
    run_to_end(client, CAND_40, state, right=False)
    sid = state["session"]["id"]
    res = client.get(f"/api/testing/sessions/{sid}/result", headers=CAND_40).json()
    assert not res["passed"] and res["result_grade"] != "middle"
    seen = client.get("/api/candidates/me/profile", headers=CAND_40).json()
    assert seen["category"] is None


# ---------------------------------------------------------------- админка: банк, утечки, калибровка


def _engine_item(spec: str) -> tuple[int, float, float]:
    client_rows = sql_sync(
        "SELECT id, a, b FROM items WHERE code LIKE :s || '.%'"
        " AND status = 'active' ORDER BY id DESC LIMIT 1",
        {"s": spec},
    )
    return client_rows[0][0], client_rows[0][1], client_rows[0][2]


def _fake_session(candidate_id: int, spec: str) -> int:
    rows = sql_sync(
        "INSERT INTO test_sessions (candidate_id, specialization, target_grade, kind, status,"
        " started_at, finished_at, items_answered, max_items, passed, topic_scores, engine_state)"
        " VALUES (:c, :s, 'junior', 'placement', 'finished', now(), now(), 0, 20, true,"
        " '[]'::jsonb, '{}'::jsonb) RETURNING id",
        {"c": candidate_id, "s": spec},
    )
    return int(rows[0][0])


def _insert_answers(session_id: int, item_id: int, rows: list[tuple[float, bool, int]]) -> None:
    values = ", ".join(
        f"({session_id}, {item_id}, {n}, {n + 1}, now(), now(), {str(ok).lower()}, {ms}, true,"
        f" {theta:.4f})"
        for n, (theta, ok, ms) in enumerate(rows)
    )
    sql_sync(
        "INSERT INTO test_answers (session_id, item_id, seed, position, shown_at, answered_at,"
        " correct, response_time_ms, is_scored, theta_loo) VALUES " + values
    )


def test_admin_bank_on_db(client: TestClient) -> None:
    page = client.get("/api/admin/items", params={"page_size": 200}, headers=ADMIN).json()
    assert page["total"] == 30 + len(registry())
    engine_rows = [i for i in page["items"] if i["id"] > 30]
    assert all(i["variants_count"] >= 40 for i in engine_rows)
    coverage = client.get("/api/admin/items/coverage", headers=ADMIN).json()
    assert sum(c["active"] for c in coverage) >= len(registry())
    item_id = engine_rows[0]["id"]
    detail = client.get(f"/api/admin/items/{item_id}", headers=ADMIN).json()
    previews = detail["preview_variants"]
    assert len(previews) == 3 and len({p["seed"] for p in previews}) == 3
    assert len({p["prompt"] + str(p["options"]) + str(p["code"]) for p in previews}) == 3
    assert all(p["correct_answer"] for p in previews)
    draft = next(i for i in page["items"] if i["status"] == "draft")
    approved = client.post(f"/api/admin/items/{draft['id']}/approve", headers=ADMIN).json()
    assert approved["status"] == "pilot"
    retired = client.post(f"/api/admin/items/{item_id}/retire", headers=ADMIN).json()
    assert retired["status"] == "retired"
    again = client.post(f"/api/admin/items/{item_id}/retire", headers=ADMIN)
    assert again.status_code == 409


def test_leak_detector_retires_template(client: TestClient) -> None:
    client.get("/api/admin/items", headers=ADMIN)  # синхронизация банка
    item_id, _, b = _engine_item("qa")
    sid = _fake_session(5, "qa")
    # слабые кандидаты (θ = b − 3) массово отвечают верно — так выглядит слитая задача
    _insert_answers(sid, item_id, [(b - 3.0, True, 60_000)] * 40)
    scan = client.post("/api/admin/items/leak-scan", headers=ADMIN)
    assert scan.status_code == 200, scan.text
    retired = {r["item_id"]: r for r in scan.json()["retired"]}
    assert item_id in retired and "irt_drift" in retired[item_id]["reasons"]
    row = sql_sync("SELECT status, leak_flag FROM items WHERE id = :id", {"id": item_id})
    status, flag = row[0]
    assert status == "retired" and flag is True
    audit = sql_sync(
        "SELECT count(*) FROM audit_log WHERE action = 'item_leak_retired' AND target_id = :id",
        {"id": item_id},
    )
    assert audit[0][0] == 1
    listed = client.get("/api/admin/items", params={"leak_flag": "true"}, headers=ADMIN).json()
    assert item_id in {i["id"] for i in listed["items"]}


def test_leak_scan_runs_after_nth_session(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.get("/api/admin/items", headers=ADMIN)
    item_id, _, b = _engine_item("devops")
    _insert_answers(_fake_session(5, "devops"), item_id, [(b - 3.0, True, 60_000)] * 40)
    monkeypatch.setattr(get_testing_settings(), "leak_scan_every", 1)
    run_to_end(client, CAND_27, start(client, CAND_27, "backend", "junior"), right=False)
    assert sql_sync("SELECT status FROM items WHERE id = :id", {"id": item_id})[0][0] == "retired"


def test_recalibration_changes_params_and_promotes_pilot(client: TestClient) -> None:
    client.get("/api/admin/items", headers=ADMIN)
    item_id, a, b = _engine_item("data_ml")
    pilot_id, _, _ = _engine_item("mobile")
    sql_sync("UPDATE items SET status = 'pilot' WHERE id = :id", {"id": pilot_id})
    rng = random.Random(7)

    def responses(a_true: float, b_true: float, n: int) -> list[tuple[float, bool, int]]:
        out = []
        for _ in range(n):
            theta = rng.gauss(0, 1)
            p = 1 / (1 + 2.718281828 ** (-a_true * (theta - b_true)))
            out.append((theta, rng.random() < p, 90_000))
        return out

    sid = _fake_session(5, "data_ml")
    _insert_answers(sid, item_id, responses(a, b + 1.0, 300))  # задача оказалась сложнее
    _insert_answers(sid, pilot_id, responses(1.4, 0.2, 300))
    r = client.post("/api/admin/items/recalibrate", params={"min_responses": 50}, headers=ADMIN)
    assert r.status_code == 200, r.text
    body = r.json()
    changes = {c["item_id"]: c for c in body["changes"]}
    assert item_id in changes and changes[item_id]["b_after"] > changes[item_id]["b_before"] + 0.4
    assert body["pilot_promoted"] >= 1
    status, new_b = sql_sync("SELECT status, b FROM items WHERE id = :id", {"id": pilot_id})[0]
    assert status == "active" and abs(new_b - 0.2) < 0.5
    logged = sql_sync(
        "SELECT reason FROM item_params_log WHERE item_id IN (:a, :b) ORDER BY item_id",
        {"a": item_id, "b": pilot_id},
    )
    assert {r[0] for r in logged} == {"recalibration", "activation"}
    detail = client.get(f"/api/admin/items/{item_id}", headers=ADMIN).json()
    assert detail["b"] == changes[item_id]["b_after"] and detail["correct_rate"] is not None

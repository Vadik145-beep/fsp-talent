"""Приглашения на БД [ТЗ 2.1, 2.2; T7.1–T7.8]: видимость до/после принятия, вилка, квота,
машина состояний, журнал, отказ с причиной, истечение, изоляция, подсказка, письма, счётчики.

Каждый тест начинает с чистого сида (перезаливка ~2 с) — тесты не зависят друг от друга
и не меняют данные для других модулей.
"""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.common import fixtures
from app.common.enums import InvitationStatus
from app.invitations.service import TRANSITIONS, can_transition
from app.seed.testkit import reseed_sync, sql_sync
from tests.conftest import CANDIDATE, CANDIDATE_NO_FSP, RECRUITER, RECRUITER_C2, as_role

PRIVATE_KEYS = {"full_name", "email", "phone", "telegram", "min_salary", "fsp_id", "user_id"}


@pytest.fixture(scope="module", autouse=True)
def _restore_seed_after_module() -> Iterator[None]:
    yield
    reseed_sync()


@pytest.fixture(autouse=True)
def _fresh_db() -> None:
    reseed_sync()


@pytest.fixture
def mails(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    sent: list[dict[str, str]] = []

    def fake_send(to: str, subject: str, text: str, html: str | None = None) -> None:
        sent.append({"to": to, "subject": subject, "text": text})

    monkeypatch.setattr("app.core.email.send_email", fake_send)
    return sent


def body(candidate_id: int, **extra: Any) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "description": "Ищем разработчика в команду платёжного шлюза.",
        "salary_from": 200000,
        "salary_to": 300000,
        "contact_method": {"type": "telegram", "value": "@hr_example"},
        **extra,
    }


def private_values(candidate_id: int) -> list[str]:
    cand = fixtures.by_id("candidates", candidate_id)
    assert cand is not None
    return [v for v in (cand["full_name"], cand["email"], cand["phone"], cand["telegram"]) if v]


def invite(client: TestClient, candidate_id: int, headers: dict[str, str] = RECRUITER) -> Any:
    response = client.post("/api/invitations", json=body(candidate_id), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def set_setting(key: str, value: Any) -> None:
    sql_sync(
        "UPDATE platform_settings SET value = CAST(:v AS jsonb) WHERE key = :k",
        {"k": key, "v": json.dumps(value)},
    )


# ---------- машина состояний (без БД) ----------


def test_state_machine_table() -> None:
    s = InvitationStatus
    assert can_transition(s.sent, s.viewed) and can_transition(s.viewed, s.accepted)
    assert can_transition(s.sent, s.accepted) and can_transition(s.viewed, s.withdrawn)
    for final in (s.accepted, s.declined, s.expired, s.withdrawn):
        assert TRANSITIONS[final] == set()
        for target in s:
            assert not can_transition(final, target)
    assert not can_transition(s.viewed, s.sent)


# ---------- сквозной сценарий и видимость ----------


def test_full_flow_visibility_before_and_after_accept(
    client: TestClient, mails: list[dict[str, str]]
) -> None:
    created = invite(client, 1)
    assert created["status"] == "sent"
    assert created["company_name"] and created["recruiter_name"]
    assert created["category"] == "backend:middle"
    assert created["candidate"]["pseudonym"].startswith("Кандидат #")
    assert created["candidate_contacts"] is None and created["recruiter_contacts"] is None

    # до принятия: ни ФИО, ни контактов, ни минимальной зарплаты в ответах рекрутеру
    listed = client.get("/api/invitations", headers=RECRUITER).json()
    for item in (
        client.get(f"/api/invitations/{created['id']}", headers=RECRUITER).json(),
        next(i for i in listed if i["id"] == created["id"]),
    ):
        raw = json.dumps(item, ensure_ascii=False)
        for value in private_values(1):
            assert value not in raw
        assert '"min_salary"' not in raw
    detail = client.get(f"/api/invitations/{created['id']}", headers=RECRUITER).json()
    assert not PRIVATE_KEYS & set(detail["candidate"])
    assert detail["status"] == "sent", "открытие рекрутером не меняет статус"

    # кандидат видит условия и способ связи до общения, но не сами контакты рекрутера
    mine = client.get(f"/api/invitations/{created['id']}", headers=CANDIDATE).json()
    assert mine["status"] == "viewed" and mine["viewed_at"]
    assert mine["salary_from"] == 200000 and mine["salary_to"] == 300000
    assert mine["contact_method"] == {"type": "telegram", "value": None}
    assert mine["recruiter_contacts"] is None and mine["candidate"] is None

    accepted = client.post(f"/api/invitations/{created['id']}/accept", headers=CANDIDATE).json()
    assert accepted["status"] == "accepted" and accepted["responded_at"]
    assert accepted["recruiter_contacts"]["email"] == "recruiter@example.com"
    assert accepted["contact_method"] == {"type": "telegram", "value": "@hr_example"}

    after = client.get(f"/api/invitations/{created['id']}", headers=RECRUITER).json()
    assert after["candidate_contacts"]["full_name"] == private_values(1)[0]
    assert [e["type"] for e in after["events"]] == [
        "created",
        "viewed",
        "accepted",
        "contacts_revealed",
    ]
    audit = sql_sync(
        "SELECT action, actor_role FROM audit_log WHERE target_type = 'invitation' "
        "AND target_id = :id AND at > now() - interval '10 minutes'",
        {"id": created["id"]},
    )
    assert [tuple(r) for r in audit] == [("contacts_revealed", "candidate")]

    # письма: кандидату о приглашении, рекрутеру о принятии
    assert mails[0]["to"] == fixtures.by_id("candidates", 1)["email"]  # type: ignore[index]
    assert "Новое приглашение" in mails[0]["subject"]
    assert mails[1]["to"] == "recruiter@example.com" and "принял" in mails[1]["subject"]


def test_privacy_settings_respected_in_card(client: TestClient) -> None:
    # кандидат 17 (qa:middle) скрыл город и стаж
    created = invite(client, 17)
    card = created["candidate"]
    assert card["city"] is None and card["experience_years"] is None
    assert card["links"] is None


def test_candidate_sees_recruiter_contacts_only_after_accept(client: TestClient) -> None:
    created = invite(client, 1)
    listed = client.get("/api/invitations", headers=CANDIDATE).json()
    new = next(i for i in listed if i["id"] == created["id"])
    assert new["recruiter_contacts"] is None
    for inv in listed:
        assert (inv["recruiter_contacts"] is not None) == (inv["status"] == "accepted")


def test_contact_value_and_task_text_hidden_from_candidate_until_accept(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/invitations", json=body(1, task_text="Как ускорить доставку?"), headers=RECRUITER
    ).json()
    assert created["contact_method"]["value"] == "@hr_example"
    assert created["task_text"] == "Как ускорить доставку?" and created["has_task_text"]
    url = f"/api/invitations/{created['id']}"
    for before in (
        client.get(url, headers=CANDIDATE).json(),
        next(
            i
            for i in client.get("/api/invitations", headers=CANDIDATE).json()
            if i["id"] == created["id"]
        ),
    ):
        assert before["contact_method"] == {"type": "telegram", "value": None}
        assert before["task_text"] is None and before["has_task_text"] is True
        assert "@hr_example" not in json.dumps(before, ensure_ascii=False)
    accepted = client.post(f"{url}/accept", headers=CANDIDATE).json()
    assert accepted["contact_method"]["value"] == "@hr_example"
    assert accepted["task_text"] == "Как ускорить доставку?"


def test_task_text_stays_hidden_after_decline(client: TestClient) -> None:
    created = client.post(
        "/api/invitations", json=body(1, task_text="Вопрос"), headers=RECRUITER
    ).json()
    url = f"/api/invitations/{created['id']}"
    declined = client.post(f"{url}/decline", json={"reason": "salary_too_low"}, headers=CANDIDATE)
    assert declined.status_code == 200, declined.text
    assert declined.json()["task_text"] is None
    assert declined.json()["contact_method"]["value"] is None
    recruiter_view = client.get(url, headers=RECRUITER).json()
    assert recruiter_view["task_text"] == "Вопрос"


# ---------- создание: вилка, ожидания, квота, повтор ----------


def test_salary_range_required_and_ordered(client: TestClient) -> None:
    no_to = {k: v for k, v in body(1).items() if k != "salary_to"}
    assert client.post("/api/invitations", json=no_to, headers=RECRUITER).status_code == 422
    bad = client.post(
        "/api/invitations", json=body(1, salary_from=300000, salary_to=200000), headers=RECRUITER
    )
    assert bad.status_code == 422
    assert bad.json()["details"]["errors"][0]["type"] == "salary_range_invalid"


def test_below_expectations_hides_amount(client: TestClient) -> None:
    # минимум кандидата 1 — 180 000
    response = client.post(
        "/api/invitations", json=body(1, salary_from=100000, salary_to=179999), headers=RECRUITER
    )
    assert response.status_code == 422
    error = response.json()
    assert error["code"] == "salary_below_expectations" and error["details"] == {}
    assert "180" not in response.text
    ok = client.post(
        "/api/invitations", json=body(1, salary_from=150000, salary_to=180000), headers=RECRUITER
    )
    assert ok.status_code == 201, "максимум вилки = минимуму кандидата — можно"


def test_quota_limits_active_invitations(client: TestClient) -> None:
    used = client.get("/api/invitations/quota", headers=RECRUITER).json()["used"]
    set_setting("invitation_quota", used + 1)
    quota = client.get("/api/invitations/quota", headers=RECRUITER).json()
    assert quota == {"limit": used + 1, "used": used, "left": 1, "hint": None}
    first = invite(client, 10)
    full = client.post("/api/invitations", json=body(18), headers=RECRUITER)
    assert full.status_code == 409 and full.json()["code"] == "quota_exceeded"
    assert full.json()["details"] == {"limit": used + 1, "used": used + 1}
    quota = client.get("/api/invitations/quota", headers=RECRUITER).json()
    assert quota["left"] == 0 and quota["hint"]
    # отзыв освобождает место
    client.post(f"/api/invitations/{first['id']}/withdraw", headers=RECRUITER)
    assert client.post("/api/invitations", json=body(18), headers=RECRUITER).status_code == 201


def test_one_active_invitation_per_company(client: TestClient) -> None:
    created = invite(client, 10)
    again = client.post("/api/invitations", json=body(10), headers=RECRUITER)
    assert again.status_code == 409 and again.json()["code"] == "already_invited"
    assert again.json()["details"] == {"invitation_id": created["id"]}
    # другая компания может пригласить того же кандидата
    invite(client, 10, RECRUITER_C2)
    # после отзыва — снова можно
    client.post(f"/api/invitations/{created['id']}/withdraw", headers=RECRUITER)
    invite(client, 10)


def test_hidden_candidate_cannot_be_invited(client: TestClient) -> None:
    # 37 — отозвал согласие, 38 — пауза поиска, 39 — без теста
    for cid in (37, 38, 39):
        response = client.post("/api/invitations", json=body(cid), headers=RECRUITER)
        assert response.status_code == 404, cid
    sql_sync(
        "UPDATE users SET blocked = true "
        "WHERE id = (SELECT user_id FROM candidate_profiles WHERE id = 10)"
    )
    assert client.post("/api/invitations", json=body(10), headers=RECRUITER).status_code == 404


def test_need_and_vacancy_must_belong_to_company(client: TestClient) -> None:
    other_need = next(n for n in fixtures.load("needs") if n["company_id"] != 1)
    response = client.post(
        "/api/invitations", json=body(10, need_id=other_need["id"]), headers=RECRUITER
    )
    assert response.status_code == 404
    own_need = next(n for n in fixtures.load("needs") if n["company_id"] == 1)
    created = client.post(
        "/api/invitations",
        json=body(10, need_id=own_need["id"], task_text="Задача"),
        headers=RECRUITER,
    ).json()
    assert created["need_id"] == own_need["id"] and created["task_text"] == "Задача"
    assert created["vacancy_id"] is None


# ---------- статусы ----------


def test_invalid_transitions_return_409(client: TestClient) -> None:
    created = invite(client, 10)
    cand10 = as_role("candidate", fixtures.by_id("candidates", 10)["user_id"])  # type: ignore[index]
    assert (
        client.post(f"/api/invitations/{created['id']}/accept", headers=cand10).status_code == 200
    )
    for path, headers in (
        ("accept", cand10),
        ("withdraw", RECRUITER),
    ):
        response = client.post(f"/api/invitations/{created['id']}/{path}", headers=headers)
        assert response.status_code == 409, path
        assert response.json()["code"] == "invalid_transition"
    declined = client.post(
        f"/api/invitations/{created['id']}/decline",
        json={"reason": "salary_too_low"},
        headers=cand10,
    )
    assert declined.status_code == 409
    # роли: рекрутер не принимает, кандидат не отзывает
    other = invite(client, 18)
    assert (
        client.post(f"/api/invitations/{other['id']}/accept", headers=RECRUITER).status_code == 403
    )
    assert (
        client.post(f"/api/invitations/{other['id']}/withdraw", headers=cand10).status_code == 403
    )


def test_withdrawn_cannot_be_accepted(client: TestClient) -> None:
    created = invite(client, 1)
    withdrawn = client.post(f"/api/invitations/{created['id']}/withdraw", headers=RECRUITER).json()
    assert withdrawn["status"] == "withdrawn" and withdrawn["withdrawn_at"]
    response = client.post(f"/api/invitations/{created['id']}/accept", headers=CANDIDATE)
    assert response.status_code == 409
    assert response.json()["details"] == {"from": "withdrawn", "to": "accepted"}


def test_decline_with_reason(client: TestClient, mails: list[dict[str, str]]) -> None:
    created = invite(client, 1)
    no_comment = client.post(
        f"/api/invitations/{created['id']}/decline", json={"reason": "other"}, headers=CANDIDATE
    )
    assert no_comment.status_code == 422
    bad_reason = client.post(
        f"/api/invitations/{created['id']}/decline", json={"reason": "nope"}, headers=CANDIDATE
    )
    assert bad_reason.status_code == 422
    declined = client.post(
        f"/api/invitations/{created['id']}/decline",
        json={"reason": "salary_too_low", "comment": "Рассматриваю выше"},
        headers=CANDIDATE,
    ).json()
    assert declined["status"] == "declined" and declined["recruiter_contacts"] is None
    seen = client.get(f"/api/invitations/{created['id']}", headers=RECRUITER).json()
    assert seen["decline_reason"] == "salary_too_low"
    assert seen["decline_reason_label"] == "Мала зарплата"
    assert seen["decline_comment"] == "Рассматриваю выше"
    assert seen["candidate_contacts"] is None
    assert [e["type"] for e in seen["events"]] == ["created", "viewed", "declined"]
    assert mails[-1]["to"] == "recruiter@example.com"
    assert "Мала зарплата" in mails[-1]["text"]


def test_expired_lazily_on_read(client: TestClient) -> None:
    created = invite(client, 1)
    expires = created["expires_at"][:10]
    assert expires > created["created_at"][:10], "срок из настроек (7 дней)"
    sql_sync(
        "UPDATE invitations SET expires_at = now() - interval '1 minute' WHERE id = :id",
        {"id": created["id"]},
    )
    listed = client.get("/api/invitations", headers=RECRUITER).json()
    assert next(i for i in listed if i["id"] == created["id"])["status"] == "expired"
    detail = client.get(f"/api/invitations/{created['id']}", headers=CANDIDATE).json()
    assert detail["status"] == "expired"
    expired = [e for e in detail["events"] if e["type"] == "expired"]
    assert len(expired) == 1 and expired[0]["actor_role"] is None
    assert (
        client.post(f"/api/invitations/{created['id']}/accept", headers=CANDIDATE).status_code
        == 409
    )


def test_ttl_from_settings(client: TestClient) -> None:
    set_setting("invitation_ttl_days", 3)
    created = invite(client, 1)
    rows = sql_sync(
        "SELECT round(extract(epoch FROM expires_at - created_at) / 86400) FROM invitations "
        "WHERE id = :id",
        {"id": created["id"]},
    )
    assert int(rows[0][0]) == 3


# ---------- изоляция ----------


def test_isolation_foreign_invitations_are_404(client: TestClient) -> None:
    created = invite(client, 1)
    assert (
        client.get(f"/api/invitations/{created['id']}", headers=CANDIDATE_NO_FSP).status_code == 404
    )
    assert client.get(f"/api/invitations/{created['id']}", headers=RECRUITER_C2).status_code == 404
    assert (
        client.post(f"/api/invitations/{created['id']}/withdraw", headers=RECRUITER_C2).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/invitations/{created['id']}/accept", headers=CANDIDATE_NO_FSP
        ).status_code
        == 404
    )
    assert {
        i["company_id"] for i in client.get("/api/invitations", headers=RECRUITER_C2).json()
    } == {2}
    ids = {i["id"] for i in client.get("/api/invitations", headers=CANDIDATE_NO_FSP).json()}
    assert created["id"] not in ids
    assert client.get("/api/invitations/999999", headers=RECRUITER).status_code == 404


def test_status_filter(client: TestClient) -> None:
    items = client.get("/api/invitations", params={"status": "accepted"}, headers=RECRUITER).json()
    assert items and {i["status"] for i in items} == {"accepted"}


# ---------- счётчики ----------


def test_counters(client: TestClient) -> None:
    before = client.get("/api/invitations/counters", headers=CANDIDATE).json()
    created = invite(client, 1)
    after = client.get("/api/invitations/counters", headers=CANDIDATE).json()
    assert after["new"] == before["new"] + 1 and after["active"] == before["active"] + 1
    rec_before = client.get("/api/invitations/counters", headers=RECRUITER).json()
    client.get(f"/api/invitations/{created['id']}", headers=CANDIDATE)  # просмотр
    assert client.get("/api/invitations/counters", headers=CANDIDATE).json()["new"] == before["new"]
    client.post(f"/api/invitations/{created['id']}/accept", headers=CANDIDATE)
    rec_after = client.get("/api/invitations/counters", headers=RECRUITER).json()
    assert rec_after["new"] == rec_before["new"] + 1
    client.get(f"/api/invitations/{created['id']}", headers=RECRUITER)  # рекрутер открыл
    assert (
        client.get("/api/invitations/counters", headers=RECRUITER).json()["new"]
        == rec_before["new"]
    )


# ---------- рыночная подсказка ----------


def test_market_hint_by_candidate_expectations(client: TestClient) -> None:
    # backend:middle: принятых < 3, минимумы кандидатов — 3 → оценка по ожиданиям
    hint = client.get(
        "/api/invitations/market-hint",
        params={"category": "backend:middle", "salary_from": 200000, "salary_to": 260000},
        headers=RECRUITER,
    ).json()
    assert hint["median_accepted_from"] and hint["median_accepted_from"] % 10000 == 0
    assert hint["sample_size"] >= 3
    assert 0.05 <= hint["acceptance_probability"] <= 0.95
    assert "обычно принимают от" in hint["message"]
    low = client.get(
        "/api/invitations/market-hint",
        params={"category": "backend:middle", "salary_to": 50000},
        headers=RECRUITER,
    ).json()
    assert low["acceptance_probability"] < hint["acceptance_probability"]


def test_market_hint_by_accepted_invitations(client: TestClient) -> None:
    for a, b in [(200000, 250000), (220000, 260000), (240000, 300000)]:
        sql_sync(
            "INSERT INTO invitations (candidate_id, recruiter_id, company_id, category, "
            "description, salary_from, salary_to, contact_type, contact_value, status, "
            "expires_at, created_at) VALUES (:c, 1, 1, 'devops:middle', 'x', :a, :b, 'email', "
            "'x@example.com', 'accepted', now(), now())",
            {"c": 7, "a": a, "b": b},
        )
    hint = client.get(
        "/api/invitations/market-hint", params={"category": "devops:middle"}, headers=RECRUITER
    ).json()
    assert hint["median_accepted_from"] == 220000 and hint["median_accepted_to"] == 260000
    assert hint["sample_size"] == 3
    assert hint["acceptance_probability"] is None, "без введённой вилки вероятности нет"


def test_market_hint_hidden_for_small_sample(client: TestClient) -> None:
    # в демо-базе в каждой категории не меньше 6 кандидатов — малую выборку делаем сами:
    # ожидания кандидатов категории неизвестны, принятых приглашений нет
    sql_sync("UPDATE candidate_profiles SET min_salary = NULL WHERE category = 'qa:middle'")
    hint = client.get(
        "/api/invitations/market-hint",
        params={"category": "qa:middle", "salary_to": 200000},
        headers=RECRUITER,
    ).json()
    assert hint["sample_size"] < 3
    assert hint["median_accepted_from"] is None and hint["acceptance_probability"] is None
    assert "мало данных" in hint["message"]
    assert (
        client.get(
            "/api/invitations/market-hint", params={"category": "nope:x"}, headers=RECRUITER
        ).status_code
        == 404
    )

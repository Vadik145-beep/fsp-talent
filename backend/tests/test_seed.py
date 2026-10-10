"""Загрузчик демо-данных: все фикстуры в таблицах, id совпадают, идемпотентность, --reset."""

from collections.abc import Iterator

import pytest

from app.auth.passwords import verify_password
from app.common import fixtures
from app.seed import loader
from app.seed.__main__ import main as seed_cli
from app.seed.settings import get_seed_settings
from app.seed.testkit import reseed_sync, seed_sync, sql_sync

# фикстура → (таблица, колонка id)
ID_TABLES = {
    "users": ("users", "id"),
    "consents": ("consents", "id"),
    "companies": ("companies", "id"),
    "recruiters": ("recruiters", "id"),
    "candidates": ("candidate_profiles", "id"),
    "fsp_achievements": ("fsp_achievements", "id"),
    "needs": ("needs", "id"),
    "vacancies": ("vacancies", "id"),
    "applications": ("applications", "id"),
    "items": ("items", "id"),
    "test_sessions": ("test_sessions", "id"),
    "grade_history": ("grade_history", "id"),
    "invitations": ("invitations", "id"),
    "invitation_events": ("invitation_events", "id"),
    "regular_tasks": ("regular_tasks", "id"),
    "task_submissions": ("task_submissions", "id"),
    "reports": ("reports", "id"),
    "audit_log": ("audit_log", "id"),
    "specializations": ("specializations", "code"),
    "grades": ("grades", "code"),
    "categories": ("categories", "code"),
    "topics": ("topics", "code"),
    "skills": ("skills", "code"),
}


@pytest.fixture(autouse=True, scope="module")
def _fresh_db() -> Iterator[None]:
    reseed_sync()
    yield
    reseed_sync()


def _ids(table: str, column: str) -> set[object]:
    return {row[0] for row in sql_sync(f"SELECT {column} FROM {table}")}


def test_every_fixture_with_table_is_loaded_with_same_ids() -> None:
    for name, (table, column) in ID_TABLES.items():
        expected = {r["id"] for r in fixtures.load(name)}
        assert expected, name
        assert _ids(table, column) == expected, name
    # производные таблицы
    stack_rows = sum(len(c["stack"]) for c in fixtures.load("candidates"))
    assert sql_sync("SELECT count(*) FROM candidate_skills")[0][0] == stack_rows
    linked = {c["fsp_id"] for c in fixtures.load("candidates") if c["fsp_id"]}
    assert {r[0] for r in sql_sync("SELECT fsp_id FROM fsp_links")} == linked
    settings = fixtures.load("platform_settings")[0]
    keys = {r[0] for r in sql_sync("SELECT key FROM platform_settings")}
    assert keys == set(settings) - {"id"}
    # все шаги загрузчика покрывают все таблицы схемы
    assert {t for t, _ in loader.STEPS} >= {t for t, _ in ID_TABLES.values()}


def test_fixture_fields_are_mapped() -> None:
    cand = sql_sync(
        "SELECT publication_consent, fsp_score, job_search_paused FROM candidate_profiles "
        "WHERE id = 37"
    )[0]
    assert cand[0] is False  # 37 отозвал согласие на публикацию
    inv = sql_sync("SELECT contact_type, contact_value FROM invitations WHERE id = 1")[0]
    src = fixtures.by_id("invitations", 1)
    assert src is not None
    assert (inv[0], inv[1]) == (src["contact_method"]["type"], src["contact_method"]["value"])
    # actor_user_id событий восстановлен по роли
    assert (
        sql_sync(
            "SELECT count(*) FROM invitation_events WHERE actor_role = 'recruiter' "
            "AND actor_user_id IS NULL"
        )[0][0]
        == 0
    )
    order = [
        r[0]
        for r in sql_sync(
            "SELECT skill_code FROM candidate_skills WHERE candidate_id = 1 ORDER BY position"
        )
    ]
    assert order == fixtures.by_id("candidates", 1)["stack"]  # type: ignore[index]


def test_second_run_inserts_nothing_and_keeps_changes() -> None:
    before = {t: sql_sync(f"SELECT count(*) FROM {t}")[0][0] for t, _ in loader.STEPS}
    sql_sync("UPDATE candidate_profiles SET city = 'Тестоград' WHERE id = 2")
    report = seed_sync()
    assert report.inserted == 0
    after = {t: sql_sync(f"SELECT count(*) FROM {t}")[0][0] for t, _ in loader.STEPS}
    assert after == before
    # без --reset изменения, сделанные через API, не перетираются
    assert sql_sync("SELECT city FROM candidate_profiles WHERE id = 2")[0][0] == "Тестоград"


def test_reset_restores_fixture_state() -> None:
    sql_sync("UPDATE candidate_profiles SET city = 'Тестоград' WHERE id = 2")
    sql_sync("DELETE FROM audit_log WHERE id > 40")
    report = reseed_sync()
    assert report.reset and report.inserted > 1000
    expected_city = fixtures.by_id("candidates", 2)["city"]  # type: ignore[index]
    assert sql_sync("SELECT city FROM candidate_profiles WHERE id = 2")[0][0] == expected_city
    assert sql_sync("SELECT count(*) FROM audit_log")[0][0] == len(fixtures.load("audit_log"))


def test_sequences_are_shifted_after_explicit_ids() -> None:
    max_id = max(r["id"] for r in fixtures.load("audit_log"))
    new_id = sql_sync(
        "INSERT INTO audit_log (action, target_type, summary, details) "
        "VALUES ('test', 'test', '', '{}'::jsonb) RETURNING id"
    )[0][0]
    assert new_id == max_id + 1
    max_user = max(r["id"] for r in fixtures.load("users"))
    next_user = sql_sync("SELECT nextval(pg_get_serial_sequence('users', 'id'))")[0][0]
    assert next_user == max_user + 1


def test_demo_passwords_are_hashed() -> None:
    demo = {a["user_id"]: a["password"] for a in fixtures.load("demo_accounts")}
    rows = dict(sql_sync("SELECT id, password_hash FROM users"))
    for user_id, password in demo.items():
        assert rows[user_id] and rows[user_id] != password
        assert verify_password(password, rows[user_id])
        assert not verify_password("wrong-password", rows[user_id])
    assert all(rows[u] is None for u in rows if u not in demo)


def test_cli_reset(capsys: pytest.CaptureFixture[str]) -> None:
    assert seed_cli(["--reset"]) == 0
    out = capsys.readouterr().out
    assert "candidate_profiles" in out and "после очистки" in out


def test_seed_on_startup_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    get_seed_settings.cache_clear()
    monkeypatch.delenv("SEED_ON_STARTUP", raising=False)
    assert asyncio.run(loader.seed_on_startup()) is None
    monkeypatch.setenv("SEED_ON_STARTUP", "true")
    get_seed_settings.cache_clear()
    report = asyncio.run(loader.seed_on_startup())
    assert report is not None and report.inserted == 0
    get_seed_settings.cache_clear()


# ---------- повторная загрузка не задваивает данные, заменённые через API ----------

ACH_INSERT = (
    "INSERT INTO fsp_achievements (fsp_id, external_id, competition, discipline, level, date,"
    " place, verified, synced_at) VALUES (:f, :ext, 'Кубок реестра', 'product', 'national',"
    " DATE '2026-05-01', :place, true, now())"
)


def _achievements(fsp_id: str) -> list[tuple[str, int | None]]:
    rows = sql_sync(
        "SELECT external_id, place FROM fsp_achievements WHERE fsp_id = :f ORDER BY external_id",
        {"f": fsp_id},
    )
    return [(r[0], r[1]) for r in rows]


def _snapshot(candidate_id: int) -> tuple[float | None, list[str]]:
    score, badges = sql_sync(
        "SELECT fsp_score, fsp_badges FROM candidate_profiles WHERE id = :id", {"id": candidate_id}
    )[0]
    return score, [b["id"] for b in badges]


def test_reseed_after_registry_refresh_does_not_duplicate_achievements() -> None:
    """«Обновить из реестра» заменяет достижения новыми строками (другие id и external_id);
    рестарт с SEED_ON_STARTUP не должен вернуть рядом сидовые копии (было 14 вместо 7)."""
    reseed_sync()
    seed_count = len(_achievements("FSP-000001"))
    assert seed_count == 7
    # как FspRepository.replace_achievements: удалить и вставить данные реестра
    sql_sync("DELETE FROM fsp_achievements WHERE fsp_id = 'FSP-000001'")
    for n in range(1, seed_count + 1):
        sql_sync(ACH_INSERT, {"f": "FSP-000001", "ext": f"ACH-000001-{n:02d}", "place": 2})
    registry = _achievements("FSP-000001")
    report = seed_sync()
    assert report.tables["fsp_achievements"][1] == 0
    assert _achievements("FSP-000001") == registry
    reseed_sync()


def test_reseed_heals_old_duplicates_and_recomputes_snapshot() -> None:
    """База, уже задвоенная старым загрузчиком: сидовые копии рядом с данными реестра
    удаляются, ФСП-скор и бейджи кандидата пересчитываются по оставшимся достижениям."""
    from app.candidates.fsp_score import fsp_badges, fsp_score

    reseed_sync()
    # кандидат 1 — FSP-000001: к 7 сидовым добавились 2 записи реестра
    for n in (1, 2):
        sql_sync(ACH_INSERT, {"f": "FSP-000001", "ext": f"ACH-000001-{n:02d}", "place": 1})
    assert len(_achievements("FSP-000001")) == 9
    seed_sync()
    assert _achievements("FSP-000001") == [("ACH-000001-01", 1), ("ACH-000001-02", 1)]
    achs = [
        {"date": d, "level": level, "place": place}
        for d, level, place in sql_sync(
            "SELECT date, level, place FROM fsp_achievements WHERE fsp_id = 'FSP-000001'"
        )
    ]
    score, badges = _snapshot(1)
    assert score == fsp_score(achs)
    assert badges == [b["id"] for b in fsp_badges(achs)]
    # у остальных кандидатов ничего не тронуто
    assert len(_achievements("FSP-000002")) == sum(
        1 for a in fixtures.load("fsp_achievements") if a["fsp_id"] == "FSP-000002"
    )
    reseed_sync()


def test_reseed_does_not_bring_back_unlinked_fsp_or_removed_skills() -> None:
    reseed_sync()
    # кандидат 2 отвязал ФСП ID (как FspService.unlink) и убрал технологию из стека
    sql_sync("DELETE FROM fsp_achievements WHERE fsp_id = 'FSP-000002'")
    sql_sync("DELETE FROM fsp_links WHERE candidate_id = 2")
    removed = sql_sync(
        "SELECT skill_code FROM candidate_skills WHERE candidate_id = 2 ORDER BY position LIMIT 1"
    )[0][0]
    sql_sync(
        "DELETE FROM candidate_skills WHERE candidate_id = 2 AND skill_code = :s", {"s": removed}
    )
    seed_sync()
    assert sql_sync("SELECT count(*) FROM fsp_links WHERE candidate_id = 2")[0][0] == 0
    skills = {
        r[0] for r in sql_sync("SELECT skill_code FROM candidate_skills WHERE candidate_id = 2")
    }
    assert removed not in skills
    reseed_sync()

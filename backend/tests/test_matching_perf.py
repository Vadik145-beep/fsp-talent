"""Нагрузка на 1000 синтетических кандидатов [T6.5]: банк кандидатов с фильтрами отвечает
< 500 мс, подборка не делает N+1 (число SQL-запросов не зависит от числа кандидатов).

Кандидаты создаются SQL-запросом в базе тестов и удаляются перезаливкой сида после модуля.
Половина синтетики — в категории `backend:middle` (подборка по потребности 1 идёт по ~500).
"""

import time
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core.db import get_engine
from app.seed.testkit import reseed_sync, sql_sync
from tests.conftest import RECRUITER

N = 1000
BANK_LIMIT_MS = 500

SPECS = "ARRAY['backend','frontend','mobile','data_ml','qa','devops']"
GRADES = "ARRAY['intern','junior','middle','senior']"
CITIES = "ARRAY['Москва','Казань','Самара','Пермь','Томск']"
FORMATS = (
    "CASE g % 4 WHEN 0 THEN ARRAY['remote'] WHEN 1 THEN ARRAY['remote', 'hybrid'] "
    "WHEN 2 THEN ARRAY['office'] ELSE ARRAY['hybrid', 'office'] END"
)

INSERT_USERS = """
INSERT INTO users (email, role, full_name, email_verified, blocked)
SELECT 'synthetic' || g || '@example.com', 'candidate', 'Синтетический Кандидат ' || g, true, false
FROM generate_series(1, :n) AS g
"""

INSERT_PROFILES = f"""
WITH src AS (
    SELECT u.id AS user_id, split_part(split_part(u.email, '@', 1), 'synthetic', 2)::int AS g
    FROM users u WHERE u.email LIKE 'synthetic%@example.com'
), cat AS (
    SELECT user_id, g,
        CASE WHEN g % 2 = 0 THEN 'backend' ELSE ({SPECS})[1 + (g / 2) % 6] END AS spec,
        CASE WHEN g % 2 = 0 THEN 'middle' ELSE ({GRADES})[1 + (g / 12) % 4] END AS grade
    FROM src
)
INSERT INTO candidate_profiles (
    user_id, pseudonym, phone, city, work_formats, specialization, grade, category, theta,
    topic_scores, roles_in_team, experience_years, soft_skills, about, links, min_salary,
    privacy, job_search_paused, publication_consent, fsp_badges, freshness
)
SELECT user_id, 'Кандидат #S' || g, '+7 900 000-' || lpad(g::text, 4, '0'),
    ({CITIES})[1 + g % 5],
    ({FORMATS})::varchar[],
    spec, grade, spec || ':' || grade,
    ((g * 37) % 400) / 100.0 - 2,
    '[]'::jsonb, '{{}}', (g % 10)::float, '{{}}', '', '[]'::jsonb,
    80000 + (g * 7919) % 300000,
    '{{"show_city": true, "show_experience": true, "show_links": false,
       "show_fsp_achievements": true}}'::jsonb,
    false, g % 50 <> 0, '[]'::jsonb, ((g * 13) % 100) / 100.0
FROM cat
"""

INSERT_SKILLS = """
INSERT INTO candidate_skills (candidate_id, skill_code, position)
SELECT p.id, s.code, s.pos
FROM candidate_profiles p
JOIN LATERAL (
    VALUES ('postgresql', 0, true), ('python', 1, p.id % 2 = 0), ('docker', 2, p.id % 3 = 0),
           ('kafka', 3, p.id % 5 = 0), ('go', 4, p.id % 7 = 0)
) AS s(code, pos, keep) ON s.keep
WHERE p.pseudonym LIKE 'Кандидат #S%'
"""


@pytest.fixture(scope="module", autouse=True)
def synthetic() -> Iterator[None]:
    reseed_sync()
    sql_sync(INSERT_USERS, {"n": N})
    sql_sync(INSERT_PROFILES)
    sql_sync(INSERT_SKILLS)
    yield
    reseed_sync()


def timed(client: TestClient, url: str, params: dict[str, Any], runs: int = 7) -> float:
    """Лучшее время ответа из нескольких прогонов, мс (после прогрева).

    Берём минимум, а не медиану: на общей машине разработки параллельно идут чужие тесты
    и отдельные замеры прыгают в разы; минимум показывает время самого запроса.
    """
    client.get(url, params=params, headers=RECRUITER)
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        response = client.get(url, params=params, headers=RECRUITER)
        samples.append((time.perf_counter() - start) * 1000)
        assert response.status_code == 200, response.text
    return min(samples)


def test_synthetic_loaded(client: TestClient) -> None:
    total = client.get("/api/candidates", headers=RECRUITER).json()["total"]
    # 2 % синтетики без согласия на публикацию — их в банке нет
    assert total >= N - N // 50


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"specialization": "backend", "sort": "fsp"},
        {"grade": "middle", "skills": ["python", "postgresql"], "sort": "freshness"},
        {"category": "backend:middle", "has_fsp": False, "page": 3, "page_size": 50},
        {"skills": ["kafka"], "work_format": "remote", "city": "Казань", "sort": "recent"},
    ],
)
def test_bank_search_under_500ms(client: TestClient, params: dict[str, Any]) -> None:
    ms = timed(client, "/api/candidates", params)
    print(f"bank {params}: {ms:.0f} мс")
    assert ms < BANK_LIMIT_MS, f"{params}: {ms:.0f} мс"


def test_bank_filters_and_pagination(client: TestClient) -> None:
    params = {"grade": "middle", "skills": ["python", "postgresql"], "page_size": 100}
    page1 = client.get("/api/candidates", params=params, headers=RECRUITER).json()
    page2 = client.get("/api/candidates", params={**params, "page": 2}, headers=RECRUITER).json()
    assert page1["total"] > 100
    assert not {c["id"] for c in page1["items"]} & {c["id"] for c in page2["items"]}
    for card in page1["items"]:
        assert card["grade"] == "middle" and {"python", "postgresql"} <= set(card["stack"])
    thetas = [c["theta"] for c in page1["items"]]
    assert thetas == sorted(thetas, reverse=True)


def count_queries(client: TestClient, url: str) -> int:
    statements: list[str] = []

    def on_execute(*args: Any) -> None:
        statements.append(str(args[2]))

    engine = get_engine().sync_engine
    event.listen(engine, "before_cursor_execute", on_execute)
    try:
        assert client.get(url, headers=RECRUITER).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", on_execute)
    return len(statements)


def test_matching_without_n_plus_one(client: TestClient) -> None:
    result = client.get("/api/matching/needs/1/candidates", headers=RECRUITER).json()
    assert result["total"] >= 400
    big = count_queries(client, "/api/matching/needs/1/candidates")
    small = count_queries(client, "/api/matching/needs/1/candidates?category=backend:junior")
    print(f"SQL-запросов: категория ~{result['total']} кандидатов — {big}, маленькая — {small}")
    # число запросов не зависит от числа кандидатов (пакетные выборки, без N+1)
    assert big == small
    assert big <= 15
    ms = timed(client, "/api/matching/needs/1/candidates", {}, runs=3)
    print(f"подборка по {result['total']} кандидатам: {ms:.0f} мс")
    assert ms < 3000

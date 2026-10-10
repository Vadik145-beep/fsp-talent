"""Загрузчик демо-данных: все `data/seed/*.json` → таблицы БД.

Правила:
- id из фикстур сохраняются (модули на фикстурах и на БД ссылаются на одни и те же записи),
  после вставки последовательности (sequence) сдвигаются за максимальный id;
- загрузка идемпотентна: `INSERT … ON CONFLICT DO NOTHING`, повторный запуск ничего не дублирует
  и не перетирает изменения, сделанные через API;
- `reset=True` — очистить все таблицы (кроме справочника ролей) и залить заново;
- пароли демо-учёток (`demo_accounts.json`) хешируются `hash_password`,
  у остальных пользователей пароля нет (вход только после сброса пароля).

Поля фикстур, которых нет в таблицах (подписи, счётчики, вычисляемые поля), отбрасываются;
сопоставление описано в функциях `_rows_*`.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import Integer, Table, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401  — регистрирует все таблицы в metadata
from app.auth.passwords import hash_password
from app.catalog.clock import now_msk, parse_dt
from app.core.config import get_settings
from app.core.db import Base
from app.seed.settings import get_seed_settings

Record = dict[str, Any]

ROLES: list[Record] = [
    {"code": "candidate", "label": "Соискатель"},
    {"code": "recruiter", "label": "Рекрутер"},
    {"code": "admin", "label": "Администратор"},
]

# Таблицы, которые reset не очищает (заполняются миграцией и нужны всегда)
KEEP_ON_RESET = {"roles"}

CHUNK = 500


def read_fixture(seed_dir: Path, name: str) -> list[Record]:
    path = seed_dir / f"{name}.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Фикстура {path} должна быть массивом объектов")
    return data


@dataclass
class SeedContext:
    seed_dir: Path
    _cache: dict[str, list[Record]] = field(default_factory=dict)

    def get(self, name: str) -> list[Record]:
        if name not in self._cache:
            self._cache[name] = read_fixture(self.seed_dir, name)
        return self._cache[name]

    def by_id(self, name: str) -> dict[Any, Record]:
        return {r["id"]: r for r in self.get(name)}


def _dt(value: Any) -> Any:
    return parse_dt(value) if isinstance(value, str) else value


def _date(value: Any) -> date | None:
    return date.fromisoformat(value) if isinstance(value, str) else value


# --------------------------------------------------------------------------- справочники


def _rows_roles(ctx: SeedContext) -> list[Record]:
    return ROLES


def _rows_specializations(ctx: SeedContext) -> list[Record]:
    return [
        {
            "code": r["id"],
            "label": r["label"],
            "description": r.get("description", ""),
            "active": r.get("active", True),
        }
        for r in ctx.get("specializations")
    ]


def _rows_grades(ctx: SeedContext) -> list[Record]:
    return [{"code": r["id"], "label": r["label"], "order": r["order"]} for r in ctx.get("grades")]


def _rows_categories(ctx: SeedContext) -> list[Record]:
    return [
        {
            "code": r["id"],
            "specialization": r["specialization"],
            "grade": r["grade"],
            "label": r["label"],
        }
        for r in ctx.get("categories")
    ]


def _rows_topics(ctx: SeedContext) -> list[Record]:
    return [
        {"code": r["id"], "specialization": r["specialization"], "label": r["label"]}
        for r in ctx.get("topics")
    ]


def _rows_skills(ctx: SeedContext) -> list[Record]:
    return [{"code": r["id"], "label": r["label"]} for r in ctx.get("skills")]


def _rows_skill_specializations(ctx: SeedContext) -> list[Record]:
    return [
        {"skill_code": r["id"], "specialization": spec}
        for r in ctx.get("skills")
        for spec in r.get("specializations", [])
    ]


def _rows_platform_settings(ctx: SeedContext) -> list[Record]:
    """Одна запись `default` с полями → строки ключ/значение."""
    rows: list[Record] = []
    for record in ctx.get("platform_settings"):
        rows.extend({"key": k, "value": v} for k, v in record.items() if k != "id")
    return rows


# --------------------------------------------------------------------------- пользователи


def _rows_users(ctx: SeedContext) -> list[Record]:
    passwords = {a["user_id"]: a["password"] for a in ctx.get("demo_accounts")}
    return [
        {
            "id": r["id"],
            "email": r["email"],
            "password_hash": hash_password(passwords[r["id"]]) if r["id"] in passwords else None,
            "role": r["role"],
            "full_name": r["full_name"],
            "email_verified": r.get("email_verified", False),
            "blocked": r.get("blocked", False),
            "failed_login_attempts": 0,
            "locked_until": None,
            "last_login_at": _dt(r.get("last_login_at")),
            "created_at": _dt(r["created_at"]),
        }
        for r in ctx.get("users")
    ]


def _rows_consents(ctx: SeedContext) -> list[Record]:
    return [
        {
            "id": r["id"],
            "user_id": r["user_id"],
            "type": r["type"],
            "version": r["version"],
            "granted": r["granted"],
            "granted_at": _dt(r.get("granted_at")),
            "revoked_at": _dt(r.get("revoked_at")),
        }
        for r in ctx.get("consents")
    ]


# --------------------------------------------------------------------------- компании


def _rows_companies(ctx: SeedContext) -> list[Record]:
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "description": r.get("description", ""),
            "industry": r.get("industry", ""),
            "website": r.get("website"),
            "city": r.get("city"),
            "contact_email": r["contact_email"],
            "contact_phone": r.get("contact_phone"),
            "inn": r.get("inn"),
            "verified_domain": r.get("verified_domain", False),
            "trust_score": r.get("trust_score", 50),
            "blocked": r.get("blocked", False),
            "invite_code": r.get("invite_code"),
            "created_at": _dt(r["created_at"]),
        }
        for r in ctx.get("companies")
    ]


def _rows_recruiters(ctx: SeedContext) -> list[Record]:
    # full_name и email рекрутера живут в users
    return [
        {
            "id": r["id"],
            "user_id": r["user_id"],
            "company_id": r["company_id"],
            "position": r.get("position", ""),
            "phone": r.get("phone"),
            "telegram": r.get("telegram"),
            "is_company_admin": r.get("is_company_admin", False),
        }
        for r in ctx.get("recruiters")
    ]


# --------------------------------------------------------------------------- кандидаты


def _rows_candidate_profiles(ctx: SeedContext) -> list[Record]:
    # full_name/email → users; stack → candidate_skills; fsp_id → fsp_links;
    # category_label и profile_completeness вычисляются при чтении
    return [
        {
            "id": r["id"],
            "user_id": r["user_id"],
            "pseudonym": r["pseudonym"],
            "phone": r.get("phone"),
            "telegram": r.get("telegram"),
            "city": r.get("city"),
            "work_formats": r.get("work_formats", []),
            "specialization": r.get("specialization"),
            "grade": r.get("grade"),
            "category": r.get("category"),
            "theta": r.get("theta"),
            "theta_se": r.get("theta_se"),
            "topic_scores": r.get("topic_scores", []),
            "roles_in_team": r.get("roles_in_team", []),
            "experience_years": r.get("experience_years", 0),
            "soft_skills": r.get("soft_skills", []),
            "about": r.get("about", ""),
            "links": r.get("links", []),
            "min_salary": r.get("min_salary"),
            "privacy": r.get("privacy", {}),
            "job_search_paused": r.get("job_search_paused", False),
            "publication_consent": r.get("publication_consent", False),
            "fsp_score": r.get("fsp_score"),
            "fsp_badges": r.get("fsp_badges", []),
            "freshness": r.get("freshness", 0),
            "last_test_at": _dt(r.get("last_test_at")),
            "grade_changed_at": _dt(r.get("grade_changed_at")),
            "created_at": _dt(r["created_at"]),
        }
        for r in ctx.get("candidates")
    ]


def _rows_candidate_skills(ctx: SeedContext) -> list[Record]:
    return [
        {"candidate_id": r["id"], "skill_code": code, "position": pos}
        for r in ctx.get("candidates")
        for pos, code in enumerate(r.get("stack", []))
    ]


def _rows_fsp_links(ctx: SeedContext) -> list[Record]:
    # id привязки = id кандидата (в фикстурах у привязки нет своего id)
    return [
        {
            "id": r["id"],
            "candidate_id": r["id"],
            "fsp_id": r["fsp_id"],
            "keycloak_sub": None,
            "linked_at": _dt(r["created_at"]),
            "last_sync_at": _dt(r.get("last_test_at") or r["created_at"]),
        }
        for r in ctx.get("candidates")
        if r.get("fsp_id")
    ]


def _rows_fsp_achievements(ctx: SeedContext) -> list[Record]:
    synced = now_msk()
    return [
        {
            "id": r["id"],
            "fsp_id": r["fsp_id"],
            "external_id": str(r.get("external_id") or r["id"]),
            "competition": r["competition"],
            "discipline": r["discipline"],
            "level": r["level"],
            "date": _date(r["date"]),
            "place": r.get("place"),
            "diploma": r.get("diploma"),
            "team": r.get("team"),
            "role": r.get("role"),
            "rating": r.get("rating"),
            "protocol_url": r.get("protocol_url"),
            "verified": r.get("verified", True),
            "synced_at": synced,
        }
        for r in ctx.get("fsp_achievements")
    ]


# --------------------------------------------------------------------------- подбор, вакансии


def _rows_needs(ctx: SeedContext) -> list[Record]:
    return [
        {
            "id": r["id"],
            "company_id": r["company_id"],
            "recruiter_id": r["recruiter_id"],
            "title": r["title"],
            "raw_text": r.get("raw_text"),
            "specialization": r["specialization"],
            "grade": r["grade"],
            "category": r["category"],
            "skills_required": r.get("skills_required", []),
            "skills_desired": r.get("skills_desired", []),
            "team_description": r.get("team_description", ""),
            "work_format": r["work_format"],
            "city": r.get("city"),
            "salary_from": r["salary_from"],
            "salary_to": r["salary_to"],
            "status": r.get("status", "active"),
            "saved_filters": r.get("saved_filters", {}),
            "created_at": _dt(r["created_at"]),
        }
        for r in ctx.get("needs")
    ]


def _rows_vacancies(ctx: SeedContext) -> list[Record]:
    return [
        {
            "id": r["id"],
            "company_id": r["company_id"],
            "title": r["title"],
            "description": r["description"],
            "specialization": r["specialization"],
            "grade": r["grade"],
            "category": r["category"],
            "skills_required": r.get("skills_required", []),
            "skills_desired": r.get("skills_desired", []),
            "work_format": r["work_format"],
            "city": r.get("city"),
            "salary_from": r["salary_from"],
            "salary_to": r["salary_to"],
            "status": r["status"],
            "published_at": _dt(r.get("published_at")),
            "created_at": _dt(r["created_at"]),
        }
        for r in ctx.get("vacancies")
    ]


def _rows_applications(ctx: SeedContext) -> list[Record]:
    return [
        {
            "id": r["id"],
            "vacancy_id": r["vacancy_id"],
            "candidate_id": r["candidate_id"],
            "cover_letter": r.get("cover_letter", ""),
            "status": r["status"],
            "contact_type": (r.get("contact_method") or {}).get("type"),
            "contact_value": (r.get("contact_method") or {}).get("value"),
            "invite_message": r.get("invite_message", ""),
            "created_at": _dt(r["created_at"]),
            "updated_at": _dt(r.get("updated_at") or r["created_at"]),
        }
        for r in ctx.get("applications")
    ]


# --------------------------------------------------------------------------- тестирование


def _rows_items(ctx: SeedContext) -> list[Record]:
    # generator: в фикстурах нет — имя генератора движка совпадает с кодом шаблона;
    # correct_count = exposures × correct_rate
    return [
        {
            "id": r["id"],
            "code": r["code"],
            "title": r["title"],
            "description": r.get("description", ""),
            "specialization": r["specialization"],
            "topic": r["topic"],
            "target_grade": r["target_grade"],
            "format": r["format"],
            "generator": r.get("generator") or r["code"],
            "generator_params": r.get("generator_params", {}),
            "a": r["a"],
            "b": r["b"],
            "status": r["status"],
            "source": r.get("source", "expert"),
            "exposures": r.get("exposures", 0),
            "correct_count": round(r.get("exposures", 0) * (r.get("correct_rate") or 0)),
            "leak_flag": r.get("leak_flag", False),
            "leak_score": r.get("leak_score", 0),
            "created_at": _dt(r["created_at"]),
        }
        for r in ctx.get("items")
    ]


def _rows_test_sessions(ctx: SeedContext) -> list[Record]:
    # ci_low/ci_high — в engine_state; result_category = "<spec>:<result_grade>"
    rows = []
    for r in ctx.get("test_sessions"):
        state = {k: r[k] for k in ("ci_low", "ci_high") if r.get(k) is not None}
        rows.append(
            {
                "id": r["id"],
                "candidate_id": r["candidate_id"],
                "specialization": r["specialization"],
                "target_grade": r["target_grade"],
                "kind": r["kind"],
                "status": r["status"],
                "started_at": _dt(r["started_at"]),
                "finished_at": _dt(r.get("finished_at")),
                "items_answered": r.get("items_answered", 0),
                "max_items": r.get("max_items", 15),
                "theta": r.get("theta"),
                "se": r.get("se"),
                "result_grade": r.get("result_grade"),
                "passed": r.get("passed"),
                "topic_scores": r.get("topic_scores", []),
                "engine_state": state,
            }
        )
    return rows


def _rows_grade_history(ctx: SeedContext) -> list[Record]:
    return [
        {
            "id": r["id"],
            "candidate_id": r["candidate_id"],
            "at": _dt(r["at"]),
            "event": r["event"],
            "specialization": r.get("specialization"),
            "grade_from": r.get("grade_from"),
            "grade_to": r.get("grade_to"),
            "test_session_id": r.get("test_session_id"),
            "comment": r.get("comment", ""),
        }
        for r in ctx.get("grade_history")
    ]


# --------------------------------------------------------------------------- приглашения


def _rows_invitations(ctx: SeedContext) -> list[Record]:
    rows = []
    for r in ctx.get("invitations"):
        contact = r.get("contact_method") or {}
        rows.append(
            {
                "id": r["id"],
                "candidate_id": r["candidate_id"],
                "recruiter_id": r["recruiter_id"],
                "company_id": r["company_id"],
                "need_id": r.get("need_id"),
                "vacancy_id": r.get("vacancy_id"),
                "category": r["category"],
                "description": r["description"],
                "salary_from": r["salary_from"],
                "salary_to": r["salary_to"],
                "contact_type": contact.get("type", "other"),
                "contact_value": contact.get("value", ""),
                "task_text": r.get("task_text"),
                "status": r["status"],
                "decline_reason": r.get("decline_reason"),
                "decline_comment": r.get("decline_comment"),
                "viewed_at": _dt(r.get("viewed_at")),
                "responded_at": _dt(r.get("responded_at")),
                "expires_at": _dt(r["expires_at"]),
                "withdrawn_at": _dt(r.get("withdrawn_at")),
                "created_at": _dt(r["created_at"]),
            }
        )
    return rows


def _rows_invitation_events(ctx: SeedContext) -> list[Record]:
    # actor_user_id в фикстуре нет — восстанавливаем по роли: рекрутер или кандидат приглашения
    invitations = ctx.by_id("invitations")
    recruiters = ctx.by_id("recruiters")
    candidates = ctx.by_id("candidates")
    rows = []
    for r in ctx.get("invitation_events"):
        inv = invitations.get(r["invitation_id"], {})
        actor = r.get("actor_user_id")
        if actor is None and r.get("actor_role") == "recruiter":
            actor = recruiters.get(inv.get("recruiter_id"), {}).get("user_id")
        elif actor is None and r.get("actor_role") == "candidate":
            actor = candidates.get(inv.get("candidate_id"), {}).get("user_id")
        rows.append(
            {
                "id": r["id"],
                "invitation_id": r["invitation_id"],
                "type": r["type"],
                "at": _dt(r["at"]),
                "actor_user_id": actor,
                "actor_role": r.get("actor_role"),
            }
        )
    return rows


# --------------------------------------------------------------------------- задания, жалобы


def _rows_regular_tasks(ctx: SeedContext) -> list[Record]:
    return [
        {
            "id": r["id"],
            "company_id": r["company_id"],
            "recruiter_id": r["recruiter_id"],
            "title": r["title"],
            "statement": r["statement"],
            "category": r["category"],
            "deadline_days": r.get("deadline_days", 7),
            "status": r.get("status", "active"),
            "created_at": _dt(r["created_at"]),
        }
        for r in ctx.get("regular_tasks")
    ]


def _rows_task_submissions(ctx: SeedContext) -> list[Record]:
    return [
        {
            "id": r["id"],
            "task_id": r["task_id"],
            "candidate_id": r["candidate_id"],
            "status": r["status"],
            "assigned_at": _dt(r["assigned_at"]),
            "due_at": _dt(r["due_at"]),
            "answer_kind": r.get("answer_kind"),
            "answer_text": r.get("answer_text"),
            "submitted_at": _dt(r.get("submitted_at")),
            "score": r.get("score"),
            "grader_comment": r.get("grader_comment"),
            "graded_by": r.get("graded_by"),
            "graded_at": _dt(r.get("graded_at")),
        }
        for r in ctx.get("task_submissions")
    ]


def _rows_reports(ctx: SeedContext) -> list[Record]:
    return [
        {
            "id": r["id"],
            "company_id": r["company_id"],
            "reporter_candidate_id": r["reporter_candidate_id"],
            "invitation_id": r.get("invitation_id"),
            "vacancy_id": r.get("vacancy_id"),
            "reason": r["reason"],
            "text": r["text"],
            "status": r["status"],
            "resolution": r.get("resolution"),
            "resolved_by": r.get("resolved_by"),
            "resolved_at": _dt(r.get("resolved_at")),
            "created_at": _dt(r["created_at"]),
        }
        for r in ctx.get("reports")
    ]


def _rows_audit_log(ctx: SeedContext) -> list[Record]:
    return [
        {
            "id": r["id"],
            "at": _dt(r["at"]),
            "actor_user_id": r.get("actor_user_id"),
            "actor_role": r.get("actor_role"),
            "action": r["action"],
            "target_type": r["target_type"],
            "target_id": r.get("target_id"),
            "summary": r.get("summary", ""),
            "details": r.get("details", {}),
        }
        for r in ctx.get("audit_log")
    ]


# Порядок важен: сначала то, на что ссылаются внешние ключи
STEPS: list[tuple[str, Callable[[SeedContext], list[Record]]]] = [
    ("roles", _rows_roles),
    ("specializations", _rows_specializations),
    ("grades", _rows_grades),
    ("categories", _rows_categories),
    ("topics", _rows_topics),
    ("skills", _rows_skills),
    ("skill_specializations", _rows_skill_specializations),
    ("platform_settings", _rows_platform_settings),
    ("users", _rows_users),
    ("consents", _rows_consents),
    ("companies", _rows_companies),
    ("recruiters", _rows_recruiters),
    ("candidate_profiles", _rows_candidate_profiles),
    ("candidate_skills", _rows_candidate_skills),
    ("fsp_links", _rows_fsp_links),
    ("fsp_achievements", _rows_fsp_achievements),
    ("needs", _rows_needs),
    ("vacancies", _rows_vacancies),
    ("applications", _rows_applications),
    ("items", _rows_items),
    ("test_sessions", _rows_test_sessions),
    ("grade_history", _rows_grade_history),
    ("invitations", _rows_invitations),
    ("invitation_events", _rows_invitation_events),
    ("regular_tasks", _rows_regular_tasks),
    ("task_submissions", _rows_task_submissions),
    ("reports", _rows_reports),
    ("audit_log", _rows_audit_log),
]

# Фикстуры без своей таблицы: читаются модулями напрямую (или служат источником для других таблиц)
NOT_LOADED = (
    "decline_reasons",  # фиксированный справочник (enum), отдаётся из фикстуры
    "survey_questions",  # вопросы опроса — модуль testing
    "vacancy_tests",  # примеры заданий из вакансий — модуль admin/testing (волна 3)
    "validation_charts",  # графики валидации — модуль eval
    "demo_accounts",  # источник паролей для users
)


@dataclass
class SeedReport:
    reset: bool
    # таблица → (строк в фикстурах, вставлено)
    tables: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def inserted(self) -> int:
        return sum(ins for _, ins in self.tables.values())

    def format(self) -> str:
        lines = [f"{'таблица':<24}{'в фикстурах':>12}{'вставлено':>11}"]
        lines += [f"{t:<24}{n:>12}{ins:>11}" for t, (n, ins) in self.tables.items()]
        suffix = " (после очистки)" if self.reset else ""
        lines.append(f"Итого вставлено строк: {self.inserted}{suffix}")
        return "\n".join(lines)


def _table(name: str) -> Table:
    return Base.metadata.tables[name]


def _check_columns(table: Table, rows: list[Record]) -> None:
    if not rows:
        return
    keys = set(rows[0])
    unknown = keys - set(table.columns.keys())
    if unknown:
        raise ValueError(f"{table.name}: нет колонок {sorted(unknown)}")
    for row in rows:
        if set(row) != keys:
            raise ValueError(f"{table.name}: строки с разным набором полей")


async def _insert(conn: AsyncConnection, table: Table, rows: list[Record]) -> int:
    _check_columns(table, rows)
    inserted = 0
    for start in range(0, len(rows), CHUNK):
        chunk = rows[start : start + CHUNK]
        result = await conn.execute(pg_insert(table).values(chunk).on_conflict_do_nothing())
        inserted += max(result.rowcount or 0, 0)
    return inserted


async def reset_tables(conn: AsyncConnection) -> None:
    """Очистить все таблицы, кроме ролей.

    DELETE в обратном порядке зависимостей, а не TRUNCATE: на маленьких таблицах это в разы
    быстрее (TRUNCATE пересоздаёт файлы таблиц). Последовательности потом сдвигает
    `sync_sequences`.
    """
    for table in reversed(Base.metadata.sorted_tables):
        if table.name not in KEEP_ON_RESET:
            await conn.execute(table.delete())


async def sync_sequences(conn: AsyncConnection) -> None:
    """Сдвинуть последовательности id за максимальный id (после вставки с явными id)."""
    for table in Base.metadata.sorted_tables:
        pk = list(table.primary_key.columns)
        if len(pk) != 1 or pk[0].name != "id" or not isinstance(pk[0].type, Integer):
            continue
        await conn.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table.name}), 0) + 1, false)"
            )
        )


async def load_seed(
    conn: AsyncConnection, *, reset: bool = False, seed_dir: Path | None = None
) -> SeedReport:
    """Загрузить фикстуры в БД в рамках переданного соединения (транзакцию открывает вызывающий)."""
    ctx = SeedContext(Path(seed_dir or get_settings().seed_dir))
    report = SeedReport(reset=reset)
    if reset:
        await reset_tables(conn)
    for table_name, build in STEPS:
        rows = build(ctx)
        report.tables[table_name] = (len(rows), await _insert(conn, _table(table_name), rows))
    await sync_sequences(conn)
    return report


async def run_seed(
    database_url: str | None = None, *, reset: bool = False, seed_dir: Path | None = None
) -> SeedReport:
    """Загрузка через отдельное подключение (CLI, старт приложения, тесты)."""
    engine = create_async_engine(database_url or get_settings().database_url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            return await load_seed(conn, reset=reset, seed_dir=seed_dir)
    finally:
        await engine.dispose()


async def seed_on_startup() -> SeedReport | None:
    """Вызвать из lifespan приложения: грузит сид, если включён SEED_ON_STARTUP (dev)."""
    if not get_seed_settings().seed_on_startup:
        return None
    return await run_seed()

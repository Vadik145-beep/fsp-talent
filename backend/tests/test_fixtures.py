"""Фикстуры data/seed: соответствуют схемам API и воспроизводятся генератором байт в байт."""

import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from app.admin.schemas import AuditEntry, ItemDetail, PlatformSettings, Report, VacancyTestResult
from app.candidates.schemas import CandidateProfile
from app.catalog.schemas import Category, DeclineReasonItem, Grade, Skill, Specialization, Topic
from app.common import fixtures
from app.companies.schemas import Company, Recruiter
from app.core.config import REPO_ROOT
from app.eval.schemas import ValidationChart
from app.fsp.schemas import FspAchievement
from app.invitations.schemas import InvitationEvent, InvitationRecord
from app.matching.schemas import Need
from app.tasks.schemas import RegularTask, TaskSubmission
from app.testing.schemas import GradeHistoryEntry, SurveyQuestion
from app.testing.schemas import TestSession as SessionSchema
from app.users.schemas import Consent, UserRecord
from app.vacancies.schemas import ApplicationRecord, Vacancy

SCHEMAS: dict[str, Any] = {
    "specializations": Specialization,
    "grades": Grade,
    "categories": Category,
    "topics": Topic,
    "skills": Skill,
    "decline_reasons": DeclineReasonItem,
    "users": UserRecord,
    "consents": Consent,
    "companies": Company,
    "recruiters": Recruiter,
    "candidates": CandidateProfile,
    "fsp_achievements": FspAchievement,
    "survey_questions": SurveyQuestion,
    "items": ItemDetail,
    "test_sessions": SessionSchema,
    "grade_history": GradeHistoryEntry,
    "needs": Need,
    "vacancies": Vacancy,
    "applications": ApplicationRecord,
    "invitations": InvitationRecord,
    "invitation_events": InvitationEvent,
    "regular_tasks": RegularTask,
    "task_submissions": TaskSubmission,
    "reports": Report,
    "audit_log": AuditEntry,
    "platform_settings": PlatformSettings,
    "validation_charts": ValidationChart,
    "vacancy_tests": VacancyTestResult,
}
SEED_DIR = REPO_ROOT / "data" / "seed"


def test_every_fixture_file_has_schema() -> None:
    files = {p.stem for p in SEED_DIR.glob("*.json")}
    assert files - {"demo_accounts"} == set(SCHEMAS)


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_fixture_matches_schema_exactly(name: str) -> None:
    """Каждая запись проходит схему, и схема не теряет полей записи (поля = поля API)."""
    model = SCHEMAS[name]
    records = fixtures.load(name)
    assert records, name
    for record in records:
        dumped = model.model_validate(record).model_dump(mode="json")
        assert set(record) <= set(dumped), f"{name}: лишние поля {set(record) - set(dumped)}"


def test_counts_match_plan() -> None:
    assert len(fixtures.load("specializations")) == 6
    assert len(fixtures.load("grades")) == 4
    assert 55 <= len(fixtures.load("skills")) <= 75
    assert len(fixtures.load("companies")) == 3
    # 40 «сюжетных» кандидатов + банк (id от 50): в выдаче 246, в каждой категории от 6
    assert len(fixtures.load("candidates")) == 251
    assert len(fixtures.load("vacancies")) == 8
    assert len(fixtures.load("invitations")) == 25
    assert len(fixtures.load("items")) == 30
    statuses = {i["status"] for i in fixtures.load("invitations")}
    assert statuses == {"sent", "viewed", "accepted", "declined", "expired", "withdrawn"}


def test_fsp_id_convention() -> None:
    linked = {c["fsp_id"] for c in fixtures.load("candidates") if c["fsp_id"]}
    expected = {f"FSP-{i:06d}" for i in [*range(1, 21), *range(31, 36), *range(101, 181)]}
    assert linked == expected
    with_history = {a["fsp_id"] for a in fixtures.load("fsp_achievements")}
    assert with_history <= {f"FSP-{i:06d}" for i in [*range(1, 31), *range(101, 181)]}


def test_synthetic_emails() -> None:
    for user in fixtures.load("users"):
        assert user["email"].endswith("@example.com")


def test_generator_is_deterministic(tmp_path: Path) -> None:
    path = REPO_ROOT / "scripts" / "seed" / "generate_fixtures.py"
    spec = importlib.util.spec_from_file_location("generate_fixtures_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.__dict__["OUT_DIR"] = tmp_path
    module.main()
    for generated in tmp_path.glob("*.json"):
        committed = SEED_DIR / generated.name
        assert json.loads(generated.read_text(encoding="utf-8")) == json.loads(
            committed.read_text(encoding="utf-8")
        ), f"{generated.name}: перегенерируйте фикстуры"


def test_demo_data_for_jury() -> None:
    """Демо-данные живут до проверки жюри (15.11.2026) и подборка не пустая."""
    users = {u["id"]: u for u in fixtures.load("users")}
    shown = [
        c
        for c in fixtures.load("candidates")
        if c["grade"]
        and c["publication_consent"]
        and not c["job_search_paused"]
        and not users[c["user_id"]]["blocked"]
    ]
    per_category = Counter(c["category"] for c in shown)
    assert len(per_category) == 24 and min(per_category.values()) >= 6
    for spec in ("backend", "frontend", "data_ml"):
        for grade in ("junior", "middle", "senior"):
            assert per_category[f"{spec}:{grade}"] >= 12, (spec, grade)
    with_history = sum(1 for c in fixtures.load("candidates") if c["fsp_badges"])
    assert 0.35 <= with_history / len(fixtures.load("candidates")) <= 0.45
    tasks = {t["id"]: t for t in fixtures.load("regular_tasks")}
    for cand_id in (1, 26):
        pending = [
            i
            for i in fixtures.load("invitations")
            if i["candidate_id"] == cand_id and i["status"] == "sent"
        ]
        assert len(pending) == 2 and len({i["company_id"] for i in pending}) == 2
        assert all(i["expires_at"] >= "2026-11-15" for i in pending)
        offers = [
            s
            for s in fixtures.load("task_submissions")
            if s["candidate_id"] == cand_id and s["status"] == "assigned"
        ]
        assert len(offers) == 3 and all(s["due_at"] >= "2026-11-15" for s in offers)
        assert len({tasks[s["task_id"]]["company_id"] for s in offers}) == 3
    recruiter_needs = [
        n for n in fixtures.load("needs") if n["company_id"] == 1 and n["status"] == "active"
    ]
    assert len({n["category"] for n in recruiter_needs}) == len(recruiter_needs) >= 2
    assert all(per_category[n["category"]] >= 10 for n in recruiter_needs)
    version = fixtures.load("platform_settings")[0]["consent_version"]
    for consent in fixtures.load("consents"):
        assert consent["granted_at"] is None or consent["granted_at"][:10] >= version


def test_free_fsp_accounts_not_linked() -> None:
    """Учётки fsp.free* в Keycloak свободны (ни к кому не привязаны), реестр их знает."""
    realm = json.loads((REPO_ROOT / "infra/keycloak/realm-fsp.json").read_text(encoding="utf-8"))
    registry = json.loads(
        (REPO_ROOT / "services/fsp-registry-mock/data/participants.json").read_text(
            encoding="utf-8"
        )
    )
    people = {p["fsp_id"]: p for p in registry["participants"]}
    linked = {c["fsp_id"] for c in fixtures.load("candidates") if c["fsp_id"]}
    free = {
        u["username"]: u["attributes"]["fsp_id"][0]
        for u in realm["users"]
        if u["username"].startswith("fsp.free")
    }
    assert len(free) == 6 and not set(free.values()) & linked
    for login, fsp_id in free.items():
        p = people[fsp_id]
        assert bool(p["achievements"]) == (login != "fsp.free.nohistory"), login
    user = next(u for u in realm["users"] if u["username"] == "fsp.free01")
    assert (user["firstName"], user["lastName"]) == (
        people["FSP-000022"]["first_name"],
        people["FSP-000022"]["last_name"],
    )

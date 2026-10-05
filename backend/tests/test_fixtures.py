"""Фикстуры data/seed: соответствуют схемам API и воспроизводятся генератором байт в байт."""

import importlib.util
import json
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
    assert len(fixtures.load("candidates")) == 40
    assert len(fixtures.load("vacancies")) == 8
    assert len(fixtures.load("invitations")) == 20
    assert len(fixtures.load("items")) == 30
    statuses = {i["status"] for i in fixtures.load("invitations")}
    assert statuses == {"sent", "viewed", "accepted", "declined", "expired", "withdrawn"}


def test_fsp_id_convention() -> None:
    linked = {c["fsp_id"] for c in fixtures.load("candidates") if c["fsp_id"]}
    expected = {f"FSP-{i:06d}" for i in [*range(1, 21), *range(31, 36)]}
    assert linked == expected
    with_history = {a["fsp_id"] for a in fixtures.load("fsp_achievements")}
    assert with_history <= {f"FSP-{i:06d}" for i in range(1, 31)}


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

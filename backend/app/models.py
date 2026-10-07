"""Реестр всех моделей — импортируется Alembic, чтобы metadata знала все таблицы."""

from app.admin.models import AuditLog, Report
from app.auth.models import EmailToken
from app.candidates.models import CandidateProfile, Resume, candidate_skills
from app.catalog.models import (
    Category,
    Grade,
    PlatformSetting,
    Skill,
    Specialization,
    Topic,
    skill_specializations,
)
from app.companies.models import Company, Recruiter
from app.core.db import Base
from app.fsp.models import FspAchievement, FspLink
from app.integrations.models import CompanyApiToken, WebhookDelivery, WebhookEndpoint
from app.invitations.models import Invitation, InvitationEvent
from app.matching.models import Need
from app.nlp.models import VacancyTest
from app.tasks.models import RegularTask, TaskSubmission
from app.testing.models import GradeHistory, Item, ItemParamsLog, TestAnswer, TestSession
from app.users.models import Consent, Role, User
from app.vacancies.models import Application, Vacancy

__all__ = [
    "Application",
    "AuditLog",
    "Base",
    "CandidateProfile",
    "Category",
    "Company",
    "CompanyApiToken",
    "Consent",
    "EmailToken",
    "FspAchievement",
    "FspLink",
    "Grade",
    "GradeHistory",
    "Invitation",
    "InvitationEvent",
    "Item",
    "ItemParamsLog",
    "Need",
    "PlatformSetting",
    "Recruiter",
    "RegularTask",
    "Report",
    "Resume",
    "Role",
    "Skill",
    "Specialization",
    "TaskSubmission",
    "TestAnswer",
    "TestSession",
    "Topic",
    "User",
    "Vacancy",
    "VacancyTest",
    "WebhookDelivery",
    "WebhookEndpoint",
    "candidate_skills",
    "skill_specializations",
]

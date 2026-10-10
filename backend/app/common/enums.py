"""Перечисления, общие для схем API и моделей БД. Коды фиксированы (см. общие правила)."""

from enum import StrEnum


class Role(StrEnum):
    candidate = "candidate"
    recruiter = "recruiter"
    admin = "admin"


class SpecializationCode(StrEnum):
    backend = "backend"
    frontend = "frontend"
    mobile = "mobile"
    data_ml = "data_ml"
    qa = "qa"
    devops = "devops"


class GradeCode(StrEnum):
    intern = "intern"
    junior = "junior"
    middle = "middle"
    senior = "senior"


class GradeStatusCode(StrEnum):
    """Статус грейда соискателя (ответ организаторов FTT.4).

    confirmed — грейд присвоен по результату теста (только такие в выдаче работодателю);
    unconfirmed — грейд заявлен самим соискателем, тест ещё не пройден;
    none — грейд не выбран и не присвоен.
    """

    confirmed = "confirmed"
    unconfirmed = "unconfirmed"
    none = "none"


def grade_status_code(grade: str | None, declared_grade: str | None) -> GradeStatusCode:
    if grade:
        return GradeStatusCode.confirmed
    return GradeStatusCode.unconfirmed if declared_grade else GradeStatusCode.none


class WorkFormat(StrEnum):
    office = "office"
    hybrid = "hybrid"
    remote = "remote"


class ConsentType(StrEnum):
    processing = "processing"  # обработка ПДн (обязательно при регистрации)
    publication = "publication"  # публикация профиля работодателям


class InvitationStatus(StrEnum):
    sent = "sent"
    viewed = "viewed"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"
    withdrawn = "withdrawn"


ACTIVE_INVITATION_STATUSES = (InvitationStatus.sent, InvitationStatus.viewed)


class DeclineReason(StrEnum):
    salary_too_low = "salary_too_low"
    wrong_stack = "wrong_stack"
    not_interested_domain = "not_interested_domain"
    not_looking = "not_looking"
    other = "other"


class ContactMethodType(StrEnum):
    email = "email"
    phone = "phone"
    telegram = "telegram"
    other = "other"


class InvitationEventType(StrEnum):
    created = "created"
    viewed = "viewed"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"
    withdrawn = "withdrawn"
    contacts_revealed = "contacts_revealed"


class VacancyStatus(StrEnum):
    draft = "draft"
    published = "published"
    unpublished = "unpublished"


class ApplicationStatus(StrEnum):
    new = "new"
    viewed = "viewed"
    invited = "invited"
    rejected = "rejected"


class NeedStatus(StrEnum):
    active = "active"
    closed = "closed"


class ItemFormat(StrEnum):
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"
    numeric = "numeric"
    short_text = "short_text"
    code_output = "code_output"
    find_error_line = "find_error_line"
    ordering = "ordering"


class ItemStatus(StrEnum):
    draft = "draft"
    pilot = "pilot"
    active = "active"
    retired = "retired"


class ItemSource(StrEnum):
    expert = "expert"
    llm_vacancy = "llm_vacancy"


class TestSessionKind(StrEnum):
    placement = "placement"  # первый тест после опроса
    grade_lower = "lower"  # пересдача на грейд ниже
    grade_higher = "higher"  # попытка на грейд выше


class TestSessionStatus(StrEnum):
    in_progress = "in_progress"
    finished = "finished"
    abandoned = "abandoned"


class TopicLevel(StrEnum):
    strong = "strong"
    ok = "ok"
    weak = "weak"


class GradeEventType(StrEnum):
    survey = "survey"
    test_passed = "test_passed"
    test_failed = "test_failed"
    grade_changed = "grade_changed"
    offer_lower = "offer_lower"
    offer_higher = "offer_higher"


class FspDiscipline(StrEnum):
    product = "product"  # продуктовое программирование
    algorithmic = "algorithmic"
    cybersecurity = "cybersecurity"
    uas = "uas"  # беспилотные авиационные системы (БАС)
    robotics = "robotics"


class FspLevel(StrEnum):
    regional = "regional"
    national = "national"
    international = "international"


class LinkType(StrEnum):
    github = "github"
    gitlab = "gitlab"
    portfolio = "portfolio"
    linkedin = "linkedin"
    other = "other"


class TaskStatus(StrEnum):
    active = "active"
    archived = "archived"


class SubmissionStatus(StrEnum):
    assigned = "assigned"  # предложено кандидату на этой неделе, ответа ещё нет
    submitted = "submitted"
    graded = "graded"
    expired = "expired"
    skipped = "skipped"  # кандидат выбрал другую задачу из предложенных


class AnswerKind(StrEnum):
    text = "text"
    code = "code"
    approach = "approach"


class ReportReason(StrEnum):
    fake_vacancy = "fake_vacancy"
    spam = "spam"
    salary_mismatch = "salary_mismatch"
    rude = "rude"
    other = "other"


class ReportStatus(StrEnum):
    new = "new"
    in_review = "in_review"
    resolved = "resolved"
    rejected = "rejected"


class CategoryRelation(StrEnum):
    primary = "primary"
    grade_lower = "grade_lower"
    grade_higher = "grade_higher"
    adjacent_specialization = "adjacent_specialization"


class ChartType(StrEnum):
    bar = "bar"
    line = "line"
    scatter = "scatter"
    histogram = "histogram"

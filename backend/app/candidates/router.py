"""Кабинет соискателя (свой профиль) и банк кандидатов для рекрутера (обезличенно)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.grade_schemas import CandidateGradeStatus
from app.candidates.schemas import (
    AnonymousCandidateProfile,
    CandidateCard,
    CandidateDashboard,
    CandidateProfile,
    CandidateProfileUpdate,
    CandidateSettings,
    JobSearchUpdate,
    PrivacySettings,
    PublicationConsentUpdate,
    ResumeParseResult,
)
from app.candidates.service import CandidateProfileService
from app.common.enums import GradeCode, SpecializationCode, WorkFormat
from app.common.pdf import placeholder_pdf
from app.common.schemas import Page
from app.core.db import get_session
from app.core.errors import AppError, error_responses
from app.core.security import CandidateUser, CurrentUser, RecruiterUser

router = APIRouter(prefix="/candidates", tags=["candidates"])

AUTH_ERRORS = (401, 403)
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _me_id(user: CurrentUser) -> int:
    if user.candidate_id is None:
        raise AppError(404, "not_found", "Профиль кандидата не найден")
    return user.candidate_id


@router.get(
    "/me/dashboard",
    response_model=CandidateDashboard,
    summary="Главная соискателя",
    responses=error_responses(*AUTH_ERRORS, 404),
)
async def my_dashboard(user: CandidateUser, session: SessionDep) -> Any:
    return await CandidateProfileService(session).dashboard(_me_id(user))


@router.get(
    "/me/profile",
    response_model=CandidateProfile,
    summary="Свой полный профиль",
    responses=error_responses(*AUTH_ERRORS, 404),
)
async def my_profile(user: CandidateUser, session: SessionDep) -> Any:
    return await CandidateProfileService(session).get_or_404(_me_id(user))


@router.put(
    "/me/profile",
    response_model=CandidateProfile,
    summary="Сохранить профиль",
    description=(
        "Сохраняет профиль. Стек — коды из справочника `skills` (порядок сохраняется). "
        "Минимальная зарплата видна только системе: рекрутеру не отдаётся никогда."
    ),
    responses=error_responses(
        *AUTH_ERRORS,
        404,
        422,
        (422, "unknown_skills", "Технологий нет в справочнике стека"),
    ),
)
async def update_my_profile(
    body: CandidateProfileUpdate, user: CandidateUser, session: SessionDep
) -> Any:
    return await CandidateProfileService(session).update_profile(_me_id(user), body)


@router.post(
    "/me/resume",
    response_model=ResumeParseResult,
    summary="Загрузить PDF-резюме и получить предзаполнение",
    description="Заглушка: разбор PDF появится в волне 3 (T3.2); сейчас поля берутся из профиля.",
    responses=error_responses(
        *AUTH_ERRORS,
        (413, "file_too_large", "Файл больше 5 МБ"),
        (415, "unsupported_file", "Нужен PDF"),
        422,
    ),
)
async def upload_resume(
    user: CandidateUser,
    session: SessionDep,
    file: Annotated[UploadFile, File(description="PDF до 5 МБ")],
) -> Any:
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise AppError(415, "unsupported_file", "Нужен PDF", {"content_type": file.content_type})
    cand = await CandidateProfileService(session).get_or_404(_me_id(user))
    return {
        "resume_id": 1,
        "filename": file.filename or "resume.pdf",
        "parser": "rules",
        "fields": {
            "full_name": {"value": cand["full_name"], "confidence": 0.95},
            "email": {"value": cand["email"], "confidence": 0.99},
            "phone": {"value": cand.get("phone"), "confidence": 0.9},
            "stack": {"value": cand["stack"], "confidence": 0.8},
            "experience_years": {"value": cand["experience_years"], "confidence": 0.7},
            "roles_in_team": {"value": cand["roles_in_team"], "confidence": 0.6},
            "soft_skills": {"value": cand["soft_skills"], "confidence": 0.5},
        },
        "unmatched_skills": [],
    }


@router.get(
    "/me/profile.pdf",
    summary="Скачать стандартизированный PDF-профиль",
    description="Заглушка: настоящий PDF в стиле ФСП — волна 3 (T3.3).",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF-файл"},
        **error_responses(*AUTH_ERRORS, 404),
    },
)
async def my_profile_pdf(user: CandidateUser, session: SessionDep) -> Response:
    cand = await CandidateProfileService(session).get_or_404(_me_id(user))
    content = placeholder_pdf(f"fsp-talent profile: {cand['pseudonym'].split('#')[-1]}")
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="fsp-talent-profile.pdf"'},
    )


@router.get(
    "/me/settings",
    response_model=CandidateSettings,
    summary="Настройки: приватность, согласия, ФСП ID",
    responses=error_responses(*AUTH_ERRORS, 404),
)
async def my_settings(user: CandidateUser, session: SessionDep) -> Any:
    return await CandidateProfileService(session).settings(_me_id(user))


@router.put(
    "/me/settings/privacy",
    response_model=CandidateSettings,
    summary="Что видно работодателю до принятия приглашения",
    responses=error_responses(*AUTH_ERRORS, 404, 422),
)
async def update_privacy(body: PrivacySettings, user: CandidateUser, session: SessionDep) -> Any:
    return await CandidateProfileService(session).update_privacy(_me_id(user), body)


@router.put(
    "/me/settings/job-search",
    response_model=CandidateSettings,
    summary="Пауза поиска («не ищу работу»)",
    responses=error_responses(*AUTH_ERRORS, 404, 422),
)
async def update_job_search(body: JobSearchUpdate, user: CandidateUser, session: SessionDep) -> Any:
    return await CandidateProfileService(session).update_job_search(_me_id(user), body.paused)


@router.put(
    "/me/settings/publication",
    response_model=CandidateSettings,
    summary="Согласие на публикацию профиля работодателям",
    description=(
        "Без согласия кандидата нет в банке кандидатов и подборках. Отзыв действует сразу; "
        "история выдачи и отзыва хранится в согласиях (версия текста и даты)."
    ),
    responses=error_responses(*AUTH_ERRORS, 404, 422),
)
async def update_publication_consent(
    body: PublicationConsentUpdate, user: CandidateUser, session: SessionDep
) -> Any:
    return await CandidateProfileService(session).set_publication_consent(
        _me_id(user), body.granted, user
    )


@router.get(
    "/me/grade",
    response_model=CandidateGradeStatus,
    summary="Категория и грейд: статус, история, доступность теста ниже/выше",
    description=(
        "Правила частоты — движок теста: смена грейда не чаще раза в 90 дней "
        "(первое присвоение не считается), повтор неудачной попытки — через 30 дней. "
        "Интервалы берутся из настроек платформы."
    ),
    responses=error_responses(*AUTH_ERRORS, 404),
)
async def my_grade(user: CandidateUser, session: SessionDep) -> Any:
    return await CandidateProfileService(session).grade(_me_id(user))


@router.get(
    "",
    response_model=Page[CandidateCard],
    summary="Банк кандидатов (обезличенно)",
    description=(
        "Поиск по всей базе. В выдаче только кандидаты с грейдом, согласием на публикацию "
        "и без паузы поиска. ФИО и контактов в ответе нет."
    ),
    responses=error_responses(*AUTH_ERRORS, 422),
)
async def search_candidates(
    user: RecruiterUser,
    session: SessionDep,
    specialization: SpecializationCode | None = None,
    grade: GradeCode | None = None,
    category: str | None = Query(default=None, examples=["backend:middle"]),
    skills: Annotated[list[str] | None, Query(description="Все перечисленные навыки")] = None,
    has_fsp: bool | None = None,
    work_format: WorkFormat | None = None,
    city: str | None = None,
    sort: Annotated[str, Query(pattern="^(theta|fsp|freshness|recent)$")] = "theta",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Any:
    return await CandidateProfileService(session).search(
        specialization=specialization,
        grade=grade,
        category=category,
        skills=skills or [],
        has_fsp=has_fsp,
        work_format=work_format,
        city=city,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{candidate_id}",
    response_model=AnonymousCandidateProfile,
    summary="Обезличенный профиль кандидата",
    description=(
        "Псевдоним вместо ФИО. Поле `contacts` заполнено только после принятия приглашения "
        "компании рекрутера или отклика кандидата на её вакансию."
    ),
    responses=error_responses(*AUTH_ERRORS, 404),
)
async def get_candidate(candidate_id: int, user: RecruiterUser, session: SessionDep) -> Any:
    if user.company_id is None:
        raise AppError(404, "not_found", "Компания не найдена")
    return await CandidateProfileService(session).anonymous_profile(candidate_id, user.company_id)

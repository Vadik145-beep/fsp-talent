"""Кабинет соискателя (свой профиль) и банк кандидатов для рекрутера (обезличенно)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.candidates.grade_schemas import CandidateGradeStatus
from app.candidates.pdf import profile_pdf
from app.candidates.resume import ResumeParseResponse, ResumeService
from app.candidates.schemas import (
    AnonymousCandidateProfile,
    BankCandidateCard,
    CandidateDashboard,
    CandidateProfile,
    CandidateProfileUpdate,
    CandidateSettings,
    DeclaredGradeUpdate,
    JobSearchUpdate,
    PrivacySettings,
    PublicationConsentUpdate,
)
from app.candidates.service import CandidateProfileService
from app.common.enums import GradeCode, SpecializationCode, WorkFormat
from app.common.schemas import Page
from app.core.db import get_session
from app.core.errors import AppError, error_responses
from app.core.security import CandidateUser, CurrentUser, RecruiterUser
from app.matching.service import NeedService

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
    response_model=ResumeParseResponse,
    summary="Загрузить PDF-резюме и получить предзаполнение",
    description=(
        "Разбор PDF (pdfplumber; страницы в две колонки режутся по колонкам) правилами, "
        "если подключена LLM — она дозаполняет только пустые поля (уверенность 0,5). "
        "Поля формы профиля с уверенностью 0..1: "
        "`full_name`, `email`, `phone` (+7XXXXXXXXXX), `city`, `specialization`, `grade`, "
        "`stack` (коды справочника), `experience_years`, `roles_in_team`, `soft_skills`, "
        "`work_formats`, `links`, `about`; не найдено — `value: null, confidence: 0`. "
        "`unmatched_skills` — технологии, которых нет в справочнике. `warnings` — что не удалось "
        "прочитать (скан без текста, битый файл): тогда поля пустые, форму заполняют вручную."
    ),
    responses=error_responses(
        *AUTH_ERRORS,
        404,
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
    candidate_id = _me_id(user)
    await CandidateProfileService(session).get_or_404(candidate_id)
    return await ResumeService(session).upload(candidate_id, file)


@router.get(
    "/me/profile.pdf",
    summary="Скачать стандартизированный PDF-профиль",
    description=(
        "PDF в стиле ФСП: категория и грейд, результаты теста по темам, стек, опыт и роли, "
        "достижения ФСП с отметкой «подтверждено ФСП» (или «нет данных ФСП»)."
    ),
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF-файл"},
        **error_responses(*AUTH_ERRORS, 404),
    },
)
async def my_profile_pdf(user: CandidateUser, session: SessionDep) -> Response:
    content = await profile_pdf(session, _me_id(user))
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


@router.put(
    "/me/declared-grade",
    response_model=CandidateGradeStatus,
    summary="Заявить грейд (до теста): статус «грейд не подтверждён»",
    description=(
        "Грейд соискатель выбирает сам (онбординг), но официально он присваивается только "
        "по результату теста. До теста `grade_status = unconfirmed`: кандидата нет в подборке "
        "и банке кандидатов работодателя. Официальный `grade` этот запрос не меняет."
    ),
    responses=error_responses(*AUTH_ERRORS, 404, 422),
)
async def declare_grade(body: DeclaredGradeUpdate, user: CandidateUser, session: SessionDep) -> Any:
    return await CandidateProfileService(session).declare_grade(
        _me_id(user), str(body.specialization), str(body.grade)
    )


@router.get(
    "",
    response_model=Page[BankCandidateCard],
    summary="Банк кандидатов (обезличенно)",
    description=(
        "Поиск по всей базе. В выдаче только кандидаты с грейдом, подтверждённым тестом "
        "(`grade_status = confirmed`; заявленный, но не подтверждённый грейд — не в выдаче), "
        "согласием на публикацию и без паузы поиска. ФИО и контактов в ответе нет. "
        "`need_id` — потребность своей компании (чужая → 404): у карточек появляются "
        "`match_score` и `match_reasons` (та же формула и причины, что в подборке), "
        "сортировка по умолчанию — `match` (по соответствию). Фильтры работают вместе с ней. "
        "`sort=match` без `need_id` — 422. `invitation_status` — статус последнего приглашения "
        "от вашей компании (null — не приглашали)."
    ),
    responses=error_responses(*AUTH_ERRORS, 404, 422),
)
async def search_candidates(
    user: RecruiterUser,
    session: SessionDep,
    specialization: SpecializationCode | None = None,
    grade: GradeCode | None = None,
    category: str | None = Query(default=None, examples=["backend:middle"]),
    skills: Annotated[list[str] | None, Query(description="Все перечисленные навыки")] = None,
    has_fsp: Annotated[
        bool | None,
        Query(
            description="true — есть подтверждённые достижения ФСП и кандидат их не скрыл; "
            "false — остальные"
        ),
    ] = None,
    work_format: WorkFormat | None = None,
    city: str | None = None,
    need_id: Annotated[
        int | None, Query(description="Потребность своей компании: ранжирование под неё")
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            pattern="^(match|theta|fsp|freshness|recent)$",
            description="По умолчанию: `match` с `need_id`, иначе `theta`",
        ),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Any:
    need = None
    if need_id is not None:
        if user.company_id is None:
            raise AppError(404, "not_found", "Компания не найдена")
        need = await NeedService(session).get_need(need_id, user.company_id)
    elif sort == "match":
        raise AppError(
            422,
            "validation_error",
            "Сортировка по соответствию — только с выбранной потребностью",
            {"fields": {"sort": "Выберите потребность (need_id)"}},
        )
    return await CandidateProfileService(session).search(
        need=need,
        company_id=user.company_id,
        specialization=specialization,
        grade=grade,
        category=category,
        skills=skills or [],
        has_fsp=has_fsp,
        work_format=work_format,
        city=city,
        sort=sort or ("match" if need is not None else "theta"),
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

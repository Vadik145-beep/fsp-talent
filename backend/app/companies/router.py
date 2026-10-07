"""Компания рекрутера: профиль, рекрутеры, дашборд."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.companies.schemas import CompanyUpdate, MyCompany, Recruiter, RecruiterDashboard
from app.companies.service import CompanyService
from app.core.db import get_session
from app.core.errors import AppError, error_responses
from app.core.security import CurrentUser, RecruiterUser
from app.integrations.router import router as integrations_router

router = APIRouter(prefix="/companies", tags=["companies"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _company_id(user: CurrentUser) -> int:
    if user.company_id is None:
        raise AppError(404, "not_found", "Компания не найдена")
    return user.company_id


@router.get(
    "/my",
    response_model=MyCompany,
    summary="Профиль моей компании",
    description="Администратору компании приходит `invite_code` — код приглашения рекрутеров.",
    responses=error_responses(401, 403, 404),
)
async def my_company(user: RecruiterUser, session: SessionDep) -> Any:
    return await CompanyService(session).my(_company_id(user), user)


@router.post(
    "/my/invite-code",
    response_model=MyCompany,
    status_code=status.HTTP_200_OK,
    summary="Выпустить новый код приглашения рекрутеров",
    description="Старый код перестаёт действовать. Только администратор компании.",
    responses=error_responses(
        401, (403, "forbidden", "Код приглашения меняет только администратор компании"), 404
    ),
)
async def regenerate_invite_code(user: RecruiterUser, session: SessionDep) -> Any:
    return await CompanyService(session).my(_company_id(user), user, regenerate=True)


@router.put(
    "/my",
    response_model=MyCompany,
    summary="Изменить профиль компании",
    description="Только администратор компании (рекрутер с флагом `is_company_admin`).",
    responses=error_responses(
        401, (403, "forbidden", "Менять профиль может только администратор компании"), 404, 422
    ),
)
async def update_my_company(body: CompanyUpdate, user: RecruiterUser, session: SessionDep) -> Any:
    return await CompanyService(session).update(_company_id(user), body, user)


@router.get(
    "/my/recruiters",
    response_model=list[Recruiter],
    summary="Рекрутеры компании",
    responses=error_responses(401, 403, 404),
)
async def my_recruiters(user: RecruiterUser, session: SessionDep) -> Any:
    return await CompanyService(session).recruiters(_company_id(user))


@router.get(
    "/my/dashboard",
    response_model=RecruiterDashboard,
    summary="Главная рекрутера",
    responses=error_responses(401, 403, 404),
)
async def recruiter_dashboard(user: RecruiterUser, session: SessionDep) -> Any:
    if user.recruiter_id is None:
        raise AppError(404, "not_found", "Рекрутер не найден")
    return await CompanyService(session).dashboard(_company_id(user), user.recruiter_id)


# API-токены, вебхуки и выгрузка для ATS (T12.2): /api/companies/my/api-tokens, /my/webhooks,
# /ats/export — модуль app.integrations
router.include_router(integrations_router)

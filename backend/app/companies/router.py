"""Компания рекрутера: профиль, рекрутеры, дашборд."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.companies.schemas import Company, CompanyUpdate, Recruiter, RecruiterDashboard
from app.companies.service import CompanyService
from app.core.db import get_session
from app.core.errors import AppError, error_responses
from app.core.security import CurrentUser, RecruiterUser

router = APIRouter(prefix="/companies", tags=["companies"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _company_id(user: CurrentUser) -> int:
    if user.company_id is None:
        raise AppError(404, "not_found", "Компания не найдена")
    return user.company_id


@router.get(
    "/my",
    response_model=Company,
    summary="Профиль моей компании",
    responses=error_responses(401, 403, 404),
)
async def my_company(user: RecruiterUser, session: SessionDep) -> Any:
    return await CompanyService(session).get_or_404(_company_id(user))


@router.put(
    "/my",
    response_model=Company,
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

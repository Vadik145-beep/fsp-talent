"""Согласия пользователя (152-ФЗ): обработка ПДн и публикация профиля."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import ConsentType
from app.core.db import get_session
from app.core.errors import AppError, error_responses
from app.core.security import AnyUser
from app.users.schemas import Consent, ConsentUpdate
from app.users.service import UserService

router = APIRouter(prefix="/users", tags=["users"])

Db = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "/me/consents",
    response_model=list[Consent],
    summary="Мои согласия: версия текста и даты",
    responses=error_responses(401),
)
async def my_consents(user: AnyUser, db: Db) -> Any:
    return await UserService(db).consents(user)


@router.put(
    "/me/consents/{consent_type}",
    response_model=Consent,
    summary="Дать или отозвать согласие",
    description=(
        "Отзыв согласия на публикацию сразу скрывает профиль из выдачи. "
        "Согласие на обработку ПДн отозвать можно только удалением аккаунта (409)."
    ),
    responses=error_responses(
        401,
        (409, "consent_required", "Согласие на обработку ПДн обязательно; удалите аккаунт"),
        422,
    ),
)
async def update_consent(
    consent_type: ConsentType, body: ConsentUpdate, user: AnyUser, db: Db
) -> Any:
    if consent_type == ConsentType.processing and not body.granted:
        raise AppError(
            409, "consent_required", "Согласие на обработку ПДн обязательно; удалите аккаунт"
        )
    return await UserService(db).update_consent(user, consent_type, body.granted, body.version)

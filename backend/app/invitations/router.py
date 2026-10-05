"""Приглашения: список и карточка (обе стороны), создание и отзыв (рекрутер),
принятие и отказ с причиной (кандидат), квота и рыночная подсказка."""

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.common.enums import InvitationStatus
from app.core.errors import error_responses
from app.core.security import CandidateOrRecruiter, CandidateUser, RecruiterUser
from app.invitations.schemas import (
    DeclineRequest,
    Invitation,
    InvitationCreate,
    InvitationDetail,
    InvitationQuota,
    MarketHint,
)
from app.invitations.service import InvitationService

router = APIRouter(prefix="/invitations", tags=["invitations"])
service = InvitationService()

TRANSITION_ERROR = (409, "invalid_transition", "Действие недоступно в текущем статусе приглашения")


@router.get(
    "",
    response_model=list[Invitation],
    summary="Мои приглашения",
    description=(
        "Кандидат видит полученные приглашения, рекрутер — приглашения своей компании. "
        "Контакты другой стороны — только при статусе `accepted`."
    ),
    responses=error_responses(401, 403),
)
async def list_invitations(
    user: CandidateOrRecruiter, status_filter: InvitationStatus | None = Query(None, alias="status")
) -> Any:
    return service.list_for(user, status_filter)


@router.get(
    "/quota",
    response_model=InvitationQuota,
    summary="Квота активных приглашений рекрутера",
    responses=error_responses(401, 403),
)
async def get_quota(user: RecruiterUser) -> Any:
    assert user.recruiter_id is not None
    return service.quota(user.recruiter_id)


@router.get(
    "/market-hint",
    response_model=MarketHint,
    summary="Рыночная подсказка зарплаты по категории",
    responses=error_responses(401, 403, 404, 422),
)
async def market_hint(
    user: RecruiterUser,
    category: Annotated[str, Query(examples=["backend:middle"])],
    salary_from: Annotated[int | None, Query(gt=0)] = None,
    salary_to: Annotated[int | None, Query(gt=0)] = None,
) -> Any:
    return service.market_hint(category, salary_from, salary_to)


@router.post(
    "",
    response_model=Invitation,
    status_code=status.HTTP_201_CREATED,
    summary="Отправить приглашение",
    description=(
        "Вилка от–до обязательна (от ≤ до). Если максимум вилки ниже минимальной зарплаты "
        "кандидата — 422 `salary_below_expectations`, сумма кандидата не раскрывается."
    ),
    responses=error_responses(
        401,
        403,
        (404, "not_found", "Кандидат не найден или скрыт"),
        (409, "quota_exceeded", "Достигнута квота активных приглашений"),
        (409, "already_invited", "У кандидата уже есть активное приглашение"),
        (422, "validation_error", "Ошибка валидации (в т.ч. salary_range_invalid: от > до)"),
        (422, "salary_below_expectations", "Вилка ниже ожиданий кандидата"),
    ),
)
async def create_invitation(body: InvitationCreate, user: RecruiterUser) -> Any:
    return service.create(body, user)


@router.get(
    "/{invitation_id}",
    response_model=InvitationDetail,
    summary="Карточка приглашения с журналом событий",
    description="Открытие кандидатом переводит `sent` → `viewed`.",
    responses=error_responses(401, 403, 404),
)
async def get_invitation(invitation_id: int, user: CandidateOrRecruiter) -> Any:
    return service.detail(invitation_id, user)


@router.post(
    "/{invitation_id}/accept",
    response_model=Invitation,
    summary="Принять приглашение (кандидат)",
    description="После принятия обе стороны видят контакты; раскрытие пишется в журнал.",
    responses=error_responses(401, 403, 404, TRANSITION_ERROR),
)
async def accept_invitation(invitation_id: int, user: CandidateUser) -> Any:
    return service.accept(invitation_id, user)


@router.post(
    "/{invitation_id}/decline",
    response_model=Invitation,
    summary="Отклонить приглашение с причиной (кандидат)",
    responses=error_responses(401, 403, 404, TRANSITION_ERROR, 422),
)
async def decline_invitation(invitation_id: int, body: DeclineRequest, user: CandidateUser) -> Any:
    return service.decline(invitation_id, user, body.reason, body.comment)


@router.post(
    "/{invitation_id}/withdraw",
    response_model=Invitation,
    summary="Отозвать приглашение (рекрутер)",
    responses=error_responses(401, 403, 404, TRANSITION_ERROR),
)
async def withdraw_invitation(invitation_id: int, user: RecruiterUser) -> Any:
    return service.withdraw(invitation_id, user)

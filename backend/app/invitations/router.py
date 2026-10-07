"""Приглашения: список и карточка (обе стороны), создание и отзыв (рекрутер),
принятие и отказ с причиной (кандидат), квота, счётчики и рыночная подсказка."""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import InvitationStatus
from app.core import email as mailer
from app.core.db import get_session
from app.core.errors import error_responses
from app.core.security import CandidateOrRecruiter, CandidateUser, RecruiterUser
from app.invitations.schemas import (
    DeclineRequest,
    Invitation,
    InvitationCounters,
    InvitationCreate,
    InvitationDetail,
    InvitationQuota,
    MarketHint,
)
from app.invitations.service import InvitationService

router = APIRouter(prefix="/invitations", tags=["invitations"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
TRANSITION_ERROR = (409, "invalid_transition", "Действие недоступно в текущем статусе приглашения")


async def _send(to: str, subject: str, text: str) -> None:
    # модуль ищется при вызове — тесты подменяют app.core.email.send_email
    await mailer.send_email_async(to, subject, text)


def _flush_outbox(service: InvitationService, background: BackgroundTasks) -> None:
    """Письма уходят после ответа: недоступный SMTP не задерживает и не ломает запрос."""
    for mail in service.outbox:
        background.add_task(_send, mail.to, mail.subject, mail.text)
    service.outbox.clear()


@router.get(
    "",
    response_model=list[Invitation],
    summary="Мои приглашения",
    description=(
        "Кандидат видит полученные приглашения, рекрутер — приглашения своей компании. "
        "Контакты другой стороны — только при статусе `accepted`. Просроченные `sent`/`viewed` "
        "переводятся в `expired` при обращении."
    ),
    responses=error_responses(401, 403),
)
async def list_invitations(
    user: CandidateOrRecruiter,
    session: SessionDep,
    status_filter: InvitationStatus | None = Query(None, alias="status"),
) -> Any:
    return await InvitationService(session).list_for(user, status_filter)


@router.get(
    "/quota",
    response_model=InvitationQuota,
    summary="Квота активных приглашений рекрутера",
    responses=error_responses(401, 403),
)
async def get_quota(user: RecruiterUser, session: SessionDep) -> Any:
    assert user.recruiter_id is not None
    return await InvitationService(session).quota(user.recruiter_id)


@router.get(
    "/counters",
    response_model=InvitationCounters,
    summary="Счётчики для бейджей кабинета",
    description=(
        "Кандидат: `new` — полученные и ещё не открытые. Рекрутер: `new` — ответы кандидатов "
        "(просмотр, принятие, отказ), которые он ещё не открывал. `active` — ждут ответа."
    ),
    responses=error_responses(401, 403),
)
async def get_counters(user: CandidateOrRecruiter, session: SessionDep) -> Any:
    return await InvitationService(session).counters(user)


@router.get(
    "/market-hint",
    response_model=MarketHint,
    summary="Рыночная подсказка зарплаты по категории",
    description=(
        "Медиана принятых вилок в категории (если принятых ≥ 3), иначе — оценка по ожиданиям "
        "кандидатов категории. При выборке < 3 медиана и вероятность не показываются."
    ),
    responses=error_responses(401, 403, 404, 422),
)
async def market_hint(
    user: RecruiterUser,
    session: SessionDep,
    category: Annotated[str, Query(examples=["backend:middle"])],
    salary_from: Annotated[int | None, Query(gt=0)] = None,
    salary_to: Annotated[int | None, Query(gt=0)] = None,
) -> Any:
    return await InvitationService(session).market_hint(category, salary_from, salary_to)


@router.post(
    "",
    response_model=Invitation,
    status_code=status.HTTP_201_CREATED,
    summary="Отправить приглашение",
    description=(
        "Вилка от–до обязательна (от ≤ до). Если максимум вилки ниже минимальной зарплаты "
        "кандидата — 422 `salary_below_expectations`, сумма кандидата не раскрывается. "
        "Кандидату уходит письмо."
    ),
    responses=error_responses(
        401,
        403,
        (404, "not_found", "Кандидат не найден или скрыт"),
        (409, "quota_exceeded", "Достигнута квота активных приглашений"),
        (409, "already_invited", "У кандидата уже есть активное приглашение"),
        (422, "validation_error", "Ошибка валидации (в т.ч. salary_range_invalid: от > до)"),
        (422, "salary_below_expectations", "Вилка ниже ожиданий кандидата"),
        (403, "company_blocked", "Компания заблокирована администратором платформы"),
    ),
)
async def create_invitation(
    body: InvitationCreate, user: RecruiterUser, session: SessionDep, background: BackgroundTasks
) -> Any:
    service = InvitationService(session)
    result = await service.create(body, user)
    _flush_outbox(service, background)
    return result


@router.get(
    "/{invitation_id}",
    response_model=InvitationDetail,
    summary="Карточка приглашения с журналом событий",
    description="Открытие кандидатом переводит `sent` → `viewed`.",
    responses=error_responses(401, 403, 404),
)
async def get_invitation(
    invitation_id: int, user: CandidateOrRecruiter, session: SessionDep
) -> Any:
    return await InvitationService(session).detail(invitation_id, user)


@router.post(
    "/{invitation_id}/accept",
    response_model=Invitation,
    summary="Принять приглашение (кандидат)",
    description=(
        "После принятия обе стороны видят контакты; раскрытие пишется в журнал событий "
        "и в audit_log. Рекрутеру уходит письмо."
    ),
    responses=error_responses(401, 403, 404, TRANSITION_ERROR),
)
async def accept_invitation(
    invitation_id: int, user: CandidateUser, session: SessionDep, background: BackgroundTasks
) -> Any:
    service = InvitationService(session)
    result = await service.accept(invitation_id, user)
    _flush_outbox(service, background)
    return result


@router.post(
    "/{invitation_id}/decline",
    response_model=Invitation,
    summary="Отклонить приглашение с причиной (кандидат)",
    description="Для причины `other` комментарий обязателен. Рекрутеру уходит письмо.",
    responses=error_responses(401, 403, 404, TRANSITION_ERROR, 422),
)
async def decline_invitation(
    invitation_id: int,
    body: DeclineRequest,
    user: CandidateUser,
    session: SessionDep,
    background: BackgroundTasks,
) -> Any:
    service = InvitationService(session)
    result = await service.decline(invitation_id, user, body.reason, body.comment)
    _flush_outbox(service, background)
    return result


@router.post(
    "/{invitation_id}/withdraw",
    response_model=Invitation,
    summary="Отозвать приглашение (рекрутер)",
    responses=error_responses(401, 403, 404, TRANSITION_ERROR),
)
async def withdraw_invitation(invitation_id: int, user: RecruiterUser, session: SessionDep) -> Any:
    return await InvitationService(session).withdraw(invitation_id, user)

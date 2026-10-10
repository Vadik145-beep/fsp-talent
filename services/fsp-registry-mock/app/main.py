"""Мок реестра ФСП: отдаёт синтетических участников и их достижения по ФСП ID.

Это наша версия будущего API реестра ФСП (реального API организаторы не дают).
Данные синтетические: см. data/participants.json и tools/generate_participants.py.
"""

import os
import re
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.data import Registry, load_registry
from app.schemas import (
    AchievementList,
    Dictionaries,
    DisciplineCode,
    ErrorBody,
    Health,
    LevelCode,
    Participant,
    ParticipantBatch,
)

FSP_ID_RE = re.compile(r"^FSP-\d{6}$")
MAX_BATCH = 100

DESCRIPTION = """
Мок реестра Федерации спортивного программирования (ФСП) для платформы fsp-talent.

**Все данные синтетические**: ФИО, команды, соревнования, места и рейтинги выдуманы.
Названия соревнований составлены по общему образцу и не утверждают, что такие мероприятия
проводились.

Сервис — это **предлагаемый контракт** будущего API реестра ФСП: какие сведения о достижениях
участника платформа хотела бы получать. Подробно — `docs/integration/fsp.md`.

- `FSP-000001`…`FSP-000030` и `FSP-000101`…`FSP-000180` — участники с достижениями;
- `FSP-000031`…`FSP-000040` — участники без истории (пустой список достижений);
- любой другой корректный ID — 404.

Ошибки возвращаются в формате `{"code": "...", "message": "...", "details": {...}}`.
Если задана переменная `FSP_MOCK_API_TOKEN`, все методы, кроме `/health`, требуют заголовок
`Authorization: Bearer <токен>` (в реальной интеграции — сервисный токен Keycloak).
"""

ERRORS_ID = {
    404: {"model": ErrorBody, "description": "Участник с таким ФСП ID не найден"},
    422: {"model": ErrorBody, "description": "Неверный формат ФСП ID или параметров"},
}
ERROR_401 = {401: {"model": ErrorBody, "description": "Нет или неверный сервисный токен"}}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def create_app(registry: Registry | None = None) -> FastAPI:
    app = FastAPI(
        title="Реестр ФСП (мок)",
        version="0.1.0",
        description=DESCRIPTION,
        openapi_tags=[
            {"name": "Участники", "description": "Профиль участника и его достижения"},
            {"name": "Служебное", "description": "Проверка работы и справочники"},
        ],
    )
    app.state.registry = registry or load_registry()

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        body = {"code": exc.code, "message": exc.message, "details": exc.details}
        return JSONResponse(status_code=exc.status, content=body)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        body = {
            "code": "validation_error",
            "message": "Неверные параметры запроса",
            "details": {"errors": [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]},
        }
        return JSONResponse(status_code=422, content=body)

    def get_registry(request: Request) -> Registry:
        return request.app.state.registry

    def check_token(authorization: Annotated[str | None, Header()] = None) -> None:
        expected = os.environ.get("FSP_MOCK_API_TOKEN", "")
        if expected and authorization != f"Bearer {expected}":
            raise ApiError(401, "unauthorized", "Нужен сервисный токен в заголовке Authorization")

    def normalize_id(raw: str) -> str:
        fsp_id = raw.strip().upper()
        if not FSP_ID_RE.match(fsp_id):
            raise ApiError(
                422, "invalid_fsp_id", "ФСП ID должен иметь вид FSP-000001", {"fsp_id": raw}
            )
        return fsp_id

    def find(reg: Registry, raw: str) -> dict:
        fsp_id = normalize_id(raw)
        item = reg.participants.get(fsp_id)
        if item is None:
            raise ApiError(
                404,
                "participant_not_found",
                "Участник ФСП с таким ID не найден",
                {"fsp_id": fsp_id},
            )
        return item

    RegDep = Annotated[Registry, Depends(get_registry)]
    auth = [Depends(check_token)]

    @app.get("/health", response_model=Health, tags=["Служебное"], summary="Проверка работы")
    def health(reg: RegDep) -> dict:
        return {"status": "ok", "participants": len(reg.participants), "synthetic": True}

    @app.get(
        "/dictionaries",
        response_model=Dictionaries,
        tags=["Служебное"],
        summary="Справочники дисциплин и уровней",
        dependencies=auth,
        responses=ERROR_401,
    )
    def dictionaries(reg: RegDep) -> dict:
        return {"disciplines": reg.disciplines, "levels": reg.levels}

    @app.get(
        "/participants",
        response_model=ParticipantBatch,
        tags=["Участники"],
        summary="Несколько участников за один запрос",
        description="Пакетное получение профилей (например, для ночной синхронизации). "
        f"До {MAX_BATCH} ID через запятую. Неизвестные ID попадают в `not_found`.",
        dependencies=auth,
        responses={**ERROR_401, 422: ERRORS_ID[422]},
    )
    def participants_batch(
        reg: RegDep,
        ids: Annotated[
            str, Query(description="ФСП ID через запятую", examples=["FSP-000001,FSP-000031"])
        ],
    ) -> dict:
        raw = [x for x in ids.split(",") if x.strip()]
        if not raw:
            raise ApiError(422, "validation_error", "Передайте хотя бы один ФСП ID")
        if len(raw) > MAX_BATCH:
            raise ApiError(
                422,
                "too_many_ids",
                f"Не больше {MAX_BATCH} ID за запрос",
                {"limit": MAX_BATCH, "received": len(raw)},
            )
        wanted = list(dict.fromkeys(normalize_id(x) for x in raw))
        items = [reg.participants[i]["profile"] for i in wanted if i in reg.participants]
        not_found = [i for i in wanted if i not in reg.participants]
        return {"items": items, "not_found": not_found}

    @app.get(
        "/participants/{fsp_id}",
        response_model=Participant,
        tags=["Участники"],
        summary="Профиль участника",
        description="ФИО, регион, дата регистрации в ФСП и сводка по достижениям.",
        dependencies=auth,
        responses={**ERROR_401, **ERRORS_ID},
    )
    def participant(reg: RegDep, fsp_id: str) -> dict:
        return find(reg, fsp_id)["profile"]

    @app.get(
        "/participants/{fsp_id}/achievements",
        response_model=AchievementList,
        tags=["Участники"],
        summary="Достижения участника",
        description="Список подтверждённых результатов. У участника без истории — "
        "`has_history: false` и пустой `items` (это не ошибка).",
        dependencies=auth,
        responses={**ERROR_401, **ERRORS_ID},
    )
    def achievements(
        reg: RegDep,
        fsp_id: str,
        discipline: Annotated[
            DisciplineCode | None, Query(description="Фильтр по дисциплине")
        ] = None,
        level: Annotated[LevelCode | None, Query(description="Фильтр по уровню")] = None,
    ) -> dict:
        item = find(reg, fsp_id)
        rows = [
            a
            for a in item["achievements"]
            if (discipline is None or a["discipline"]["code"] == discipline)
            and (level is None or a["level"]["code"] == level)
        ]
        return {
            "fsp_id": item["profile"]["fsp_id"],
            "has_history": item["profile"]["has_history"],
            "total": len(rows),
            "items": rows,
            "updated_at": item["profile"]["updated_at"],
        }

    return app


app = create_app()

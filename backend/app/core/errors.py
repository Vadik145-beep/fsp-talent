"""Единый формат ошибок API: {"code": "...", "message": "...", "details": {...}}."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")


class ErrorResponse(BaseModel):
    """Тело любой ошибки API."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "code": "not_found",
                    "message": "Объект не найден",
                    "details": {"resource": "vacancy", "id": 42},
                }
            ]
        }
    )

    code: str = Field(description="Машинный код ошибки (англ.)")
    message: str = Field(description="Сообщение для пользователя (рус.)")
    details: dict[str, Any] = Field(default_factory=dict)


class AppError(Exception):
    """Ошибка приложения, которая превращается в ErrorResponse."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def not_found(resource: str, obj_id: object) -> AppError:
    return AppError(404, "not_found", "Объект не найден", {"resource": resource, "id": obj_id})


# Стандартные ошибки по HTTP-коду: (code, message)
_DEFAULTS: dict[int, tuple[str, str]] = {
    400: ("bad_request", "Некорректный запрос"),
    401: ("unauthorized", "Требуется вход"),
    403: ("forbidden", "Недостаточно прав"),
    404: ("not_found", "Объект не найден"),
    409: ("conflict", "Конфликт состояния"),
    410: ("gone", "Срок действия истёк"),
    422: ("validation_error", "Ошибка валидации данных"),
    429: ("too_many_requests", "Слишком много попыток, попробуйте позже"),
    500: ("internal_error", "Внутренняя ошибка сервера"),
    501: ("not_implemented", "Будет реализовано в следующих волнах"),
    503: ("service_unavailable", "Сервис временно недоступен"),
}

ErrorSpec = int | tuple[int, str, str]


def error_responses(*specs: ErrorSpec) -> dict[int | str, dict[str, Any]]:
    """Описание ошибок для `responses=` эндпоинта.

    Каждый элемент — HTTP-код или кортеж (код, error_code, сообщение).
    Несколько кортежей с одним HTTP-кодом объединяются в несколько примеров.
    """
    grouped: dict[int, list[tuple[str, str]]] = {}
    for spec in specs:
        if isinstance(spec, int):
            status, (code, message) = spec, _DEFAULTS.get(spec, ("error", "Ошибка"))
        else:
            status, code, message = spec
        grouped.setdefault(status, []).append((code, message))

    result: dict[int | str, dict[str, Any]] = {}
    for status, items in grouped.items():
        examples = {
            code: {"summary": message, "value": {"code": code, "message": message, "details": {}}}
            for code, message in items
        }
        result[status] = {
            "model": ErrorResponse,
            "description": "; ".join(f"`{c}` — {m}" for c, m in items),
            "content": {"application/json": {"examples": examples}},
        }
    return result


def _payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return ErrorResponse(code=code, message=message, details=details or {}).model_dump()


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=_payload(exc.code, exc.message, exc.details)
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = jsonable_encoder(exc.errors(), custom_encoder={Exception: str})
        code, message = _DEFAULTS[422]
        return JSONResponse(status_code=422, content=_payload(code, message, {"errors": errors}))

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _DEFAULTS.get(exc.status_code, ("error", str(exc.detail)))
        if isinstance(exc.detail, str) and exc.status_code not in (404, 405):
            message = exc.detail
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(code, message),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Необработанная ошибка: %s", exc)
        code, message = _DEFAULTS[500]
        return JSONResponse(status_code=500, content=_payload(code, message))

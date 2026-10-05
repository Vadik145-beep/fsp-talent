"""Логирование: единый формат и журнал запросов."""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format=LOG_FORMAT, force=True)
    # uvicorn пишет свой access-лог; наш middleware его заменяет
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def register_request_logging(app: FastAPI) -> None:
    logger = logging.getLogger("app.request")

    @app.middleware("http")
    async def log_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if request.url.path != "/api/health":
            logger.info(
                "%s %s -> %s (%.1f мс)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
        return response

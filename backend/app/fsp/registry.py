"""HTTP-клиент реестра ФСП (у нас — мок `services/fsp-registry-mock`).

Контракт — `docs/integration/fsp.md`, раздел 3. Таймауты и повторы: сетевые ошибки и 5xx
повторяются `registry_retries` раз с короткой паузой; 4xx не повторяются. Ошибки
превращаются в исключения с понятными кодами, роутеры отдают их как 503/404.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.fsp.settings import get_fsp_settings

logger = logging.getLogger("app.fsp.registry")

FSP_ID_RE = re.compile(r"^FSP-\d{6}$")
MAX_BATCH = 100
RETRY_PAUSE_SEC = 0.2


class RegistryError(Exception):
    """Реестр ответил неожиданно (4xx кроме 404, битый JSON)."""

    code = "fsp_registry_error"

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class RegistryUnavailableError(RegistryError):
    """Реестр недоступен: сеть, таймаут или 5xx после всех повторов."""

    code = "fsp_registry_unavailable"


class ParticipantNotFoundError(RegistryError):
    """В реестре нет участника с таким ФСП ID (404 participant_not_found)."""

    code = "participant_not_found"


class RegistryClient:
    def __init__(
        self,
        base_url: str,
        *,
        token: str = "",
        timeout: float = 5.0,
        retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_pause: float = RETRY_PAUSE_SEC,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.retries = max(0, retries)
        self.transport = transport
        self.retry_pause = retry_pause

    async def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        last_error = "нет ответа"
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout, connect=min(self.timeout, 3.0)),
            transport=self.transport,
            headers=headers,
        ) as client:
            for attempt in range(self.retries + 1):
                if attempt:
                    await asyncio.sleep(self.retry_pause * attempt)
                try:
                    response = await client.get(path, params=params)
                except httpx.HTTPError as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    logger.warning("Реестр ФСП: %s %s — %s", path, attempt + 1, last_error)
                    continue
                if response.status_code >= 500:
                    last_error = f"HTTP {response.status_code}"
                    logger.warning("Реестр ФСП: %s %s — %s", path, attempt + 1, last_error)
                    continue
                return self._parse(response)
        raise RegistryUnavailableError(f"Реестр ФСП недоступен ({last_error})")

    @staticmethod
    def _parse(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise RegistryError("Реестр ФСП вернул не JSON", response.status_code) from exc
        if response.status_code == 404:
            raise ParticipantNotFoundError("Участник не найден в реестре ФСП", 404)
        if response.status_code >= 400 or not isinstance(body, dict):
            code = body.get("code") if isinstance(body, dict) else None
            raise RegistryError(
                f"Реестр ФСП отклонил запрос (HTTP {response.status_code}, {code})",
                response.status_code,
            )
        return body

    async def participant(self, fsp_id: str) -> dict[str, Any]:
        """Профиль участника и сводка (`GET /participants/{fsp_id}`)."""
        return await self._get(f"/participants/{fsp_id}")

    async def achievements(self, fsp_id: str) -> dict[str, Any]:
        """`{fsp_id, has_history, total, items[], updated_at}`. Без истории — пустой items."""
        return await self._get(f"/participants/{fsp_id}/achievements")

    async def participants_batch(self, fsp_ids: list[str]) -> dict[str, Any]:
        """Пакетно до 100 ID: `{items[], not_found[]}` (для ночной синхронизации)."""
        if not fsp_ids:
            return {"items": [], "not_found": []}
        if len(fsp_ids) > MAX_BATCH:
            raise ValueError(f"Не больше {MAX_BATCH} ID за запрос")
        return await self._get("/participants", params={"ids": ",".join(fsp_ids)})


def parse_updated_at(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def get_registry_client() -> RegistryClient:
    """Зависимость FastAPI: клиент реестра из настроек (тесты подменяют её)."""
    fsp = get_fsp_settings()
    return RegistryClient(
        get_settings().fsp_registry_url,
        token=fsp.registry_token,
        timeout=fsp.registry_timeout_sec,
        retries=fsp.registry_retries,
    )

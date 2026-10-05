"""Клиент реестра ФСП: ответы, повторы, ошибки → понятные исключения."""

import asyncio

import httpx
import pytest

from app.fsp.registry import (
    ParticipantNotFoundError,
    RegistryClient,
    RegistryError,
    RegistryUnavailableError,
)
from tests.test_fsp_support import FakeRegistry


def test_achievements_and_batch() -> None:
    reg = FakeRegistry()
    client = reg.client()
    data = asyncio.run(client.achievements("FSP-000001"))
    assert data["has_history"] and data["total"] == 7
    empty = asyncio.run(client.achievements("FSP-000031"))
    assert empty["has_history"] is False and empty["items"] == []
    batch = asyncio.run(client.participants_batch(["FSP-000001", "FSP-000099"]))
    assert [i["fsp_id"] for i in batch["items"]] == ["FSP-000001"]
    assert batch["not_found"] == ["FSP-000099"]


def test_not_found() -> None:
    with pytest.raises(ParticipantNotFoundError):
        asyncio.run(FakeRegistry().client().achievements("FSP-000099"))


def test_network_error_retried_then_unavailable() -> None:
    reg = FakeRegistry(down=True)
    with pytest.raises(RegistryUnavailableError):
        asyncio.run(reg.client().achievements("FSP-000001"))
    assert len(reg.calls) == 2  # 1 попытка + 1 повтор


def test_5xx_retried_then_succeeds() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 3:
            return httpx.Response(503, json={})
        return httpx.Response(200, json={"fsp_id": "FSP-000001", "items": []})

    client = RegistryClient(
        "http://r", retries=2, retry_pause=0, transport=httpx.MockTransport(handler)
    )
    assert asyncio.run(client.achievements("FSP-000001"))["items"] == []
    assert len(attempts) == 3


def test_4xx_not_retried_and_token_sent() -> None:
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Authorization"))
        return httpx.Response(401, json={"code": "unauthorized"})

    client = RegistryClient(
        "http://r", token="t0k", retries=3, retry_pause=0, transport=httpx.MockTransport(handler)
    )
    with pytest.raises(RegistryError) as exc:
        asyncio.run(client.participant("FSP-000001"))
    assert exc.value.status == 401 and not isinstance(exc.value, RegistryUnavailableError)
    assert seen == ["Bearer t0k"]


def test_timeout_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = RegistryClient("http://r", retries=0, transport=httpx.MockTransport(handler))
    with pytest.raises(RegistryUnavailableError):
        asyncio.run(client.achievements("FSP-000001"))


def test_batch_limit() -> None:
    with pytest.raises(ValueError):
        asyncio.run(
            FakeRegistry().client().participants_batch([f"FSP-{i:06d}" for i in range(101)])
        )

"""Общие помощники тестов модуля ФСП (тестов в этом файле нет).

- БД: минимальные строки users/candidate_profiles из фикстур (пока нет загрузчика 2b) и ФСП-часть
  сида через `load_fsp_fixtures`. Базовое состояние: кандидат 1 ↔ FSP-000001 (с историей),
  2 ↔ FSP-000002, 21 ↔ FSP-000031 (без истории), 26 — без ФСП ID. Модули тестов восстанавливают
  его до и после себя — на нём же работает test_routers.
- Фейковый реестр (httpx.MockTransport по данным мока) и фейковый Keycloak с настоящей
  проверкой PKCE и ID-токенами, подписанными тестовым RSA-ключом.
"""

import asyncio
import base64
import hashlib
import json
import time
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.candidates.models import CandidateProfile
from app.common import fixtures
from app.core.config import REPO_ROOT, get_settings
from app.fsp.fixtures_loader import load_fsp_fixtures
from app.fsp.models import FspAchievement, FspLink
from app.fsp.oidc import KeycloakClient
from app.fsp.registry import RegistryClient
from app.users.models import User

BASE_CANDIDATES = [1, 2, 21, 26]
REGISTRY_JSON = REPO_ROOT / "services" / "fsp-registry-mock" / "data" / "participants.json"
PUBLIC_KC = "http://kc-public.test"
INTERNAL_KC = "http://kc-internal.test"
REALM = "fsp"
CLIENT_ID = "fsp-talent"
ISSUER = f"{PUBLIC_KC}/realms/{REALM}"


# ---------------------------------------------------------------- БД


def run_db[T](fn: Callable[[AsyncSession], Awaitable[T]]) -> T:
    """Выполнить fn(session) в отдельном движке (у TestClient свой цикл событий)."""

    async def main() -> T:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        try:
            maker = async_sessionmaker(engine, expire_on_commit=False)
            async with maker() as session:
                return await fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(main())


async def ensure_candidates(session: AsyncSession, ids: list[int]) -> None:
    """Минимальные строки users + candidate_profiles из фикстур (существующие не трогаем)."""
    for cid in ids:
        cand = fixtures.by_id("candidates", cid)
        assert cand is not None
        user = fixtures.by_id("users", cand["user_id"])
        assert user is not None
        await session.execute(
            insert(User)
            .values(
                id=user["id"],
                email=user["email"],
                role=user["role"],
                full_name=user["full_name"],
                email_verified=True,
                blocked=False,
            )
            .on_conflict_do_nothing()
        )
        await session.execute(
            insert(CandidateProfile)
            .values(
                id=cand["id"],
                user_id=cand["user_id"],
                pseudonym=cand["pseudonym"],
                city=cand["city"],
                work_formats=cand["work_formats"],
                topic_scores=[],
                roles_in_team=cand["roles_in_team"],
                experience_years=cand["experience_years"],
                soft_skills=cand["soft_skills"],
                about=cand["about"],
                links=[],
                privacy=cand["privacy"],
                freshness=cand["freshness"],
                min_salary=cand["min_salary"],
            )
            .on_conflict_do_nothing()
        )
    for table, model in (("users", User), ("candidate_profiles", CandidateProfile)):
        max_id = (await session.execute(select(func.max(model.id)))).scalar_one()
        await session.execute(
            text("SELECT setval(pg_get_serial_sequence(:t, 'id'), :v)"), {"t": table, "v": max_id}
        )
    await session.commit()


async def _reset(session: AsyncSession) -> None:
    await ensure_candidates(session, BASE_CANDIDATES)
    await session.execute(delete(FspLink).where(FspLink.candidate_id.in_(BASE_CANDIDATES)))
    await session.commit()
    await load_fsp_fixtures(session, BASE_CANDIDATES)


def reset_baseline() -> None:
    run_db(_reset)


@pytest.fixture(scope="module")
def fsp_db() -> Iterator[None]:
    reset_baseline()
    yield
    reset_baseline()


def db_link(candidate_id: int) -> FspLink | None:
    async def q(s: AsyncSession) -> FspLink | None:
        stmt = select(FspLink).where(FspLink.candidate_id == candidate_id)
        return (await s.execute(stmt)).scalar_one_or_none()

    return run_db(q)


def db_achievements(fsp_id: str) -> list[FspAchievement]:
    async def q(s: AsyncSession) -> list[FspAchievement]:
        stmt = select(FspAchievement).where(FspAchievement.fsp_id == fsp_id)
        return list((await s.execute(stmt)).scalars())

    return run_db(q)


def db_unlink(candidate_id: int) -> None:
    async def q(s: AsyncSession) -> None:
        await s.execute(delete(FspLink).where(FspLink.candidate_id == candidate_id))
        await s.commit()

    run_db(q)


# ---------------------------------------------------------------- фейковый реестр


@dataclass
class FakeRegistry:
    """Реестр по данным мока. down=True — сеть недоступна; calls — журнал путей."""

    down: bool = False
    status_5xx: bool = False
    updated_at: dict[str, str] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        raw = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
        self.default_updated = raw["meta"]["updated_at"]
        self.people: dict[str, dict[str, Any]] = {p["fsp_id"]: p for p in raw["participants"]}

    def _profile(self, fsp_id: str) -> dict[str, Any]:
        p = {k: v for k, v in self.people[fsp_id].items() if k != "achievements"}
        p["has_history"] = bool(self.people[fsp_id]["achievements"])
        p["updated_at"] = self.updated_at.get(fsp_id, self.default_updated)
        return p

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request.url.path)
        if self.down:
            raise httpx.ConnectError("connection refused", request=request)
        if self.status_5xx:
            return httpx.Response(502, json={"code": "bad_gateway"})
        parts = request.url.path.strip("/").split("/")
        if parts == ["participants"]:
            ids = request.url.params["ids"].split(",")
            items = [self._profile(i) for i in ids if i in self.people]
            return httpx.Response(
                200, json={"items": items, "not_found": [i for i in ids if i not in self.people]}
            )
        fsp_id = parts[1]
        if fsp_id not in self.people:
            return httpx.Response(404, json={"code": "participant_not_found", "message": "нет"})
        if len(parts) == 3:
            achs = self.people[fsp_id]["achievements"]
            body = {
                "fsp_id": fsp_id,
                "has_history": bool(achs),
                "total": len(achs),
                "items": achs,
                "updated_at": self._profile(fsp_id)["updated_at"],
            }
            return httpx.Response(200, json=body)
        return httpx.Response(200, json=self._profile(fsp_id))

    def client(self) -> RegistryClient:
        return RegistryClient(
            "http://registry.test",
            retries=1,
            retry_pause=0,
            transport=httpx.MockTransport(self.handler),
        )


# ---------------------------------------------------------------- фейковый Keycloak

TEST_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_id_token(claims: dict[str, Any], key: rsa.RSAPrivateKey = TEST_KEY) -> str:
    now = int(time.time())
    base = {"iss": ISSUER, "aud": CLIENT_ID, "azp": CLIENT_ID, "sub": "kc-user", "iat": now}
    base["exp"] = now + 300
    return jwt.encode({**base, **claims}, key, algorithm="RS256", headers={"kid": "test"})


def s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


@dataclass
class FakeKeycloak:
    """Keycloak на MockTransport: discovery, token (с проверкой PKCE) и ключ для ID-токена."""

    down: bool = False
    codes: dict[str, dict[str, str]] = field(default_factory=dict)
    token_requests: list[dict[str, str]] = field(default_factory=list)

    def issue_code(self, authorize_url: str, fsp_id: str, code: str = "code-1") -> str:
        """«Пользователь вошёл»: запоминаем challenge и nonce из адреса входа, выдаём код."""
        query = {k: v[0] for k, v in parse_qs(urlparse(authorize_url).query).items()}
        self.codes[code] = {
            "challenge": query["code_challenge"],
            "nonce": query["nonce"],
            "redirect_uri": query["redirect_uri"],
            "fsp_id": fsp_id,
        }
        return query["state"]

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("connection refused", request=request)
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(200, json={"issuer": ISSUER})
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        self.token_requests.append(form)
        grant = self.codes.pop(form.get("code", ""), None)
        if (
            grant is None
            or s256(form.get("code_verifier", "")) != grant["challenge"]
            or form.get("redirect_uri") != grant["redirect_uri"]
        ):
            return httpx.Response(400, json={"error": "invalid_grant"})
        token = make_id_token(
            {"nonce": grant["nonce"], "fsp_id": grant["fsp_id"], "sub": f"sub-{grant['fsp_id']}"}
        )
        return httpx.Response(200, json={"id_token": token, "access_token": "at"})

    def client(self) -> KeycloakClient:
        return KeycloakClient(
            public_url=PUBLIC_KC,
            internal_url=INTERNAL_KC,
            realm=REALM,
            client_id=CLIENT_ID,
            transport=httpx.MockTransport(self.handler),
            key_resolver=lambda _token: TEST_KEY.public_key(),
        )

"""ФСП ID: PKCE, state в cookie, проверка ID-токена, клиент Keycloak (без настоящего Keycloak)."""

import asyncio
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import jwt
import pytest

from app.fsp.oidc import (
    IdTokenVerifier,
    KeycloakClient,
    KeycloakUnavailableError,
    OidcError,
    OidcState,
    code_challenge_s256,
    decode_state,
    encode_state,
    make_code_verifier,
)
from tests.test_fsp_support import (
    CLIENT_ID,
    ISSUER,
    OTHER_KEY,
    TEST_KEY,
    FakeKeycloak,
    make_id_token,
)


def verifier() -> IdTokenVerifier:
    return IdTokenVerifier(ISSUER, CLIENT_ID, lambda _t: TEST_KEY.public_key())


# ---------------------------------------------------------------- PKCE


def test_pkce_rfc7636_vector() -> None:
    # пример из RFC 7636, приложение B
    assert (
        code_challenge_s256("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")
        == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )


def test_code_verifier_length_and_randomness() -> None:
    values = {make_code_verifier() for _ in range(20)}
    assert len(values) == 20
    assert all(43 <= len(v) <= 128 for v in values)


# ---------------------------------------------------------------- state


def test_state_roundtrip() -> None:
    st = OidcState.new("link", "http://localhost:15173/auth/fsp-callback")
    got = decode_state(encode_state(st), st.state, "link")
    assert got == st


def test_state_expired() -> None:
    st = OidcState.new("login", "http://x/cb")
    cookie = encode_state(st, ttl_sec=600, now=time.time() - 601)
    with pytest.raises(OidcError) as exc:
        decode_state(cookie, st.state, "login")
    assert exc.value.reason == "state_expired"


def test_state_substituted() -> None:
    st = OidcState.new("login", "http://x/cb")
    cookie = encode_state(st)
    with pytest.raises(OidcError) as exc:
        decode_state(cookie, "attacker-state", "login")
    assert exc.value.reason == "state_mismatch"


def test_state_cookie_tampered_or_missing() -> None:
    st = OidcState.new("login", "http://x/cb")
    cookie = encode_state(st)
    forged = jwt.encode({"st": st.state, "exp": time.time() + 60, "iat": time.time()}, "other")
    for bad in (cookie[:-3] + "abc", forged):
        with pytest.raises(OidcError) as exc:
            decode_state(bad, st.state, "login")
        assert exc.value.reason == "state_invalid"
    with pytest.raises(OidcError) as exc:
        decode_state(None, st.state, "login")
    assert exc.value.reason == "state_missing"


def test_state_purpose_mismatch() -> None:
    st = OidcState.new("login", "http://x/cb")
    with pytest.raises(OidcError) as exc:
        decode_state(encode_state(st), st.state, "link")
    assert exc.value.reason == "purpose_mismatch"


# ---------------------------------------------------------------- ID-токен


def test_id_token_valid() -> None:
    identity = verifier().verify(make_id_token({"fsp_id": "FSP-000002", "nonce": "n1"}), "n1")
    assert identity.fsp_id == "FSP-000002"
    assert identity.sub == "kc-user"


@pytest.mark.parametrize(
    ("claims", "key", "reason"),
    [
        ({}, OTHER_KEY, "id_token_invalid"),  # чужая подпись
        ({"iss": "http://evil/realms/fsp"}, TEST_KEY, "id_token_invalid"),
        ({"aud": "other-client"}, TEST_KEY, "id_token_invalid"),
        ({"azp": "other-client"}, TEST_KEY, "id_token_invalid"),
        ({"exp": int(time.time()) - 3600}, TEST_KEY, "id_token_expired"),
        ({"nonce": "other"}, TEST_KEY, "id_token_invalid"),
        ({"fsp_id": None}, TEST_KEY, "fsp_id_missing"),
        ({"fsp_id": "12345"}, TEST_KEY, "fsp_id_missing"),
    ],
)
def test_id_token_rejected(claims: dict[str, Any], key: Any, reason: str) -> None:
    token = make_id_token({"fsp_id": "FSP-000002", "nonce": "n1", **claims}, key)
    with pytest.raises(OidcError) as exc:
        verifier().verify(token, "n1")
    assert exc.value.reason == reason


def test_id_token_hs256_not_accepted() -> None:
    token = jwt.encode(
        {"iss": ISSUER, "aud": CLIENT_ID, "sub": "x", "exp": time.time() + 60, "iat": time.time()},
        "secret",
        algorithm="HS256",
    )
    with pytest.raises(OidcError):
        verifier().verify(token)


def test_jwks_connection_error_is_unavailable() -> None:
    def resolver(_token: str) -> Any:
        raise jwt.PyJWKClientConnectionError("down")

    v = IdTokenVerifier(ISSUER, CLIENT_ID, resolver)
    with pytest.raises(KeycloakUnavailableError):
        v.verify(make_id_token({"fsp_id": "FSP-000001"}))


# ---------------------------------------------------------------- клиент Keycloak


def test_authorize_url_uses_public_address_and_s256() -> None:
    kc = FakeKeycloak().client()
    st = OidcState.new("login", "http://localhost:15173/auth/fsp-callback")
    url = urlparse(kc.authorize_url(st))
    query = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert f"{url.scheme}://{url.netloc}{url.path}" == (
        "http://kc-public.test/realms/fsp/protocol/openid-connect/auth"
    )
    assert query["code_challenge_method"] == "S256"
    assert query["code_challenge"] == code_challenge_s256(st.code_verifier)
    assert query["client_id"] == "fsp-talent" and query["state"] == st.state
    assert "code_verifier" not in query


def test_exchange_uses_internal_address_and_verifier() -> None:
    fake = FakeKeycloak()
    kc = fake.client()
    st = OidcState.new("link", "http://localhost:15173/auth/fsp-callback")
    fake.issue_code(kc.authorize_url(st), "FSP-000003")
    identity = asyncio.run(kc.identity_from_code("code-1", st))
    assert identity.fsp_id == "FSP-000003"
    assert fake.token_requests[0]["code_verifier"] == st.code_verifier
    # повторное использование кода Keycloak отклоняет
    with pytest.raises(OidcError) as exc:
        asyncio.run(kc.identity_from_code("code-1", st))
    assert exc.value.reason == "code_exchange_failed"


def test_wrong_verifier_rejected() -> None:
    fake = FakeKeycloak()
    kc = fake.client()
    st = OidcState.new("link", "http://x/cb")
    fake.issue_code(kc.authorize_url(st), "FSP-000003")
    other = OidcState(st.state, make_code_verifier(), st.nonce, st.purpose, st.redirect_uri)
    with pytest.raises(OidcError):
        asyncio.run(kc.identity_from_code("code-1", other))


def test_keycloak_down() -> None:
    kc = FakeKeycloak(down=True).client()
    with pytest.raises(KeycloakUnavailableError):
        asyncio.run(kc.check_available())
    with pytest.raises(KeycloakUnavailableError):
        asyncio.run(kc.exchange_code("c", OidcState.new("login", "http://x/cb")))


def test_realm_url_accepts_both_forms() -> None:
    a = KeycloakClient(
        public_url="http://h:1", internal_url="http://k:8080/realms/fsp", realm="fsp", client_id="c"
    )
    assert a.internal_realm == "http://k:8080/realms/fsp"
    assert a.public_realm == "http://h:1/realms/fsp"

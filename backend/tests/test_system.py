"""Health, единый формат ошибок, заглушка ролей, OpenAPI."""

import json

from fastapi.testclient import TestClient

from app.core.config import REPO_ROOT
from app.main import app
from tests.conftest import ADMIN, CANDIDATE, RECRUITER


def test_health_checks_db_and_migration(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["db_revision"] == "0001"


def test_docs_available(client: TestClient) -> None:
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/openapi.json").status_code == 200


def test_missing_role_is_401_in_error_format(client: TestClient) -> None:
    response = client.get("/api/candidates/me/profile")
    assert response.status_code == 401
    assert response.json() == {"code": "unauthorized", "message": "Требуется вход", "details": {}}


def test_wrong_role_is_403(client: TestClient) -> None:
    response = client.get("/api/admin/dashboard", headers=CANDIDATE)
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_unknown_path_is_404_in_error_format(client: TestClient) -> None:
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert set(response.json()) == {"code", "message", "details"}


def test_validation_error_format(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"email": "not-an-email"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["details"]["errors"]


def test_user_id_must_match_role(client: TestClient) -> None:
    response = client.get("/api/auth/me", headers={"X-Demo-Role": "admin", "X-Demo-User-Id": "1"})
    assert response.status_code == 401


def test_every_operation_has_model_and_errors() -> None:
    schema = app.openapi()
    for path, methods in schema["paths"].items():
        for method, op in methods.items():
            responses = op["responses"]
            ok = next(code for code in responses if code.startswith("2"))
            if ok != "204" and not path.endswith(".pdf"):
                content = responses[ok].get("content", {}).get("application/json", {})
                assert "schema" in content, f"{method} {path}: нет схемы ответа"
            protected = any(p["name"] == "X-Demo-Role" for p in op.get("parameters", []))
            if protected and path != "/api/health":
                assert "401" in responses, f"{method} {path}: не описан 401"


def test_exported_openapi_is_up_to_date() -> None:
    exported = REPO_ROOT / "docs" / "api" / "openapi.json"
    assert exported.exists(), "Выгрузите схему: python scripts/export_openapi.py"
    assert json.loads(exported.read_text(encoding="utf-8")) == app.openapi(), (
        "docs/api/openapi.json устарел — перевыгрузите: python scripts/export_openapi.py"
    )


def test_roles_resolve_to_demo_accounts(client: TestClient) -> None:
    for headers, role in ((CANDIDATE, "candidate"), (RECRUITER, "recruiter"), (ADMIN, "admin")):
        me = client.get("/api/auth/me", headers=headers).json()
        assert me["role"] == role

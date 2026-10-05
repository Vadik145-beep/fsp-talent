import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "participants": 40, "synthetic": True}


def test_participant_with_history(client):
    r = client.get("/participants/FSP-000001")
    assert r.status_code == 200
    body = r.json()
    assert body["fsp_id"] == "FSP-000001"
    assert body["has_history"] is True
    assert body["full_name"]
    assert body["summary"]["achievements_count"] >= 1
    assert body["summary"]["best_level"] in {"regional", "national", "international"}


def test_all_ids_ranges(client):
    for n in range(1, 41):
        fsp_id = f"FSP-{n:06d}"
        body = client.get(f"/participants/{fsp_id}/achievements").json()
        assert body["fsp_id"] == fsp_id
        if n <= 30:
            assert body["has_history"] is True and body["total"] >= 1, fsp_id
        else:
            assert body["has_history"] is False
            assert body["items"] == [] and body["total"] == 0


def test_achievement_shape(client):
    items = client.get("/participants/FSP-000001/achievements").json()["items"]
    a = items[0]
    assert set(a) >= {
        "id",
        "competition",
        "discipline",
        "level",
        "date",
        "result",
        "participation",
        "team",
        "rating_points",
        "verified",
    }
    assert a["competition"]["protocol_url"].startswith("https://")
    assert a["discipline"]["code"] in {"product", "algorithmic", "security", "uav", "robotics"}
    dates = [x["date"] for x in items]
    assert dates == sorted(dates)
    for x in items:
        assert (x["team"] is None) == (x["participation"] == "individual")


def test_no_history_profile(client):
    body = client.get("/participants/FSP-000031").json()
    assert body["has_history"] is False
    assert body["summary"] == {
        "achievements_count": 0,
        "rating_points_total": 0,
        "disciplines": [],
        "best_level": None,
        "prizes_count": 0,
        "last_achievement_date": None,
    }


def test_unknown_participant_404(client):
    for path in ("/participants/FSP-000041", "/participants/FSP-999999/achievements"):
        r = client.get(path)
        assert r.status_code == 404
        assert r.json()["code"] == "participant_not_found"
        assert "message" in r.json() and "details" in r.json()


def test_invalid_id_422(client):
    r = client.get("/participants/12345")
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_fsp_id"


def test_lowercase_id_accepted(client):
    assert client.get("/participants/fsp-000002").json()["fsp_id"] == "FSP-000002"


def test_filters(client):
    all_items = client.get("/participants/FSP-000001/achievements").json()["items"]
    r = client.get("/participants/FSP-000001/achievements", params={"level": "national"})
    assert r.status_code == 200
    filtered = r.json()["items"]
    assert filtered and all(x["level"]["code"] == "national" for x in filtered)
    assert len(filtered) <= len(all_items)
    bad = client.get("/participants/FSP-000001/achievements", params={"level": "city"})
    assert bad.status_code == 422 and bad.json()["code"] == "validation_error"


def test_batch(client):
    r = client.get("/participants", params={"ids": "FSP-000001,FSP-000031,FSP-000077,FSP-000001"})
    assert r.status_code == 200
    body = r.json()
    assert [p["fsp_id"] for p in body["items"]] == ["FSP-000001", "FSP-000031"]
    assert body["not_found"] == ["FSP-000077"]


def test_batch_limits(client):
    ids = ",".join(f"FSP-{n:06d}" for n in range(1, 102))
    r = client.get("/participants", params={"ids": ids})
    assert r.status_code == 422 and r.json()["code"] == "too_many_ids"
    assert client.get("/participants", params={"ids": ","}).status_code == 422
    assert client.get("/participants").status_code == 422
    assert client.get("/participants", params={"ids": "abc"}).json()["code"] == "invalid_fsp_id"


def test_dictionaries(client):
    body = client.get("/dictionaries").json()
    assert len(body["disciplines"]) == 5 and len(body["levels"]) == 3


def test_token_required_when_configured(monkeypatch):
    monkeypatch.setenv("FSP_MOCK_API_TOKEN", "secret")
    c = TestClient(create_app())
    assert c.get("/health").status_code == 200
    r = c.get("/participants/FSP-000001")
    assert r.status_code == 401 and r.json()["code"] == "unauthorized"
    ok = c.get("/participants/FSP-000001", headers={"Authorization": "Bearer secret"})
    assert ok.status_code == 200


def test_openapi_in_russian(client):
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"] == "Реестр ФСП (мок)"
    assert "/participants/{fsp_id}/achievements" in spec["paths"]

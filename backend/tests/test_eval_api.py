"""Эндпоинты валидации: графики из results.json и проверка подбора по CSV (T11.6)."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.common import fixtures
from app.eval.service import MAX_BYTES
from app.eval.synthetic import data_dir, load_dataset, load_results
from tests.conftest import ADMIN

FRONT_CHART_IDS = {
    "grade_accuracy",
    "theta_recovery",
    "retest_stability",
    "item_discrimination",
    "test_length",
    "leak_detector",
    "precision_at_10",
    "bank_size",
}


def post_csv(client: TestClient, body: str | bytes, name: str = "pairs.csv") -> dict[str, Any]:
    data = body.encode("utf-8") if isinstance(body, str) else body
    response = client.post(
        "/api/eval/matching", files={"file": (name, data, "text/csv")}, headers=ADMIN
    )
    return {"status": response.status_code, **response.json()}


def test_validation_overview_from_results(client: TestClient) -> None:
    results = load_results()
    assert results is not None, "нет data/validation/results.json — запустите run_all.py"
    body = client.get("/api/eval/validation", headers=ADMIN).json()
    ids = {c["id"] for c in body["charts"]}
    assert ids >= FRONT_CHART_IDS
    assert all(c["is_stub"] is False for c in body["charts"])
    assert body["seed"] == 20261011 and body["generated_at"]
    # цифры графиков — из того же прогона, что и сводка метрик
    p10 = next(c for c in body["charts"] if c["id"] == "precision_at_10")
    assert p10["summary"]["precision_at_10"] == pytest.approx(
        results["metrics"]["matching"]["systems"]["system"]["p10"], abs=1e-4
    )
    one = client.get("/api/eval/charts/leak_detector").json()
    assert one["id"] == "leak_detector" and one["series"]
    missing = client.get("/api/eval/charts/nope")
    assert missing.status_code == 404 and missing.json()["code"] == "not_found"


def test_validation_overview_without_results(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VALIDATION_DIR", str(tmp_path))
    body = client.get("/api/eval/validation").json()
    assert body["charts"] == [] and body["seed"] == 20261011


def test_example_csv_is_ranked_by_platform(client: TestClient) -> None:
    content = (data_dir() / "example_pairs.csv").read_bytes()
    result = post_csv(client, content, "example_pairs.csv")
    assert result["status"] == 200, result
    assert result["ranking"] == "synthetic" and result["is_stub"] is False
    assert result["needs_count"] == 6 and result["pairs_count"] == 240
    expected = load_results()["metrics"]["example_pairs"]  # type: ignore[index]
    for key in (
        "precision_at_10",
        "ndcg_at_10",
        "baseline_precision_at_10",
        "random_precision_at_10",
    ):
        assert result[key] == pytest.approx(expected[key], abs=1e-3)
    assert result["precision_at_10"] > result["random_precision_at_10"]
    assert len(result["per_need"]) == 6


def test_row_order_does_not_matter(client: TestClient) -> None:
    lines = (data_dir() / "example_pairs.csv").read_text(encoding="utf-8").splitlines()
    shuffled = "\n".join([lines[0], *reversed(lines[1:])])
    a = post_csv(client, "\n".join(lines))
    b = post_csv(client, shuffled)
    assert a["precision_at_10"] == b["precision_at_10"]
    assert a["ndcg_at_10"] == b["ndcg_at_10"]


def test_synthetic_without_relevant_uses_gold(client: TestClient) -> None:
    ds = load_dataset()
    need = "N001"
    rel = [c for (n, c), v in ds.gold.items() if n == need and v == 2][:5]
    others = [c for c in list(ds.candidates)[:40] if (need, c) not in ds.gold][:15]
    body = "need_id;candidate_id\n" + "\n".join(f"{need};{c}" for c in rel + others)
    result = post_csv(client, body)
    assert result["status"] == 200, result
    assert result["ranking"] == "synthetic"
    assert result["per_need"][0]["relevant_total"] == len(rel)


def test_platform_ids_are_ranked_by_matching(client: TestClient) -> None:
    """Потребность 1 (backend:middle) и 12 кандидатов сида: без relevant подходящий = та же
    категория; платформа ставит свою категорию первой, поэтому все подходящие в топ-10."""
    candidates = fixtures.load("candidates")[:12]
    same = [c["id"] for c in candidates if c.get("category") == "backend:middle"]
    assert same
    body = "need_id,candidate_id\n" + "\n".join(f"1,{c['id']}" for c in candidates)
    result = post_csv(client, body)
    assert result["status"] == 200, result
    assert result["ranking"] == "platform"
    assert result["per_need"][0]["relevant_total"] == len(same)
    assert result["relevant_in_top_share"] == 1.0
    assert result["recall_at_50"] == 1.0


def test_unknown_ids_evaluate_file_order(client: TestClient) -> None:
    body = "need_id,candidate_id,relevant\nX1,a,1\nX1,b,0\nX1,c,1\nX2,d,0\nX2,e,1\n"
    result = post_csv(client, body)
    assert result["status"] == 200, result
    assert result["ranking"] == "file_order" and result["warnings"]
    assert result["pairs_count"] == 5 and result["needs_count"] == 2
    # X1: [1, 0, 1] → P = 2/3; X2: [0, 1] → P = 1/2
    assert result["precision_at_10"] == pytest.approx((2 / 3 + 1 / 2) / 2, abs=1e-3)
    no_rel = post_csv(client, "need_id,candidate_id\nX1,a\n")
    assert no_rel["status"] == 422 and no_rel["code"] == "invalid_csv"


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ("a,b\n1,2\n", "invalid_csv"),
        ("need_id,candidate_id\n", "invalid_csv"),
        ("need_id,candidate_id,relevant\nN001,C0001,5\n", "invalid_csv"),
        ("need_id,candidate_id,relevant\nN001,,1\n", "invalid_csv"),
    ],
)
def test_bad_csv(client: TestClient, body: str, code: str) -> None:
    result = post_csv(client, body)
    assert result["status"] == 422 and result["code"] == code


def test_not_utf8_and_too_large(client: TestClient) -> None:
    bad = post_csv(client, "need_id,candidate_id\nПотр,1\n".encode("cp1251"))
    assert bad["status"] == 422
    big = b"need_id,candidate_id\n" + b"N001,C0001\n" * (MAX_BYTES // 11 + 10)
    large = post_csv(client, big)
    assert large["status"] == 413 and large["code"] == "file_too_large"


def test_results_json_is_valid() -> None:
    data = json.loads((data_dir() / "results.json").read_text(encoding="utf-8"))
    assert {"generated_at", "seed", "charts", "metrics"} <= set(data)
    cfg = data["metrics"]["config"]
    assert cfg["candidates"] >= 1000 and cfg["needs"] == 100

from fastapi.testclient import TestClient

from app.common import fixtures
from tests.conftest import CANDIDATE, as_role


def test_testing_flow(client: TestClient) -> None:
    survey = client.get("/api/testing/survey", headers=CANDIDATE).json()
    assert len(survey) == len(fixtures.load("survey_questions"))
    result = client.post(
        "/api/testing/survey",
        json={"answers": [{"question_id": "q1", "option_ids": ["q1_data"]}]},
        headers=CANDIDATE,
    ).json()
    assert result["recommended_specialization"] == "data_ml"
    # кандидат 14 провалил тест на Middle 25.09 — повтор на тот же грейд через 30 дней
    cand14 = as_role("candidate", 14)
    blocked = client.post(
        "/api/testing/sessions",
        json={"specialization": "backend", "target_grade": "middle", "kind": "higher"},
        headers=cand14,
    )
    assert blocked.status_code == 409 and blocked.json()["code"] == "cooldown_active"
    assert blocked.json()["details"]["reason_code"] == "failed_retry_cooldown"
    grade = client.get("/api/testing/grade", headers=cand14).json()
    assert grade["can_test_higher"] is False and grade["higher_available_at"]
    finished = next(s for s in client.get("/api/testing/sessions", headers=CANDIDATE).json())
    res = client.get(f"/api/testing/sessions/{finished['id']}/result", headers=CANDIDATE).json()
    assert res["category"] == "backend:middle"
    assert "correct_answer" not in str(res)

"""ФСП-скор и бейджи (T5.3): формула из docs/integration/fsp.md и согласованность с фикстурами."""

from datetime import date

import pytest

from app.common import fixtures
from app.fsp.scoring import (
    FspAchievementData,
    freshness,
    fsp_badges,
    fsp_reason,
    fsp_score,
    raw_score,
    result_weight,
    summarize,
)

TODAY = date(2026, 10, 6)  # «сейчас» генератора фикстур


def achs_of(fsp_id: str) -> list[FspAchievementData]:
    rows = fixtures.where("fsp_achievements", fsp_id=fsp_id)
    return [FspAchievementData.from_mapping(r) for r in rows]


def ach(level: str = "regional", **kw: object) -> FspAchievementData:
    return FspAchievementData.from_mapping({"level": level, "date": "2026-10-01", **kw})


@pytest.mark.parametrize(
    ("fsp_id", "s", "score"),
    [("FSP-000001", 5.88, 86.0), ("FSP-000005", 0.82, 24.0), ("FSP-000007", 0.14, 5.0)],
)
def test_examples_from_docs(fsp_id: str, s: float, score: float) -> None:
    achs = achs_of(fsp_id)
    assert round(raw_score(achs, TODAY), 2) == s
    assert fsp_score(achs, TODAY) == score


def test_result_weights() -> None:
    assert result_weight(1, None) == 1.0
    assert result_weight(2, None) == 0.85
    assert result_weight(3, None) == 0.7
    assert result_weight(7, None) == 0.4
    assert result_weight(11, None) == 0.25
    assert result_weight(None, "Диплом I степени") == 0.8
    assert result_weight(None, "Диплом II степени") == 0.6
    assert result_weight(None, "Диплом III степени") == 0.45
    assert result_weight(None, None) == 0.1


def test_freshness_halves_in_two_years() -> None:
    assert freshness(TODAY, TODAY) == 1.0
    assert freshness(date(2024, 10, 6), TODAY) == pytest.approx(0.5, abs=0.001)
    assert freshness(date(2027, 1, 1), TODAY) == 1.0  # дата в будущем — как сегодня


def test_saturation_many_participations_lose_to_one_win() -> None:
    win = [ach("national", place=1)]
    participations = [ach("national") for _ in range(9)]  # участие весит 0,1 от победы
    assert (fsp_score(win, TODAY) or 0) > (fsp_score(participations, TODAY) or 0)
    one, two = fsp_score(win, TODAY) or 0, fsp_score(win * 2, TODAY) or 0
    assert two - one < one  # вторая победа добавляет меньше первой
    many_wins = [ach("international", place=1) for _ in range(20)]
    assert fsp_score(many_wins, TODAY) == 100.0
    assert 0 < (fsp_score([ach()], TODAY) or 0) < 100


def test_no_history_is_none_not_zero() -> None:
    assert fsp_score([], TODAY) is None
    assert fsp_badges([]) == []
    assert fsp_reason([], TODAY) is None
    neutral = summarize(26, None, [])
    assert not neutral.linked and neutral.fsp_score is None and not neutral.has_history
    linked_empty = summarize(21, "FSP-000031", [])
    assert linked_empty.linked and linked_empty.fsp_score is None and linked_empty.badges == []


def test_badges() -> None:
    achs = [
        ach("national", diploma="Диплом II степени"),
        ach("international", place=1, role="Капитан, бэкенд-разработчик"),
        ach("regional", place=15),
    ]
    badges = fsp_badges(achs)
    assert [b["id"] for b in badges] == [
        "international_winner",
        "national_prize",
        "captain",
        "participant_many",
    ]
    assert badges[1]["title"] == "Призёр всероссийского соревнования"
    assert badges[-1]["title"] == "Участник 3 соревнований ФСП"
    assert all(b["verified"] for b in badges)
    assert [b["id"] for b in fsp_badges([ach(place=20)])] == ["participant"]


def test_reason_names_best_result() -> None:
    achs = [ach("regional", place=40), ach("national", place=2, discipline="product")]
    assert fsp_reason(achs, TODAY) == (
        "Призёр всероссийского соревнования по продуктовому программированию, 2026"
    )


def test_fixture_scores_and_badges_match_backend_formula() -> None:
    """Генератор фикстур дублирует формулу — значения в candidates.json совпадают с модулем."""
    for cand in fixtures.load("candidates"):
        achs = achs_of(cand["fsp_id"]) if cand["fsp_id"] else []
        assert cand["fsp_score"] == fsp_score(achs, TODAY), cand["id"]
        assert cand["fsp_badges"] == fsp_badges(achs), cand["id"]


def test_fixture_names_come_from_registry() -> None:
    import json

    from app.core.config import REPO_ROOT

    raw = json.loads(
        (REPO_ROOT / "services/fsp-registry-mock/data/participants.json").read_text(
            encoding="utf-8"
        )
    )
    people = {p["fsp_id"]: p for p in raw["participants"]}
    for cand in fixtures.load("candidates"):
        if cand["fsp_id"]:
            p = people[cand["fsp_id"]]
            assert cand["full_name"] == f"{p['first_name']} {p['last_name']}"
            assert len(achs_of(cand["fsp_id"])) == len(p["achievements"])
    demo = fixtures.by_id("candidates", 1)
    assert demo is not None and demo["fsp_id"] == "FSP-000001" and demo["fsp_badges"]
    no_fsp = fixtures.by_id("candidates", 26)
    assert no_fsp is not None and no_fsp["fsp_id"] is None and no_fsp["fsp_score"] is None

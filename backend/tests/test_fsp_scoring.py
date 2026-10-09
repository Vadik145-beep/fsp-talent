"""ФСП-скор и бейджи (T5.3): формула из docs/integration/fsp.md и согласованность с фикстурами."""

from datetime import date

import pytest

from app.common import fixtures
from app.fsp.scoring import (
    DISCIPLINE_RELEVANCE,
    FspAchievementData,
    discipline_relevance,
    freshness,
    fsp_badges,
    fsp_profile_note,
    fsp_reason,
    fsp_reason_for,
    fsp_score,
    fsp_score_for,
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


# ---------------------------------------------------------------- релевантность дисциплин (E08)

SPECS = ("backend", "frontend", "mobile", "data_ml", "qa", "devops")
DISCIPLINES = ("product", "algorithmic", "cybersecurity", "uas", "robotics")


def test_relevance_table_covers_everything_and_never_zero() -> None:
    assert set(DISCIPLINE_RELEVANCE) == set(DISCIPLINES)
    for discipline in DISCIPLINES:
        assert set(DISCIPLINE_RELEVANCE[discipline]) == set(SPECS)
        for spec in SPECS:
            assert 0 < discipline_relevance(discipline, spec) <= 1
    # продуктовое и алгоритмическое полезно всем
    assert min(DISCIPLINE_RELEVANCE["product"].values()) >= 0.7
    assert min(DISCIPLINE_RELEVANCE["algorithmic"].values()) >= 0.6
    # ИБ — сильнее для DevOps/QA/Backend, БАС и робототехника — для Data/ML и Mobile
    ib = DISCIPLINE_RELEVANCE["cybersecurity"]
    assert min(ib["devops"], ib["qa"], ib["backend"]) > max(ib["frontend"], ib["mobile"])
    for d in ("uas", "robotics"):
        row = DISCIPLINE_RELEVANCE[d]
        assert min(row["data_ml"], row["mobile"]) > max(row["backend"], row["frontend"])
    assert discipline_relevance("product", None) == 1.0
    assert discipline_relevance("unknown", "backend") == 1.0


def test_profile_discipline_scores_higher_for_need_specialization() -> None:
    ib = [ach("national", place=2, discipline="cybersecurity")]
    robo = [ach("national", place=2, discipline="robotics")]
    assert fsp_score(ib, TODAY) == fsp_score(robo, TODAY)  # общий скор одинаковый
    devops_ib, devops_robo = (
        fsp_score_for(ib, "devops", TODAY),
        fsp_score_for(robo, "devops", TODAY),
    )
    assert devops_ib is not None and devops_robo is not None and devops_ib > devops_robo > 0
    ml_ib, ml_robo = fsp_score_for(ib, "data_ml", TODAY), fsp_score_for(robo, "data_ml", TODAY)
    assert ml_ib is not None and ml_robo is not None and ml_robo > ml_ib
    # коэффициент 1 и «без специализации» — как общий скор; нет истории — None (без штрафа)
    assert fsp_score_for(ib, "devops", TODAY) == fsp_score(ib, TODAY)
    assert fsp_score_for(robo, None, TODAY) == fsp_score(robo, TODAY)
    assert fsp_score_for([], "devops", TODAY) is None


def test_reason_and_note_mark_profile_discipline() -> None:
    ib = ach("national", place=2, discipline="cybersecurity", date="2025-05-01")
    robo = ach("international", place=1, discipline="robotics", date="2026-05-01")
    reason = fsp_reason_for([ib], "devops", TODAY)
    assert reason == (
        "Призёр всероссийского соревнования по программированию систем ИБ, 2025 — "
        "профильно для DevOps"
    )
    assert fsp_reason_for([robo], "devops", TODAY) == (
        "Победитель международного соревнования по программированию робототехники, 2026"
    )
    assert fsp_reason_for([ib], None, TODAY) == fsp_reason([ib], TODAY)
    # пометка у бейджей — только по профильной дисциплине, даже если есть более сильный результат
    assert fsp_profile_note([ib, robo], "devops", TODAY) == reason
    assert fsp_profile_note([robo], "devops", TODAY) is None
    assert fsp_profile_note([robo], "data_ml", TODAY) == (
        "Победитель международного соревнования по программированию робототехники, 2026 — "
        "профильно для Data Science / ML"
    )
    assert fsp_profile_note([ib], None, TODAY) is None


def test_summary_keeps_achievements_for_ranking() -> None:
    achs = achs_of("FSP-000001")
    summary = summarize(1, "FSP-000001", achs, TODAY)
    assert len(summary.achievements) == len(achs)
    assert fsp_score_for(summary.achievements, None, TODAY) == summary.fsp_score
    assert summarize(2, None, []).achievements == []

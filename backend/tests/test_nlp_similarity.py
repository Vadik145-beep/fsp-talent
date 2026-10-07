"""Близость стека кандидата к потребности (точка стыка с подбором 3b)."""

from app.nlp.similarity import matched_skills, related_skills, skill_credit, stack_match


def test_exact_match_is_one() -> None:
    assert stack_match(["python", "postgresql"], ["redis"], ["python", "postgresql", "redis"]) == 1


def test_empty_requirements_are_full_match() -> None:
    assert stack_match([], [], ["go"]) == 1.0
    assert stack_match(["go"], [], []) == 0.25  # обязательный 0, желательного нет → 0,25


def test_weights_required_and_desired() -> None:
    # обязательный закрыт наполовину (0,5 × 0,75), желательный полностью (0,25)
    assert stack_match(["go", "kafka"], ["docker"], ["go", "docker"]) == 0.625


def test_adjacent_technology_gives_partial_credit() -> None:
    assert skill_credit("django", ["fastapi"]) == (0.5, "fastapi")
    exact = stack_match(["django"], [], ["django"])
    near = stack_match(["django"], [], ["fastapi"])
    none = stack_match(["django"], [], ["react"])
    assert exact > near > none
    assert near == 0.625  # 0,75 × 0,5 + 0,25


def test_synonyms_are_normalized() -> None:
    assert stack_match(["PostgreSQL"], [], ["постгрес"]) == 1.0
    assert matched_skills(["postgresql", "go"], ["PG", "python"]) == ["postgresql"]


def test_deterministic_and_bounded() -> None:
    args = (["go", "kafka", "postgresql"], ["redis", "docker"], ["rabbitmq", "mysql", "docker"])
    values = {stack_match(*args) for _ in range(5)}
    assert len(values) == 1
    assert 0.0 <= values.pop() <= 1.0


def test_matched_keeps_required_order_and_related() -> None:
    assert matched_skills(["redis", "python", "go"], ["go", "python"]) == ["python", "go"]
    assert related_skills(["django", "go"], ["fastapi"]) == {"django": "fastapi"}

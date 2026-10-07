"""Справочник синонимов стека и смежность технологий (трек 3c)."""

import pytest

from app.nlp.skills_lexicon import (
    ADJACENCY,
    catalog,
    find_skills,
    is_catalog,
    normalize_skill,
    similarity,
)


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("постгрес", "postgresql"),
        ("PG", "postgresql"),
        ("postgres", "postgresql"),
        ("PostgreSQL", "postgresql"),
        ("реакт", "react"),
        ("React.js", "react"),
        ("джава", "java"),
        ("питон", "python"),
        ("кубер", "kubernetes"),
        ("k8s", "kubernetes"),
        ("тайпскрипт", "typescript"),
        ("Vue.js", "vue"),
        ("вью", "vue"),
        ("GitLab CI", "gitlab_ci"),
        ("гитлаб", "gitlab_ci"),
        ("Redux Toolkit", "redux"),
        ("HTML", "html_css"),
        ("CSS", "html_css"),
        ("scikit-learn", "scikit_learn"),
        ("sklearn", "scikit_learn"),
        ("C#", "csharp"),
        ("Node.js", "nodejs"),
        ("Apache Airflow", "airflow"),
        ("Celery", "celery"),
        ("Nuxt", "nuxt"),
    ],
)
def test_normalize_synonyms(name: str, code: str) -> None:
    assert normalize_skill(name) == code


def test_unknown_skill_is_none() -> None:
    assert normalize_skill("Кобол-2077") is None
    assert normalize_skill("") is None


def test_every_catalog_code_and_label_maps_to_itself() -> None:
    for code, rec in catalog().items():
        assert normalize_skill(code) == code
        if code != "html_css":  # подпись «HTML и CSS» — два синонима, а не один
            assert normalize_skill(rec["label"]) == code, rec["label"]


def test_find_skills_word_boundaries_and_cases() -> None:
    text = (
        "мидл питонист, джанго/постгрес, JavaScript и TypeScript, swift swiftui, "
        "prometheus+grafana, PostgreSQL, React Native, на реакте"
    )
    codes = [m.code for m in find_skills(text)]
    assert codes[:3] == ["python", "django", "postgresql"]
    assert "javascript" in codes and "java" not in codes
    assert "swift" in codes and "swiftui" in codes
    assert "prometheus" in codes and "grafana" in codes
    assert "sql" not in codes  # PostgreSQL не даёт отдельного SQL
    assert "react_native" in codes and "react" in codes


def test_find_skills_marks_catalog_and_extra() -> None:
    found = {m.code: m for m in find_skills("Celery, Redis и Git")}
    assert found["redis"].in_catalog and is_catalog("redis")
    assert not found["celery"].in_catalog and found["celery"].label == "Celery"
    assert "git" in found


def test_no_false_positives_in_plain_russian() -> None:
    text = "Плюсы: ДМС, витамины в офисе, интервью в два этапа, гитара в переговорке"
    assert find_skills(text) == []


def test_similarity_and_adjacency() -> None:
    assert similarity("FastAPI", "Django") == 0.5
    assert similarity("постгрес", "PostgreSQL") == 1.0
    assert similarity("react", "postgresql") == 0.0
    for pair, weight in ADJACENCY.items():
        assert 0 < weight < 1, pair

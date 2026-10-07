"""Опрос по специализации (T4.1): правила → рекомендуемая специализация, грейд и темы теста.

Правила описаны в docs/testing/survey.md. Опрос баллом не оценивается: это подсказка,
кандидат может выбрать другую специализацию и грейд перед тестом.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.testing.engine import GRADE_LABELS, SPECIALIZATIONS

# Вес вопроса: прямые вопросы о предпочтениях весят больше, чем стек и интересы
QUESTION_WEIGHTS: dict[str, float] = {
    "q1": 3.0,  # чем нравится заниматься
    "q2": 1.0,  # технологии (несколько ответов — по 1 за каждый)
    "q3": 2.0,  # какая задача ближе
    "q5": 1.0,  # роль в команде
    "q6": 1.0,  # что интересно изучать
    "q7": 2.0,  # где запускаете код
}
DEFAULT_WEIGHT = 1.0
TEXT_WEIGHT = 0.5  # за каждое ключевое слово специализации в свободном ответе

# Опыт → предлагаемый грейд
EXPERIENCE_GRADE: dict[str, str] = {
    "q4_0": "intern",
    "q4_1": "junior",
    "q4_3": "middle",
    "q4_5": "senior",
}
DEFAULT_GRADE = "junior"

# Варианты ответа, которые поднимают тему справочника в списке тем теста
OPTION_TOPICS: dict[str, tuple[str, ...]] = {
    "q1_api": ("backend.http_api",),
    "q1_ui": ("frontend.js_core",),
    "q1_apps": ("mobile.lifecycle",),
    "q1_data": ("data_ml.ml_basics",),
    "q1_bugs": ("qa.test_design",),
    "q1_infra": ("devops.linux",),
    "q2_python": ("backend.algorithms", "data_ml.sql_data", "qa.automation"),
    "q2_go_java": ("backend.concurrency",),
    "q2_js": ("frontend.js_core", "frontend.typescript"),
    "q2_mobile": ("mobile.language",),
    "q2_sql": ("backend.databases", "data_ml.sql_data"),
    "q2_ml": ("data_ml.ml_basics", "data_ml.deep_learning"),
    "q2_tests": ("qa.automation",),
    "q2_ops": ("devops.containers", "devops.iac"),
    "q3_db": ("backend.databases",),
    "q3_render": ("frontend.react", "frontend.browser"),
    "q3_offline": ("mobile.networking",),
    "q3_model": ("data_ml.metrics",),
    "q3_regress": ("qa.test_design", "qa.process"),
    "q3_deploy": ("devops.ci_cd",),
    "q5_arch": ("backend.architecture",),
    "q6_arch": ("backend.architecture", "devops.containers"),
    "q6_ux": ("frontend.css_layout", "mobile.ui"),
    "q6_dl": ("data_ml.deep_learning",),
    "q6_auto": ("qa.automation",),
    "q6_sec": ("backend.security", "qa.api_testing"),
    "q7_server": ("backend.http_api", "devops.linux"),
    "q7_browser": ("frontend.browser",),
    "q7_phone": ("mobile.ui",),
    "q7_notebook": ("data_ml.statistics",),
}

# Ключевые слова свободного ответа (последний проект): слово → специализация и темы
TEXT_KEYWORDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "api": ("backend", ("backend.http_api",)),
    "rest": ("backend", ("backend.http_api",)),
    "django": ("backend", ("backend.http_api",)),
    "fastapi": ("backend", ("backend.http_api",)),
    "postgres": ("backend", ("backend.databases",)),
    "kafka": ("backend", ("backend.architecture",)),
    "микросервис": ("backend", ("backend.architecture",)),
    "react": ("frontend", ("frontend.react",)),
    "vue": ("frontend", ("frontend.js_core",)),
    "верстк": ("frontend", ("frontend.css_layout",)),
    "typescript": ("frontend", ("frontend.typescript",)),
    "android": ("mobile", ("mobile.lifecycle",)),
    "ios": ("mobile", ("mobile.language",)),
    "flutter": ("mobile", ("mobile.ui",)),
    "модел": ("data_ml", ("data_ml.ml_basics",)),
    "нейросет": ("data_ml", ("data_ml.deep_learning",)),
    "pandas": ("data_ml", ("data_ml.sql_data",)),
    "аналитик": ("data_ml", ("data_ml.statistics",)),
    "тест": ("qa", ("qa.test_design",)),
    "selenium": ("qa", ("qa.automation",)),
    "playwright": ("qa", ("qa.automation",)),
    "нагруз": ("qa", ("qa.performance",)),
    "docker": ("devops", ("devops.containers",)),
    "kubernetes": ("devops", ("devops.containers",)),
    "terraform": ("devops", ("devops.iac",)),
    "ci/cd": ("devops", ("devops.ci_cd",)),
    "мониторинг": ("devops", ("devops.monitoring",)),
}

MAX_TOPICS = 5


@dataclass
class SurveyOutcome:
    specialization: str
    scores: list[tuple[str, float]]
    grade: str
    topics: list[str]
    explanation: list[str] = field(default_factory=list)


def _keywords(text: str) -> list[str]:
    low = text.lower().replace("ё", "е")
    return [kw for kw in TEXT_KEYWORDS if re.search(rf"(?<![a-zа-я]){re.escape(kw)}", low)]


def evaluate(
    questions: Sequence[Mapping[str, Any]],
    answers: Iterable[Mapping[str, Any]],
    *,
    spec_labels: Mapping[str, str],
    topics_by_spec: Mapping[str, Sequence[str]],
    covered_topics: set[str],
) -> SurveyOutcome:
    """Посчитать рекомендацию.

    topics_by_spec — темы справочника по специализациям (в порядке справочника);
    covered_topics — темы, по которым в банке есть рабочие шаблоны (в тест попадут только они).
    """
    options = {o["id"]: (q["id"], o) for q in questions for o in q.get("options", [])}
    votes: dict[str, float] = defaultdict(float)
    topic_votes: dict[str, float] = defaultdict(float)
    chosen: list[str] = []
    first_choice: str | None = None
    texts: list[str] = []
    for answer in answers:
        if answer.get("text"):
            texts.append(str(answer["text"]))
        for opt_id in answer.get("option_ids") or []:
            if opt_id not in options:
                continue
            qid, opt = options[opt_id]
            chosen.append(opt_id)
            weight = QUESTION_WEIGHTS.get(qid, DEFAULT_WEIGHT)
            for spec in opt.get("specializations", []):
                votes[spec] += weight
                if qid == "q1" and first_choice is None:
                    first_choice = spec
            for topic in OPTION_TOPICS.get(opt_id, ()):
                topic_votes[topic] += weight
    found = _keywords(" ".join(texts))
    for kw in found:
        spec, kw_topics = TEXT_KEYWORDS[kw]
        votes[spec] += TEXT_WEIGHT
        for topic in kw_topics:
            topic_votes[topic] += TEXT_WEIGHT

    explanation: list[str] = []
    if votes:
        # при равенстве баллов: сначала ответ на q1, затем порядок справочника
        def rank(spec: str) -> tuple[float, int, int]:
            return (-votes[spec], 0 if spec == first_choice else 1, SPECIALIZATIONS.index(spec))

        ordered = sorted(votes, key=rank)
        best = ordered[0]
        total = sum(votes.values())
        scores = [(s, round(votes[s] / total, 2)) for s in ordered]
        explanation.append(
            f"Больше всего баллов у специализации «{spec_labels.get(best, best)}»: "
            f"{votes[best]:g} из {total:g}"
        )
    else:
        best = "backend"
        scores = [(best, 1.0)]
        explanation.append("По ответам специализацию не определить — выберите её сами")

    grade = next((EXPERIENCE_GRADE[o] for o in chosen if o in EXPERIENCE_GRADE), DEFAULT_GRADE)
    exp_label = next((options[o][1]["label"] for o in chosen if o in EXPERIENCE_GRADE), "не указан")
    explanation.append(f"Предлагаемый грейд {GRADE_LABELS[grade]} — по опыту ({exp_label})")

    spec_topics: list[str] = [t for t in topics_by_spec.get(best, ()) if t in covered_topics]
    boosted = sorted((t for t in spec_topics if topic_votes[t] > 0), key=lambda t: -topic_votes[t])
    rest = [t for t in spec_topics if t not in boosted]
    topics = (boosted + rest)[:MAX_TOPICS]
    if boosted:
        explanation.append("Темы, о которых вы говорили в ответах, — в начале списка")
    if found:
        explanation.append("Учтены слова из описания проекта: " + ", ".join(found))
    explanation.append("Рекомендация не оценивается баллом — специализацию и грейд можно поменять")
    return SurveyOutcome(best, scores, grade, topics, explanation)

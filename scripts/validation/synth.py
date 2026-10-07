"""Синтетические кандидаты и потребности с эталонной разметкой (T11.1, T11.2).

У каждого кандидата есть СКРЫТАЯ правда (истинный уровень θ, истинный грейд, технологии,
которыми он реально владеет) и то, что видит платформа (резюме со стеком, заявленный грейд,
зарплата, форматы, ФСП). Платформа правду не видит: грейд она узнаёт только из теста,
стек — из резюме, где часть технологий забыта, часть написана сленгом («постгрес», «k8s»),
а часть дописана «для ключевых слов».

Эталон релевантности (`relevance`) строится ТОЛЬКО по правде и НЕ совпадает с формулой
ранжирования — правило описано в `relevance()` и в docs/validation/report.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np
from common import GRADE_LABELS, GRADES, SPEC_LABELS, SPECS

from app.fsp.scoring import FspAchievementData, fsp_score
from app.nlp.skills_lexicon import CATALOG_ALIASES, catalog
from app.testing.engine.grading import DEFAULT_THRESHOLDS

REF_DATE = date(2026, 10, 1)  # «сегодня» для свежести достижений ФСП

SPEC_WEIGHTS = [0.24, 0.20, 0.12, 0.16, 0.14, 0.14]

# Кластеры стека: ядро (элемент-кортеж = «одно из») и дополнительные технологии.
Cluster = tuple[str, float, list[str | tuple[str, ...]], list[str]]
CLUSTERS: dict[str, list[Cluster]] = {
    "backend": [
        (
            "python",
            0.30,
            ["python", ("django", "fastapi"), "postgresql"],
            ["redis", "rabbitmq", "kafka", "pytest", "sql"],
        ),
        ("java", 0.20, ["java", "spring", "postgresql"], ["kafka", "kotlin", "redis", "sql"]),
        ("go", 0.15, ["go", "postgresql", "grpc"], ["kafka", "redis", "clickhouse", "kubernetes"]),
        (
            "node",
            0.15,
            ["nodejs", "typescript", ("mongodb", "postgresql")],
            ["graphql", "redis", "kafka"],
        ),
        ("csharp", 0.10, ["csharp", "sql", ("postgresql", "mysql")], ["rabbitmq", "redis"]),
        ("php", 0.10, ["php", "mysql"], ["redis", "nginx", "linux"]),
    ],
    "frontend": [
        (
            "react",
            0.55,
            ["javascript", "typescript", "react", "html_css"],
            ["redux", "nextjs", "jest", "webpack", "vite", "tailwind"],
        ),
        ("vue", 0.30, ["javascript", "vue", "html_css"], ["typescript", "vite", "webpack", "jest"]),
        ("angular", 0.15, ["typescript", "angular", "html_css"], ["javascript", "jest", "webpack"]),
    ],
    "mobile": [
        ("android", 0.40, ["kotlin", "android_sdk"], ["jetpack_compose", "java"]),
        ("ios", 0.35, ["swift", "ios_sdk"], ["swiftui"]),
        ("flutter", 0.15, ["flutter", "dart"], ["kotlin", "swift"]),
        ("rn", 0.10, ["react_native", "javascript"], ["typescript", "react"]),
    ],
    "data_ml": [
        (
            "classic",
            0.40,
            ["python", "pandas", "scikit_learn", "sql"],
            ["numpy", "jupyter", "clickhouse", "postgresql"],
        ),
        ("dl", 0.30, ["python", "pytorch", "numpy"], ["tensorflow", "mlflow", "pandas"]),
        ("de", 0.30, ["python", "sql", "spark", "airflow"], ["kafka", "clickhouse", "postgresql"]),
    ],
    "qa": [
        (
            "py",
            0.30,
            ["python", "pytest", ("selenium", "playwright")],
            ["allure", "postman", "sql"],
        ),
        ("java", 0.25, ["java", "selenium"], ["allure", "testrail", "jmeter"]),
        ("js", 0.20, ["javascript", ("cypress", "playwright")], ["jest", "postman"]),
        ("manual", 0.25, ["postman", "sql", "testrail"], ["jmeter"]),
    ],
    "devops": [
        (
            "k8s",
            0.45,
            ["docker", "kubernetes", "helm", "linux"],
            ["prometheus", "grafana", "gitlab_ci", "terraform"],
        ),
        ("iac", 0.25, ["terraform", "ansible", "linux"], ["aws", "bash", "docker"]),
        (
            "ci",
            0.30,
            [("gitlab_ci", "github_actions"), "docker", "bash", "linux"],
            ["nginx", "prometheus"],
        ),
    ],
}
COMMON: dict[str, list[str]] = {
    "backend": ["docker", "linux", "sql", "kubernetes"],
    "frontend": ["playwright", "graphql", "nodejs"],
    "mobile": [],
    "data_ml": ["docker", "sql"],
    "qa": ["sql", "postman"],
    "devops": ["python", "go", "nginx"],
}

# Рынок: медиана минимальной зарплаты по заявленному грейду (₽/мес) и множитель направления
MARKET = {"intern": 55_000, "junior": 105_000, "middle": 195_000, "senior": 320_000}
SPEC_SALARY = {
    "backend": 1.0,
    "frontend": 0.95,
    "mobile": 1.0,
    "data_ml": 1.08,
    "qa": 0.82,
    "devops": 1.05,
}
SPEC_WORDS = {
    "backend": "Backend-разработчик",
    "frontend": "Frontend-разработчик",
    "mobile": "Mobile-разработчик",
    "data_ml": "Data Scientist / ML-инженер",
    "qa": "QA-инженер",
    "devops": "DevOps-инженер",
}
NEED_SPEC_WORDS = {
    "backend": "бэкенд-разработчик backend",
    "frontend": "фронтенд-разработчик frontend",
    "mobile": "мобильный разработчик mobile",
    "data_ml": "data scientist ml",
    "qa": "тестировщик qa",
    "devops": "devops-инженер devops",
}
ABOUT = [
    "Люблю чистый код и ревью.",
    "Участвовал в запуске продукта с нуля.",
    "Ищу команду с сильной инженерной культурой.",
    "Работал в финтехе и e-commerce.",
    "Готов к релокации.",
    "Менторил стажёров.",
    "Интересны высоконагруженные системы.",
    "",
]
FORMATS = ["remote", "hybrid", "office"]


@dataclass
class Rng:
    g: np.random.Generator

    def p(self, prob: float) -> bool:
        return bool(self.g.random() < prob)

    def pick(self, seq: list[Any], weights: list[float] | None = None) -> Any:
        if weights is None:
            return seq[int(self.g.integers(len(seq)))]
        w = np.asarray(weights, dtype=float)
        return seq[int(self.g.choice(len(seq), p=w / w.sum()))]

    def sample(self, seq: list[Any], k: int) -> list[Any]:
        k = min(k, len(seq))
        idx = self.g.choice(len(seq), size=k, replace=False)
        return [seq[int(i)] for i in sorted(idx.tolist())]


def _resolve(core: list[str | tuple[str, ...]], rng: Rng) -> list[str]:
    return [rng.pick(list(x)) if isinstance(x, tuple) else x for x in core]


def grade_of(theta: float) -> str:
    return DEFAULT_THRESHOLDS.grade_for(theta)


def skill_text(code: str, rng: Rng) -> str:
    """Как технология написана в резюме: подпись справочника или синоним/сленг."""
    label = str(catalog()[code]["label"])
    if code == "html_css":
        return rng.pick(["HTML/CSS", "HTML, CSS", "html5", "css3", "scss"])
    if rng.p(0.55):
        return label
    aliases = [a for a in CATALOG_ALIASES.get(code, ()) if a.lower() != label.lower()]
    return rng.pick(aliases) if aliases else label


# --------------------------------------------------------------------------- кандидаты


def make_true_skills(spec: str, gi: int, rng: Rng) -> tuple[list[str], list[str]]:
    """Истинные технологии кандидата и названия его кластеров."""
    clusters = CLUSTERS[spec]
    weights = [c[1] for c in clusters]
    first = rng.pick(clusters, weights)
    chosen = [first]
    if rng.p(0.2 + 0.05 * gi):
        others = [c for c in clusters if c[0] != first[0]]
        chosen.append(rng.pick(others, [c[1] for c in others]))
    skills: list[str] = []
    for n, (_, _, core, extra) in enumerate(chosen):
        p_core = min(0.95, 0.78 + 0.05 * gi) if n == 0 else 0.6
        for code in _resolve(core, rng):
            if rng.p(p_core) and code not in skills:
                skills.append(code)
        for code in extra:
            if rng.p(0.18 + 0.12 * gi) and code not in skills:
                skills.append(code)
    for code in COMMON[spec]:
        if rng.p(0.12 + 0.08 * gi) and code not in skills:
            skills.append(code)
    if not skills:
        skills.append(_resolve(first[2], rng)[0])
    return skills, [c[0] for c in chosen]


def make_achievements(theta: float, rng: Rng) -> list[FspAchievementData]:
    n = 1 + int(rng.g.poisson(1.0 + 0.6 * max(theta, 0.0)))
    out = []
    for _ in range(n):
        lvl_shift = max(0.0, theta) * 0.12
        level = rng.pick(
            ["regional", "national", "international"],
            [0.55 - lvl_shift, 0.35, 0.10 + lvl_shift],
        )
        p_prize = 1 / (1 + math.exp(-(1.2 * theta - 0.8)))
        place: int | None = None
        diploma: str | None = None
        if rng.p(p_prize):
            if rng.p(0.5):
                place = int(rng.pick([1, 2, 3]))
            else:
                diploma = rng.pick(["Диплом I степени", "Диплом II степени", "Диплом III степени"])
        elif rng.p(0.6):
            place = int(rng.g.integers(4, 40))
        achieved = REF_DATE - timedelta(days=int(rng.g.integers(10, 4 * 365)))
        discipline = rng.pick(["product", "algorithmic", "cybersecurity", "uas", "robotics"])
        out.append(FspAchievementData(level, achieved, place, diploma, None, discipline))
    return out


def make_candidates(n: int, seed: int) -> list[dict[str, Any]]:
    rng = Rng(np.random.default_rng(seed))
    out: list[dict[str, Any]] = []
    for i in range(n):
        spec = rng.pick(SPECS, SPEC_WEIGHTS)
        theta = float(np.clip(rng.g.normal(0.0, 1.0), -3.0, 3.0))
        true_grade = grade_of(theta)
        gi = GRADES.index(true_grade)
        # Заявленный грейд: 60% честно, 25% на ступень выше, 15% ниже
        shift = int(rng.pick([-1, 0, 1], [0.15, 0.60, 0.25]))
        declared = GRADES[min(max(gi + shift, 0), 3)]
        skills, clusters = make_true_skills(spec, gi, rng)
        # Резюме: 15% технологий забыты, остальные — подписью или сленгом
        listed = [s for s in skills if rng.p(0.85)] or skills[:1]
        stuffer = rng.p(0.40 if GRADES.index(declared) > gi else 0.15)
        stuffed: list[str] = []
        if stuffer:
            pool = sorted({c for cl in CLUSTERS[spec] for c in _resolve(cl[2], rng)} - set(skills))
            stuffed = rng.sample(pool, int(rng.g.integers(2, 5)))
        resume_codes = listed + stuffed
        order = rng.g.permutation(len(resume_codes)).tolist()
        resume_codes = [resume_codes[k] for k in order]
        resume_skills = [skill_text(c, rng) for c in resume_codes]
        exp = max(0.0, 2.6 + 2.0 * theta + rng.g.normal(0.0, 1.2))
        exp = round(min(exp, 20.0) * 2) / 2
        resume_text = (
            f"{GRADE_LABELS[declared] if declared != 'intern' else 'Стажёр'} {SPEC_WORDS[spec]}. "
            f"Опыт {exp:g} лет. Навыки: {', '.join(resume_skills)}. {rng.pick(ABOUT)}"
        ).strip()
        min_salary = MARKET[declared] * SPEC_SALARY[spec] * float(rng.g.lognormal(0.0, 0.18))
        formats = [f for f, p in zip(FORMATS, (0.65, 0.5, 0.3), strict=True) if rng.p(p)]
        formats = formats or [rng.pick(FORMATS)]
        has_history = rng.p(0.60)
        achievements = make_achievements(theta, rng) if has_history else []
        fsp_id = f"FSP-S{i + 1:05d}" if has_history or rng.p(0.25) else None
        score = fsp_score(achievements, REF_DATE)
        freshness = 0.0 if rng.p(0.45) else round(float(rng.g.beta(2.0, 3.0)), 3)
        out.append(
            {
                "id": f"C{i + 1:04d}",
                "specialization": spec,
                "declared_grade": declared,
                "resume_text": resume_text,
                "resume_skills": resume_skills,
                "experience_years": exp,
                "min_salary": int(round(min_salary / 5000) * 5000),
                "work_formats": formats,
                "fsp_id": fsp_id,
                "fsp_score": score,
                "fsp_achievements": len(achievements),
                "freshness": freshness,
                "truth": {
                    "theta": round(theta, 4),
                    "grade": true_grade,
                    "skills": skills,
                    "clusters": clusters,
                    "keyword_stuffing": stuffed,
                },
            }
        )
    return out


# --------------------------------------------------------------------------- потребности


def relevance(need: dict[str, Any], cand: dict[str, Any]) -> int:
    """ЭТАЛОН: 2 — подходит, 1 — частично, 0 — нет. Только по скрытой правде.

    Жёсткие условия (иначе 0):
    1. истинная специализация кандидата = специализация потребности;
    2. кандидат РЕАЛЬНО владеет всеми обязательными технологиями (истинный стек, не резюме);
    3. минимальная зарплата кандидата ≤ «до» вилки.
    Грейд по истинному уровню θ: совпал с грейдом потребности — 2; на ступень выше — 1
    (справится, но переквалифицирован); иначе — 0.
    Не используются: тест (θ̂), ФСП, свежесть, желательный стек, формат работы, текст резюме,
    смежность технологий — то есть всё, чем ранжирует платформа, кроме зарплаты.
    """
    truth = cand["truth"]
    if cand["specialization"] != need["specialization"]:
        return 0
    if not set(need["skills_required"]) <= set(truth["skills"]):
        return 0
    if cand["min_salary"] > need["salary_to"]:
        return 0
    delta = GRADES.index(truth["grade"]) - GRADES.index(need["grade"])
    return 2 if delta == 0 else 1 if delta == 1 else 0


def make_needs(
    n: int, candidates: list[dict[str, Any]], seed: int, min_relevant: int = 3
) -> tuple[list[dict[str, Any]], int]:
    """Потребности; у каждой в базе должно быть ≥ min_relevant «подходящих» (иначе — новая).

    Возвращает потребности и число попыток (сколько сгенерировано всего, включая отброшенные).
    """
    rng = Rng(np.random.default_rng(seed))
    needs: list[dict[str, Any]] = []
    attempts = 0
    while len(needs) < n:
        attempts += 1
        spec = rng.pick(SPECS, SPEC_WEIGHTS)
        grade = rng.pick(GRADES, [0.10, 0.30, 0.40, 0.20])
        cluster = rng.pick(CLUSTERS[spec], [c[1] for c in CLUSTERS[spec]])
        core = _resolve(cluster[2], rng)
        k_req = int(rng.pick([1, 2, 3], [0.3, 0.5, 0.2]))
        required = rng.sample(core, k_req)
        extra = [c for c in cluster[3] + core if c not in required]
        desired = rng.sample(
            sorted(set(extra), key=extra.index), int(rng.pick([0, 1, 2], [0.2, 0.5, 0.3]))
        )
        mult = SPEC_SALARY[spec] * float(rng.g.uniform(0.9, 1.15))
        salary_from = int(round(MARKET[grade] * mult / 10_000) * 10_000)
        salary_to = int(round(salary_from * float(rng.g.uniform(1.2, 1.45)) / 10_000) * 10_000)
        work_format = rng.pick(FORMATS, [0.45, 0.35, 0.20])
        need = {
            "id": f"N{len(needs) + 1:03d}",
            "title": f"{GRADE_LABELS[grade]} {SPEC_LABELS[spec]}",
            "specialization": spec,
            "grade": grade,
            "category": f"{spec}:{grade}",
            "skills_required": required,
            "skills_desired": desired,
            "salary_from": salary_from,
            "salary_to": salary_to,
            "work_format": work_format,
        }
        if sum(relevance(need, c) == 2 for c in candidates) < min_relevant:
            continue
        labels = [str(catalog()[c]["label"]) for c in required + desired]
        need["keyword_query"] = f"{GRADE_LABELS[grade]} {NEED_SPEC_WORDS[spec]} {' '.join(labels)}"
        needs.append(need)
    return needs, attempts


def gold_rows(needs: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> list[list[Any]]:
    """Ненулевые оценки эталона: need_id, candidate_id, relevance."""
    rows = []
    for need in needs:
        for cand in candidates:
            rel = relevance(need, cand)
            if rel:
                rows.append([need["id"], cand["id"], rel])
    return rows

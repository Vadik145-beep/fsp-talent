"""Разбор свободного текста потребности правилами (T6.1, без LLM).

Повторяет правила прототипа рекрутера (frontend/src/mocks/handlers/recruiter.ts → parseNeedText),
которые одобрил пользователь. Точка входа для API — `app.nlp.need_parser.parse_need`
(трек 3c может заменить реализацию на LLM, этот разбор остаётся запасным путём).
"""

import re
from typing import Any

from app.common import fixtures

SPEC_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "devops",
        re.compile(r"devops|девопс|дев[\s-]?опс|\bsre\b|инфраструктур|kubernetes|k8s|кубер", re.I),
    ),
    ("qa", re.compile(r"\bqa\b|тестировщ|тестирован|автотест|\baqa\b|quality", re.I)),
    (
        "data_ml",
        re.compile(
            r"data scien|дата[\s-]?сайент|\bml\b|машинн\w* обучени|аналитик данных|"
            r"data engineer|дата[\s-]?инженер|\bds\b|nlp|computer vision",
            re.I,
        ),
    ),
    (
        "mobile",
        re.compile(
            r"мобильн|mobile|\bios\b|android|андроид|flutter|swift|kotlin multiplatform", re.I
        ),
    ),
    (
        "frontend",
        re.compile(r"фронт|frontend|front-end|react|реакт|vue|angular|вёрстк|верстк", re.I),
    ),
    (
        "backend",
        re.compile(
            r"бэкенд|бекенд|backend|back-end|серверн|\bgo\b|golang|\bна го\b|python|питон|"
            r"java\b|джав|php|node\.?js|\bnode\b|c#|\.net|fastapi|django|spring",
            re.I,
        ),
    ),
]

GRADE_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("intern", re.compile(r"стаж[её]р|стажир|intern|интерн|практикант", re.I)),
    ("junior", re.compile(r"джун|junior|младш", re.I)),
    (
        "senior",
        re.compile(
            r"сеньор|синьор|сеньер|сениор|senior|старш|ведущ|тимлид|team ?lead|\blead\b", re.I
        ),
    ),
    ("middle", re.compile(r"мидл|миддл|middle|mid\b", re.I)),
]

GRADE_LABELS = {"intern": "Стажёр", "junior": "Junior", "middle": "Middle", "senior": "Senior"}

SPEC_TITLE = {
    "backend": "Backend-разработчик",
    "frontend": "Frontend-разработчик",
    "mobile": "Mobile-разработчик",
    "data_ml": "Data Scientist / ML-инженер",
    "qa": "QA-инженер",
    "devops": "DevOps-инженер",
}

SKILL_ALIASES = {
    "питон": "python",
    "пайтон": "python",
    "golang": "go",
    "го": "go",
    "джава": "java",
    "котлин": "kotlin",
    "постгрес": "postgresql",
    "postgres": "postgresql",
    "кафка": "kafka",
    "редис": "redis",
    "реакт": "react",
    "react.js": "react",
    "reactjs": "react",
    "вью": "vue",
    "js": "javascript",
    "ts": "typescript",
    "тайпскрипт": "typescript",
    "node": "nodejs",
    "нода": "nodejs",
    "k8s": "kubernetes",
    "кубер": "kubernetes",
    "кубернетес": "kubernetes",
    "докер": "docker",
    "линукс": "linux",
    "спарк": "spark",
    "airflow": "airflow",
    "sklearn": "scikit_learn",
    "торч": "pytorch",
    "кликхаус": "clickhouse",
    "селениум": "selenium",
    "next": "nextjs",
    "tailwind": "tailwind",
    "css": "html_css",
    "html": "html_css",
    "c#": "csharp",
    ".net": "csharp",
}

CITIES = [
    "Москва",
    "Санкт-Петербург",
    "Казань",
    "Новосибирск",
    "Екатеринбург",
    "Нижний Новгород",
    "Самара",
    "Краснодар",
    "Пермь",
    "Томск",
]
CITY_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("Москва", re.compile(r"москв|мск", re.I)),
    ("Санкт-Петербург", re.compile(r"петербург|спб|питер\b", re.I)),
    *[(city, re.compile(re.escape(city[:-1]), re.I)) for city in CITIES[2:]],
]

DOMAINS: list[tuple[str, re.Pattern[str]]] = [
    ("Финтех", re.compile(r"финтех|fintech|банк|платёж|платеж", re.I)),
    ("E-commerce", re.compile(r"e-?commerce|маркетплейс|интернет-магазин|ритейл|retail", re.I)),
    ("Медицина", re.compile(r"медицин|медтех|здрав", re.I)),
    ("Образование", re.compile(r"edtech|образован|обучени", re.I)),
    ("Логистика", re.compile(r"логистик|доставк", re.I)),
    ("Игры", re.compile(r"геймдев|gamedev|игр", re.I)),
    ("B2B SaaS", re.compile(r"saas|b2b", re.I)),
]

DESIRED_SPLIT = re.compile(
    r"желательно|будет плюсом|плюсом будет|приветствуется|nice to have|как плюс", re.I
)
REMOTE = re.compile(r"удал[её]н|remote|из дома|дистанц", re.I)
HYBRID = re.compile(r"гибрид|hybrid", re.I)
OFFICE = re.compile(r"офис|office", re.I)

_WORD = "a-zа-яё0-9+#"


def _skills() -> list[dict[str, Any]]:
    return fixtures.all_records("skills")


def skill_label(code: str) -> str:
    for s in _skills():
        if s["id"] == code:
            return str(s["label"])
    return code


def _has(lower: str, token: str) -> bool:
    pattern = rf"(^|[^{_WORD}.]){re.escape(token.lower())}(?=$|[^{_WORD}])"
    return re.search(pattern, lower, re.I) is not None


def find_skills(text: str) -> list[str]:
    """Технологии справочника в тексте: по коду, подписи и синонимам."""
    found: list[str] = []
    lower = text.lower()
    skills = _skills()
    codes = {s["id"] for s in skills}
    for s in skills:
        tokens = ["go"] if s["id"] == "go" else [s["id"].replace("_", " ", 1), s["label"]]
        if any(_has(lower, t) for t in tokens) and s["id"] not in found:
            found.append(s["id"])
    for alias, code in SKILL_ALIASES.items():
        if _has(lower, alias) and code not in found and code in codes:
            found.append(code)
    return found


def _to_rub(value: float, suffix: str | None) -> float:
    if suffix and re.search(r"к|k|тыс", suffix, re.I):
        return value * 1000
    if value < 1000:
        return value * 1000
    return value


def _num(s: str) -> float:
    return float(s.replace(",", "."))


RANGE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(к|k|тыс\.?)?\s*(?:–|—|-|до)\s*(\d+(?:[.,]\d+)?)\s*"
    r"(к|k|тыс\.?|000|₽|руб)?",
    re.I,
)
FROM = re.compile(r"от\s*(\d+(?:[.,]\d+)?)\s*(к|k|тыс\.?)?", re.I)
TO = re.compile(r"до\s*(\d+(?:[.,]\d+)?)\s*(к|k|тыс\.?)?", re.I)


def parse_salary(text: str) -> tuple[int | None, int | None]:
    clean = re.sub(r"(\d)\s(?=\d{3}\b)", r"\1", text)
    m = RANGE.search(clean)
    if m:
        suffix = m.group(4) or m.group(2)
        a = _to_rub(_num(m.group(1)), m.group(2) or suffix)
        b = _to_rub(_num(m.group(3)), suffix)
        if a >= 10000 and b >= 10000:
            return round(a), round(b)
    f, t = FROM.search(clean), TO.search(clean)
    fv = _to_rub(_num(f.group(1)), f.group(2)) if f else None
    tv = _to_rub(_num(t.group(1)), t.group(2)) if t else None
    return (
        round(fv) if fv and fv >= 10000 else None,
        round(tv) if tv and tv >= 10000 else None,
    )


def _first(rules: list[tuple[str, re.Pattern[str]]], text: str) -> str | None:
    return next((code for code, rx in rules if rx.search(text)), None)


def parse_need_text(text: str) -> dict[str, Any]:
    """Текст → `NeedParseResult` (черновик полей, распознанные и нераспознанные поля)."""
    parts = DESIRED_SPLIT.split(text)
    main_text, desired_text = parts[0], " ".join(parts[1:])
    specialization = _first(SPEC_RULES, text)
    grade = _first(GRADE_RULES, text)
    required = find_skills(main_text)
    desired = [s for s in find_skills(desired_text) if s not in required]
    work_format = (
        "remote"
        if REMOTE.search(text)
        else "hybrid"
        if HYBRID.search(text)
        else "office"
        if OFFICE.search(text)
        else None
    )
    city = _first(CITY_RULES, text)
    salary_from, salary_to = parse_salary(text)
    domain = _first(DOMAINS, text)

    title = None
    if specialization:
        main_skill = f" ({skill_label(required[0])})" if required else ""
        grade_part = f"{GRADE_LABELS[grade]} " if grade else ""
        title = f"{grade_part}{SPEC_TITLE[specialization]}{main_skill}"

    draft = {
        "title": title,
        "specialization": specialization,
        "grade": grade,
        "skills_required": required,
        "skills_desired": desired,
        "team_description": f"Сфера: {domain}" if domain else None,
        "work_format": work_format,
        "city": city,
        "salary_from": salary_from,
        "salary_to": salary_to,
    }
    checks = [
        ("specialization", bool(specialization)),
        ("grade", bool(grade)),
        ("skills_required", bool(required)),
        ("skills_desired", bool(desired)),
        ("work_format", bool(work_format)),
        ("salary", salary_from is not None or salary_to is not None),
        ("city", bool(city)),
        ("team_description", bool(domain)),
    ]
    return {
        "draft": draft,
        "parser": "rules",
        "recognized_fields": [f for f, ok in checks if ok],
        "unrecognized": [f for f, ok in checks if not ok and f != "skills_desired"],
    }

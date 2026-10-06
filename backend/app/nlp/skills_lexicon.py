"""Справочник синонимов стека: названия, опечатки, сленг → коды `data/seed/skills.json`.

Плюс технологии, которых нет в справочнике платформы (Celery, Git, Jira…): их тоже узнаём,
чтобы показать кандидату «не нашли в справочнике», а не потерять молча.
И смежность технологий — частичный вклад в близость стека (FastAPI ↔ Django = 0,5).

Всё детерминированно: один и тот же текст → один и тот же результат.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.core.config import get_settings

# Код → синонимы (в нижнем регистре). Сам код и подпись из skills.json добавляются автоматически.
# Кириллические синонимы от 4 букв ловят и падежи: «реакте», «постгресе», «питонист».
CATALOG_ALIASES: dict[str, tuple[str, ...]] = {
    "python": ("python", "python3", "питон", "пайтон"),
    "go": ("go", "golang", "голанг", "гоу"),
    "java": ("java", "джава", "жава", "java se", "java ee"),
    "kotlin": ("kotlin", "котлин"),
    "csharp": ("c#", "csharp", "c sharp", ".net", "dotnet", "дотнет", "шарп", "си шарп"),
    "php": ("php", "пхп", "пэхапэ"),
    "nodejs": ("node.js", "nodejs", "node js", "нода"),
    "fastapi": ("fastapi", "fast api", "фастапи", "фаст апи"),
    "django": ("django", "джанго", "drf", "django rest framework"),
    "spring": ("spring", "spring boot", "springboot", "спринг", "спрингбут"),
    "postgresql": (
        "postgresql",
        "postgres",
        "postgre",
        "postgress",
        "posgresql",
        "постгрес",
        "постгресс",
        "постгре",
        "постгрескуэль",
        "pg",
        "psql",
    ),
    "mysql": ("mysql", "my sql", "мускул", "майскуэль", "mariadb"),
    "mongodb": ("mongodb", "mongo", "монго", "монгодб"),
    "redis": ("redis", "редис"),
    "kafka": ("kafka", "apache kafka", "кафка", "кафке", "кафку"),
    "rabbitmq": ("rabbitmq", "rabbit mq", "rabbit", "реббит"),
    "grpc": ("grpc", "g-rpc", "грпц"),
    "graphql": ("graphql", "graph ql", "графкуэль"),
    "sql": ("sql", "t-sql", "pl/sql", "скуль", "эскуэль"),
    "javascript": ("javascript", "java script", "js", "es6", "ecmascript", "джаваскрипт"),
    "typescript": ("typescript", "type script", "тайпскрипт", "тайпскрипте"),
    "react": ("react", "react.js", "reactjs", "react js", "реакт", "риакт"),
    "vue": ("vue", "vue.js", "vuejs", "vue js", "vue 3", "вью", "вьюджс", "вуе"),
    "angular": ("angular", "angularjs", "ангуляр"),
    "nextjs": ("next.js", "nextjs", "next js", "некст"),
    "html_css": ("html", "css", "html5", "css3", "scss", "sass", "html/css"),
    "redux": ("redux", "redux toolkit", "rtk", "редакс"),
    "webpack": ("webpack", "вебпак"),
    "vite": ("vite",),
    "tailwind": ("tailwind", "tailwind css", "tailwindcss", "тейлвинд"),
    "jest": ("jest", "джест"),
    "swift": ("swift", "свифт"),
    "swiftui": ("swiftui", "swift ui", "свифтюай"),
    "ios_sdk": ("ios sdk", "uikit", "ui kit"),
    "android_sdk": ("android sdk", "андроид sdk"),
    "jetpack_compose": ("jetpack compose", "compose", "компоуз"),
    "flutter": ("flutter", "флаттер"),
    "dart": ("dart", "дарт"),
    "react_native": ("react native", "react-native", "реакт нейтив"),
    "pandas": ("pandas", "пандас"),
    "numpy": ("numpy", "нампай"),
    "scikit_learn": ("scikit-learn", "scikit learn", "sklearn", "склерн", "сайкит"),
    "pytorch": ("pytorch", "torch", "пайторч"),
    "tensorflow": ("tensorflow", "tensor flow", "keras", "тензорфлоу"),
    "spark": ("spark", "apache spark", "pyspark", "спарк"),
    "airflow": ("airflow", "apache airflow", "эирфлоу", "эйрфлоу"),
    "clickhouse": ("clickhouse", "click house", "кликхаус"),
    "mlflow": ("mlflow", "ml flow"),
    "jupyter": ("jupyter", "jupyter notebook", "jupyterlab", "юпитер"),
    "selenium": ("selenium", "selenide", "селениум", "селен"),
    "playwright": ("playwright", "плейрайт"),
    "pytest": ("pytest", "py.test", "пайтест"),
    "postman": ("postman", "постман"),
    "jmeter": ("jmeter", "apache jmeter", "джиметр"),
    "allure": ("allure", "аллюр"),
    "cypress": ("cypress", "сайпресс"),
    "testrail": ("testrail", "test rail"),
    "docker": ("docker", "docker compose", "docker-compose", "докер"),
    "kubernetes": ("kubernetes", "k8s", "kube", "кубер", "кубернетес", "кубернетис"),
    "helm": ("helm", "хелм"),
    "terraform": ("terraform", "терраформ", "тераформ"),
    "ansible": ("ansible", "ансибл", "ансибле"),
    "gitlab_ci": (
        "gitlab ci",
        "gitlab-ci",
        "gitlab ci/cd",
        "gitlab",
        "гитлаб",
        "гитлаб ci",
    ),
    "github_actions": ("github actions", "gh actions", "гитхаб экшены"),
    "prometheus": ("prometheus", "прометеус", "прометей"),
    "grafana": ("grafana", "графана"),
    "nginx": ("nginx", "нгинкс", "энджинкс", "енджинкс"),
    "linux": ("linux", "линукс", "debian", "ubuntu", "rhel", "centos", "astra linux"),
    "bash": ("bash", "shell"),
    "aws": ("aws", "amazon web services"),
}

# Технологии вне справочника платформы: код → (подпись, синонимы).
EXTRA_TECH: dict[str, tuple[str, tuple[str, ...]]] = {
    "celery": ("Celery", ("celery", "селери")),
    "sqlalchemy": ("SQLAlchemy", ("sqlalchemy", "sql alchemy", "алхимия")),
    "alembic": ("Alembic", ("alembic",)),
    "flask": ("Flask", ("flask", "фласк")),
    "git": ("Git", ("git",)),
    "jira": ("Jira", ("jira", "джира")),
    "confluence": ("Confluence", ("confluence",)),
    "storybook": ("Storybook", ("storybook",)),
    "react_testing_library": (
        "React Testing Library",
        ("react testing library", "testing library"),
    ),
    "nuxt": ("Nuxt", ("nuxt", "nuxt.js", "nuxtjs", "накст")),
    "argo_cd": ("Argo CD", ("argo cd", "argocd", "argo")),
    "jenkins": ("Jenkins", ("jenkins", "дженкинс")),
    "loki": ("Loki", ("loki",)),
    "alertmanager": ("Alertmanager", ("alertmanager",)),
    "zabbix": ("Zabbix", ("zabbix", "заббикс")),
    "elasticsearch": ("Elasticsearch", ("elasticsearch", "elastic", "эластик")),
    "yandex_cloud": ("Yandex Cloud", ("yandex cloud", "яндекс облако", "yandex.cloud")),
    "gcp": ("Google Cloud", ("gcp", "google cloud")),
    "azure": ("Azure", ("azure",)),
    "haproxy": ("HAProxy", ("haproxy",)),
    "retrofit": ("Retrofit", ("retrofit",)),
    "coroutines": ("Kotlin Coroutines", ("kotlin coroutines", "coroutines", "корутины")),
    "hibernate": ("Hibernate", ("hibernate",)),
    "laravel": ("Laravel", ("laravel",)),
    "rust": ("Rust", ("rust",)),
    "cpp": ("C++", ("c++", "cpp")),
    "scala": ("Scala", ("scala",)),
    "hadoop": ("Hadoop", ("hadoop",)),
    "xgboost": ("XGBoost", ("xgboost",)),
    "catboost": ("CatBoost", ("catboost",)),
    "lightgbm": ("LightGBM", ("lightgbm",)),
    "opencv": ("OpenCV", ("opencv",)),
    "figma": ("Figma", ("figma", "фигма")),
    "sentry": ("Sentry", ("sentry",)),
    "k6": ("k6", ("k6",)),
}

# Смежные технологии: вклад в близость стека, если у кандидата нет точной, но есть соседняя.
ADJACENCY: dict[frozenset[str], float] = {
    frozenset(pair): weight
    for pair, weight in (
        (("fastapi", "django"), 0.5),
        (("fastapi", "flask"), 0.6),
        (("django", "flask"), 0.6),
        (("java", "kotlin"), 0.6),
        (("java", "csharp"), 0.3),
        (("postgresql", "mysql"), 0.6),
        (("postgresql", "sql"), 0.7),
        (("mysql", "sql"), 0.7),
        (("clickhouse", "sql"), 0.5),
        (("clickhouse", "postgresql"), 0.3),
        (("kafka", "rabbitmq"), 0.6),
        (("grpc", "graphql"), 0.3),
        (("javascript", "typescript"), 0.7),
        (("javascript", "nodejs"), 0.4),
        (("react", "vue"), 0.4),
        (("react", "angular"), 0.4),
        (("vue", "angular"), 0.4),
        (("nextjs", "react"), 0.6),
        (("nuxt", "vue"), 0.6),
        (("redux", "react"), 0.3),
        (("webpack", "vite"), 0.6),
        (("jest", "playwright"), 0.3),
        (("swift", "swiftui"), 0.6),
        (("swift", "ios_sdk"), 0.6),
        (("swiftui", "ios_sdk"), 0.6),
        (("kotlin", "android_sdk"), 0.5),
        (("android_sdk", "jetpack_compose"), 0.6),
        (("kotlin", "jetpack_compose"), 0.4),
        (("flutter", "dart"), 0.8),
        (("react_native", "react"), 0.5),
        (("react_native", "flutter"), 0.3),
        (("pandas", "numpy"), 0.6),
        (("pytorch", "tensorflow"), 0.6),
        (("scikit_learn", "pandas"), 0.3),
        (("spark", "pandas"), 0.3),
        (("airflow", "mlflow"), 0.3),
        (("selenium", "playwright"), 0.6),
        (("selenium", "cypress"), 0.5),
        (("playwright", "cypress"), 0.6),
        (("allure", "testrail"), 0.3),
        (("docker", "kubernetes"), 0.4),
        (("kubernetes", "helm"), 0.6),
        (("terraform", "ansible"), 0.4),
        (("gitlab_ci", "github_actions"), 0.6),
        (("gitlab_ci", "jenkins"), 0.5),
        (("prometheus", "grafana"), 0.5),
        (("bash", "linux"), 0.5),
        (("nginx", "haproxy"), 0.5),
    )
}

_WORD = "0-9a-zа-яё"
_CYR = re.compile(r"[а-яё]")


@dataclass(frozen=True)
class SkillMention:
    """Найденная в тексте технология."""

    code: str
    label: str
    in_catalog: bool
    text: str  # как написано в тексте
    start: int
    end: int


@lru_cache
def catalog() -> dict[str, dict[str, Any]]:
    """Справочник стека платформы: код → запись skills.json."""
    path = get_settings().seed_dir / "skills.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    return {r["id"]: r for r in records}


def label(code: str) -> str:
    if code in catalog():
        return str(catalog()[code]["label"])
    if code in EXTRA_TECH:
        return EXTRA_TECH[code][0]
    return code


def is_catalog(code: str) -> bool:
    return code in catalog()


def _alias_pattern(alias: str) -> str:
    parts = [re.escape(p) for p in re.split(r"[\s\-]+", alias.strip()) if p]
    body = r"[\s\-]?".join(parts)
    # падежи и суффиксы у кириллических синонимов: «постгресе», «питонист», «кубера»
    tail = r"[а-яё]{0,4}" if _CYR.search(alias[-1:]) and len(alias) >= 4 else ""
    end = r"(?![0-9a-zа-яё#])" if not alias.endswith(("+", "#")) else ""
    return rf"(?<![{_WORD}.#]){body}{tail}{end}"


@lru_cache
def _alias_index() -> tuple[re.Pattern[str], dict[str, str]]:
    """Один регэксп на все синонимы (длинные — раньше) и словарь «синоним → код»."""
    alias_to_code: dict[str, str] = {}
    for code, rec in catalog().items():
        for alias in (code, rec["label"], *CATALOG_ALIASES.get(code, ())):
            alias_to_code.setdefault(_norm(alias), code)
    for code, (lbl, aliases) in EXTRA_TECH.items():
        for alias in (lbl, *aliases):
            alias_to_code.setdefault(_norm(alias), code)
    # «HTML и CSS» из справочника не синоним — это подпись; отдельные html/css уже есть
    alias_to_code.pop(_norm("HTML и CSS"), None)
    ordered = sorted(alias_to_code, key=len, reverse=True)
    groups = "|".join(f"(?:{_alias_pattern(a)})" for a in ordered)
    return re.compile(groups, re.IGNORECASE), alias_to_code


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower().replace("ё", "е"))


def normalize_skill(name: str) -> str | None:
    """Название или код технологии → код (справочника или EXTRA_TECH); None — не знаем."""
    key = _norm(name)
    if not key:
        return None
    if key in catalog() or key in EXTRA_TECH:
        return key
    _, alias_to_code = _alias_index()
    if key in alias_to_code:
        return alias_to_code[key]
    found = find_skills(name)
    if len(found) == 1 and found[0].end - found[0].start >= len(name.strip()) - 4:
        return found[0].code
    return None


def find_skills(text: str) -> list[SkillMention]:
    """Все технологии в тексте в порядке появления (повторы схлопываются)."""
    pattern, alias_to_code = _alias_index()
    seen: set[str] = set()
    result: list[SkillMention] = []
    for m in pattern.finditer(text):
        raw = m.group(0)
        code = _lookup(raw, alias_to_code)
        if code is None or code in seen:
            continue
        seen.add(code)
        result.append(SkillMention(code, label(code), is_catalog(code), raw, m.start(), m.end()))
    return result


def _lookup(raw: str, alias_to_code: dict[str, str]) -> str | None:
    key = _norm(raw)
    if key in alias_to_code:
        return alias_to_code[key]
    key = re.sub(r"[\s\-]", " ", key)
    if key in alias_to_code:
        return alias_to_code[key]
    compact = key.replace(" ", "")
    for alias, code in alias_to_code.items():
        if alias.replace(" ", "").replace("-", "") == compact:
            return code
    # кириллица с окончанием: отрезаем по одной букве до известного синонима
    while key and _CYR.search(key[-1:]):
        key = key[:-1]
        if key in alias_to_code:
            return alias_to_code[key]
    return None


def similarity(a: str, b: str) -> float:
    """Близость двух технологий 0..1: 1 — одно и то же, доля — смежные, 0 — не связаны."""
    ca, cb = normalize_skill(a) or a, normalize_skill(b) or b
    if ca == cb:
        return 1.0
    return ADJACENCY.get(frozenset((ca, cb)), 0.0)


def specializations_of(code: str) -> list[str]:
    rec = catalog().get(code)
    return list(rec["specializations"]) if rec else []

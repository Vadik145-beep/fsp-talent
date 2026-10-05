"""Генератор фикстур `data/seed/*.json` — один источник данных для моков фронта и заглушек API.

Запуск из корня репозитория:  python scripts/seed/generate_fixtures.py
Детерминирован: seed фиксирован, «сейчас» = 2026-10-06 12:00 МСК. Повторный запуск даёт
те же файлы байт в байт. Только стандартная библиотека.

Все данные синтетические: имена придуманы, почты на example.com, компании вымышлены.
Каждый файл — массив объектов с полем `id`; поля совпадают со схемами API
(backend/app/*/schemas.py).
"""

# ruff: noqa: E501 — файл данных, длинные строки текста допустимы

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SEED = 20261011
MSK = timezone(timedelta(hours=3))
NOW = datetime(2026, 10, 6, 12, 0, tzinfo=MSK)
OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "seed"
CONSENT_VERSION = "2026-10-01"

rng = random.Random(SEED)
J = dict[str, Any]


def iso(dt: datetime) -> str:
    return dt.isoformat()


def days_ago(days: float, hour: int = 12) -> datetime:
    return (NOW - timedelta(days=days)).replace(hour=hour, minute=0, second=0)


def round_to(value: float, step: int = 10_000) -> int:
    return int(round(value / step) * step)


# ---------------------------------------------------------------- справочники

SPECIALIZATIONS: list[J] = [
    {
        "id": "backend",
        "label": "Backend",
        "description": "Серверная разработка: API, базы данных, интеграции",
    },
    {
        "id": "frontend",
        "label": "Frontend",
        "description": "Веб-интерфейсы: вёрстка, JavaScript/TypeScript, фреймворки",
    },
    {"id": "mobile", "label": "Mobile", "description": "Мобильные приложения для iOS и Android"},
    {
        "id": "data_ml",
        "label": "Data Science / ML",
        "description": "Анализ данных, машинное обучение, ML-инженерия",
    },
    {"id": "qa", "label": "QA", "description": "Тестирование: ручное и автоматизированное"},
    {
        "id": "devops",
        "label": "DevOps",
        "description": "Инфраструктура, CI/CD, контейнеры, мониторинг",
    },
]
SPEC_LABEL = {s["id"]: s["label"] for s in SPECIALIZATIONS}
for s in SPECIALIZATIONS:
    s["active"] = True

GRADES: list[J] = [
    {"id": "intern", "label": "Стажёр", "order": 0},
    {"id": "junior", "label": "Junior", "order": 1},
    {"id": "middle", "label": "Middle", "order": 2},
    {"id": "senior", "label": "Senior", "order": 3},
]
GRADE_IDS = [g["id"] for g in GRADES]
GRADE_LABEL = {g["id"]: g["label"] for g in GRADES}


def cat_id(spec: str, grade: str) -> str:
    return f"{spec}:{grade}"


def cat_label(spec: str, grade: str) -> str:
    return f"{SPEC_LABEL[spec]} · {GRADE_LABEL[grade]}"


CATEGORIES: list[J] = [
    {
        "id": cat_id(s["id"], g["id"]),
        "specialization": s["id"],
        "grade": g["id"],
        "label": cat_label(s["id"], g["id"]),
    }
    for s in SPECIALIZATIONS
    for g in GRADES
]

TOPIC_LABELS: dict[str, list[tuple[str, str]]] = {
    "backend": [
        ("http_api", "HTTP и REST API"),
        ("databases", "Базы данных и SQL"),
        ("concurrency", "Конкурентность и асинхронность"),
        ("architecture", "Архитектура и паттерны"),
        ("algorithms", "Алгоритмы и структуры данных"),
        ("security", "Безопасность веб-приложений"),
    ],
    "frontend": [
        ("js_core", "JavaScript"),
        ("react", "React и состояние"),
        ("css_layout", "Вёрстка и CSS"),
        ("browser", "Браузер и производительность"),
        ("typescript", "TypeScript"),
        ("testing", "Тестирование фронтенда"),
    ],
    "mobile": [
        ("lifecycle", "Жизненный цикл приложения"),
        ("ui", "Интерфейс и навигация"),
        ("networking", "Сеть и хранение данных"),
        ("language", "Kotlin / Swift"),
        ("release", "Сборка и публикация"),
    ],
    "data_ml": [
        ("statistics", "Статистика и вероятности"),
        ("ml_basics", "Классическое ML"),
        ("deep_learning", "Глубокое обучение"),
        ("sql_data", "SQL и обработка данных"),
        ("metrics", "Метрики и валидация моделей"),
    ],
    "qa": [
        ("test_design", "Тест-дизайн"),
        ("automation", "Автоматизация тестирования"),
        ("api_testing", "Тестирование API"),
        ("process", "Баг-репорты и процессы"),
        ("performance", "Нагрузочное тестирование"),
    ],
    "devops": [
        ("linux", "Linux и сети"),
        ("containers", "Контейнеры и Kubernetes"),
        ("ci_cd", "CI/CD"),
        ("monitoring", "Мониторинг и логирование"),
        ("iac", "Инфраструктура как код"),
    ],
}
TOPICS: list[J] = [
    {"id": f"{spec}.{code}", "specialization": spec, "label": label}
    for spec, items in TOPIC_LABELS.items()
    for code, label in items
]
TOPIC_LABEL = {t["id"]: t["label"] for t in TOPICS}
SPEC_TOPICS = {spec: [f"{spec}.{c}" for c, _ in items] for spec, items in TOPIC_LABELS.items()}

SKILL_DEFS: list[tuple[str, str, list[str]]] = [
    ("python", "Python", ["backend", "data_ml", "qa"]),
    ("go", "Go", ["backend", "devops"]),
    ("java", "Java", ["backend", "mobile", "qa"]),
    ("kotlin", "Kotlin", ["backend", "mobile"]),
    ("csharp", "C#", ["backend"]),
    ("php", "PHP", ["backend"]),
    ("nodejs", "Node.js", ["backend", "frontend"]),
    ("fastapi", "FastAPI", ["backend"]),
    ("django", "Django", ["backend"]),
    ("spring", "Spring", ["backend"]),
    ("postgresql", "PostgreSQL", ["backend", "data_ml"]),
    ("mysql", "MySQL", ["backend"]),
    ("mongodb", "MongoDB", ["backend"]),
    ("redis", "Redis", ["backend", "devops"]),
    ("kafka", "Kafka", ["backend", "data_ml"]),
    ("rabbitmq", "RabbitMQ", ["backend"]),
    ("grpc", "gRPC", ["backend"]),
    ("graphql", "GraphQL", ["backend", "frontend"]),
    ("sql", "SQL", ["backend", "data_ml", "qa"]),
    ("javascript", "JavaScript", ["frontend", "qa"]),
    ("typescript", "TypeScript", ["frontend", "backend"]),
    ("react", "React", ["frontend"]),
    ("vue", "Vue", ["frontend"]),
    ("angular", "Angular", ["frontend"]),
    ("nextjs", "Next.js", ["frontend"]),
    ("html_css", "HTML и CSS", ["frontend"]),
    ("redux", "Redux", ["frontend"]),
    ("webpack", "Webpack", ["frontend"]),
    ("vite", "Vite", ["frontend"]),
    ("tailwind", "Tailwind CSS", ["frontend"]),
    ("jest", "Jest", ["frontend", "qa"]),
    ("swift", "Swift", ["mobile"]),
    ("swiftui", "SwiftUI", ["mobile"]),
    ("ios_sdk", "iOS SDK", ["mobile"]),
    ("android_sdk", "Android SDK", ["mobile"]),
    ("jetpack_compose", "Jetpack Compose", ["mobile"]),
    ("flutter", "Flutter", ["mobile"]),
    ("dart", "Dart", ["mobile"]),
    ("react_native", "React Native", ["mobile", "frontend"]),
    ("pandas", "pandas", ["data_ml"]),
    ("numpy", "NumPy", ["data_ml"]),
    ("scikit_learn", "scikit-learn", ["data_ml"]),
    ("pytorch", "PyTorch", ["data_ml"]),
    ("tensorflow", "TensorFlow", ["data_ml"]),
    ("spark", "Apache Spark", ["data_ml"]),
    ("airflow", "Apache Airflow", ["data_ml", "devops"]),
    ("clickhouse", "ClickHouse", ["data_ml", "backend"]),
    ("mlflow", "MLflow", ["data_ml"]),
    ("jupyter", "Jupyter", ["data_ml"]),
    ("selenium", "Selenium", ["qa"]),
    ("playwright", "Playwright", ["qa", "frontend"]),
    ("pytest", "pytest", ["qa", "backend"]),
    ("postman", "Postman", ["qa"]),
    ("jmeter", "JMeter", ["qa"]),
    ("allure", "Allure", ["qa"]),
    ("cypress", "Cypress", ["qa", "frontend"]),
    ("testrail", "TestRail", ["qa"]),
    ("docker", "Docker", ["devops", "backend"]),
    ("kubernetes", "Kubernetes", ["devops", "backend"]),
    ("helm", "Helm", ["devops"]),
    ("terraform", "Terraform", ["devops"]),
    ("ansible", "Ansible", ["devops"]),
    ("gitlab_ci", "GitLab CI", ["devops"]),
    ("github_actions", "GitHub Actions", ["devops"]),
    ("prometheus", "Prometheus", ["devops"]),
    ("grafana", "Grafana", ["devops"]),
    ("nginx", "Nginx", ["devops", "backend"]),
    ("linux", "Linux", ["devops", "backend"]),
    ("bash", "Bash", ["devops"]),
    ("aws", "AWS", ["devops"]),
]
SKILLS: list[J] = [
    {"id": i, "label": label, "specializations": specs} for i, label, specs in SKILL_DEFS
]
SPEC_SKILLS = {
    s["id"]: [k["id"] for k in SKILLS if s["id"] in k["specializations"]] for s in SPECIALIZATIONS
}

DECLINE_REASONS: list[J] = [
    {"id": "salary_too_low", "label": "Мала зарплата"},
    {"id": "wrong_stack", "label": "Не тот стек"},
    {"id": "not_interested_domain", "label": "Не интересна сфера"},
    {"id": "not_looking", "label": "Не ищу работу сейчас"},
    {"id": "other", "label": "Другое"},
]
DECLINE_LABEL = {d["id"]: d["label"] for d in DECLINE_REASONS}

# ---------------------------------------------------------------- люди

MALE_FIRST = [
    "Алексей",
    "Дмитрий",
    "Иван",
    "Михаил",
    "Сергей",
    "Андрей",
    "Никита",
    "Артём",
    "Егор",
    "Максим",
    "Кирилл",
    "Павел",
    "Роман",
    "Тимур",
    "Глеб",
    "Илья",
    "Денис",
    "Владимир",
    "Константин",
    "Ярослав",
]
FEMALE_FIRST = [
    "Анна",
    "Мария",
    "Екатерина",
    "Ольга",
    "Дарья",
    "Полина",
    "Алина",
    "София",
    "Виктория",
    "Ксения",
    "Елизавета",
    "Наталья",
    "Юлия",
    "Вероника",
    "Татьяна",
]
SURNAMES = [
    "Смирнов",
    "Кузнецов",
    "Попов",
    "Васильев",
    "Соколов",
    "Михайлов",
    "Новиков",
    "Фёдоров",
    "Морозов",
    "Волков",
    "Алексеев",
    "Лебедев",
    "Семёнов",
    "Егоров",
    "Павлов",
    "Козлов",
    "Степанов",
    "Николаев",
    "Орлов",
    "Андреев",
    "Макаров",
    "Никитин",
    "Захаров",
    "Зайцев",
    "Соловьёв",
    "Борисов",
    "Яковлев",
    "Григорьев",
    "Романов",
    "Воробьёв",
    "Сергеев",
    "Кузьмин",
    "Фролов",
    "Александров",
    "Дмитриев",
    "Королёв",
    "Гусев",
    "Киселёв",
    "Ильин",
    "Максимов",
]
TRANSLIT = dict(
    zip(
        "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
        [
            "a",
            "b",
            "v",
            "g",
            "d",
            "e",
            "e",
            "zh",
            "z",
            "i",
            "y",
            "k",
            "l",
            "m",
            "n",
            "o",
            "p",
            "r",
            "s",
            "t",
            "u",
            "f",
            "kh",
            "ts",
            "ch",
            "sh",
            "sch",
            "",
            "y",
            "",
            "e",
            "yu",
            "ya",
        ],
        strict=True,
    )
)
CITIES = [
    "Москва",
    "Санкт-Петербург",
    "Казань",
    "Новосибирск",
    "Екатеринбург",
    "Нижний Новгород",
    "Томск",
    "Самара",
    "Краснодар",
    "Иннополис",
]
TEAM_ROLES = [
    "Разработчик",
    "Тимлид",
    "Ментор",
    "Ревьюер кода",
    "Архитектор",
    "Аналитик",
    "Тестировщик",
    "Капитан команды",
]
SOFT_SKILLS = [
    "Коммуникация",
    "Самостоятельность",
    "Работа в команде",
    "Наставничество",
    "Тайм-менеджмент",
    "Критическое мышление",
    "Публичные выступления",
    "Ответственность",
    "Обучаемость",
]


def translit(text: str) -> str:
    return "".join(TRANSLIT.get(ch, ch) for ch in text.lower())


def female_surname(surname: str) -> str:
    return surname + "а"


def pseudonym(candidate_id: int) -> str:
    digest = hashlib.sha1(f"fsp-talent-candidate-{candidate_id}".encode()).hexdigest()
    return f"Кандидат #{digest[:4].upper()}"


# ---------------------------------------------------------------- компании и рекрутеры

COMPANIES: list[J] = [
    {
        "id": 1,
        "name": "Северный код",
        "description": "Разрабатываем платёжные сервисы и мобильный банк для региональных банков.",
        "industry": "Финтех",
        "website": "https://severny-kod.example.com",
        "city": "Москва",
        "contact_email": "hr.severny@example.com",
        "contact_phone": "+7 900 000-10-00",
        "inn": "7700000001",
        "verified_domain": True,
        "trust_score": 86.0,
        "blocked": False,
        "created_at": iso(days_ago(120)),
    },
    {
        "id": 2,
        "name": "Лаборатория данных «Вектор»",
        "description": "Аналитика и ML для сетей магазинов: прогноз спроса, рекомендации.",
        "industry": "Ритейл-аналитика",
        "website": "https://vektor-lab.example.com",
        "city": "Санкт-Петербург",
        "contact_email": "jobs.vektor@example.com",
        "contact_phone": "+7 900 000-20-00",
        "inn": "7800000002",
        "verified_domain": True,
        "trust_score": 78.0,
        "blocked": False,
        "created_at": iso(days_ago(90)),
    },
    {
        "id": 3,
        "name": "Облачные системы «Тайга»",
        "description": "B2B-платформа для учёта в логистике. Молодая компания.",
        "industry": "B2B SaaS",
        "website": "https://taiga-cloud.example.com",
        "city": "Новосибирск",
        "contact_email": "taiga.hr@example.com",
        "contact_phone": None,
        "inn": None,
        "verified_domain": False,
        "trust_score": 41.0,
        "blocked": False,
        "created_at": iso(days_ago(20)),
    },
]
COMPANY_NAME = {c["id"]: c["name"] for c in COMPANIES}

RECRUITER_DEFS = [
    # (company_id, full_name, position, is_company_admin)
    (1, "Ирина Белова", "HR-директор", True),
    (1, "Олег Карпов", "Технический рекрутер", False),
    (1, "Светлана Жукова", "Рекрутер", False),
    (2, "Марина Титова", "Руководитель подбора", True),
    (2, "Георгий Лаптев", "IT-рекрутер", False),
    (3, "Виталий Ершов", "Основатель", True),
    (3, "Алёна Пестова", "HR-менеджер", False),
]

USERS: list[J] = []
RECRUITERS: list[J] = []
CANDIDATES: list[J] = []

# ---------------------------------------------------------------- кандидаты

N_CANDIDATES = 40
SPEC_PLAN = (
    ["backend"] * 9
    + ["frontend"] * 7
    + ["data_ml"] * 6
    + ["qa"] * 5
    + ["devops"] * 6
    + ["mobile"] * 5
)
GRADE_PLAN = ["intern"] * 4 + ["junior"] * 12 + ["middle"] * 14 + ["senior"] * 8
THETA_CENTER = {"intern": -1.6, "junior": -0.5, "middle": 0.5, "senior": 1.45}
SALARY_RANGE = {
    "intern": (40_000, 70_000),
    "junior": (80_000, 140_000),
    "middle": (150_000, 260_000),
    "senior": (280_000, 450_000),
}
EXPERIENCE = {"intern": (0, 0.5), "junior": (0.5, 2), "middle": (2, 5), "senior": (5, 12)}


def fsp_id_for(candidate_id: int) -> str | None:
    if 1 <= candidate_id <= 20:
        return f"FSP-{candidate_id:06d}"
    if 21 <= candidate_id <= 25:
        return f"FSP-{candidate_id + 10:06d}"  # FSP-000031..035 — без истории
    return None


# ---------------------------------------------------------------- достижения ФСП

COMPETITIONS = {
    "product": [
        "Чемпионат по продуктовому программированию",
        "Хакатон «Цифровой прорыв» (трек ФСП)",
    ],
    "algorithmic": ["Кубок по спортивному программированию", "Командная олимпиада по алгоритмам"],
    "cybersecurity": ["Соревнования по кибербезопасности (CTF)", "Турнир по защите инфраструктуры"],
    "uas": ["Чемпионат по программированию БАС"],
    "robotics": ["Турнир по программированию роботов"],
}
SPEC_DISCIPLINES = {
    "backend": ["product", "algorithmic", "cybersecurity"],
    "frontend": ["product", "algorithmic"],
    "mobile": ["product", "uas"],
    "data_ml": ["product", "algorithmic", "robotics"],
    "qa": ["product", "cybersecurity"],
    "devops": ["cybersecurity", "product", "uas"],
}
LEVEL_LABEL = {
    "regional": "регионального",
    "national": "всероссийского",
    "international": "международного",
}
ACHIEVEMENTS: list[J] = []
# Старые случайные достижения больше не попадают в фикстуры (см. make_achievements)
_LEGACY_ACHIEVEMENTS: list[J] = []

# Мок реестра ФСП — источник правды по ФИО участников и их достижениям. Кандидаты с ФСП ID
# получают ФИО из реестра, fsp_achievements.json — кэш достижений из реестра в формате API.
FSP_REGISTRY_JSON = (
    Path(__file__).resolve().parents[2]
    / "services"
    / "fsp-registry-mock"
    / "data"
    / "participants.json"
)
FSP_REGISTRY: dict[str, J] = {
    p["fsp_id"]: p
    for p in json.loads(FSP_REGISTRY_JSON.read_text(encoding="utf-8"))["participants"]
}
# коды дисциплин реестра → коды платформы (app/common/enums.py FspDiscipline)
DISCIPLINE_FROM_REGISTRY = {
    "product": "product",
    "algorithmic": "algorithmic",
    "security": "cybersecurity",
    "uav": "uas",
    "robotics": "robotics",
}
DIPLOMA_LABEL = {1: "Диплом I степени", 2: "Диплом II степени", 3: "Диплом III степени"}

# ФСП-скор (docs/integration/fsp.md, раздел 7) — та же формула, что в backend/app/fsp/scoring.py
LEVEL_WEIGHT = {"regional": 1.0, "national": 2.0, "international": 3.0}
DIPLOMA_WEIGHT = {"Диплом I степени": 0.8, "Диплом II степени": 0.6, "Диплом III степени": 0.45}
LEVEL_WINNER = {
    "regional": "Победитель регионального соревнования",
    "national": "Победитель всероссийского соревнования",
    "international": "Победитель международного соревнования",
}


def result_weight(place: int | None, diploma: str | None) -> float:
    if place is not None:
        return {1: 1.0, 2: 0.85, 3: 0.7}.get(place, 0.4 if place <= 10 else 0.25)
    if diploma is not None:
        return DIPLOMA_WEIGHT.get(diploma, 0.45)
    return 0.1  # участие


def fsp_score(achs: list[J]) -> float | None:
    """ФСП-скор = 100 × (1 − e^(−S/3)), S = Σ уровень × результат × 0,5^(возраст/2)."""
    if not achs:
        return None
    total = 0.0
    for a in achs:
        age_years = max(0, (NOW.date() - datetime.fromisoformat(a["date"]).date()).days) / 365.25
        freshness = 0.5 ** (age_years / 2)
        total += LEVEL_WEIGHT[a["level"]] * result_weight(a["place"], a["diploma"]) * freshness
    return float(round(100 * (1 - math.exp(-total / 3))))


def is_prize(a: J) -> bool:
    return a["diploma"] is not None or (a["place"] is not None and a["place"] <= 3)


def badges_for(achs: list[J]) -> list[J]:
    """Бейджи «подтверждено ФСП» — та же логика, что в backend/app/fsp/scoring.py."""
    badges: list[J] = []
    for level in ("international", "national", "regional"):
        on_level = [a for a in achs if a["level"] == level]
        if any(a["place"] == 1 for a in on_level):
            badges.append(
                {"id": f"{level}_winner", "title": LEVEL_WINNER[level], "level": level, "verified": True}
            )
        elif any(is_prize(a) for a in on_level):
            badges.append(
                {
                    "id": f"{level}_prize",
                    "title": f"Призёр {LEVEL_LABEL[level]} соревнования",
                    "level": level,
                    "verified": True,
                }
            )
    if any((a["role"] or "").startswith("Капитан") for a in achs):
        badges.append({"id": "captain", "title": "Капитан команды", "level": None, "verified": True})
    if len(achs) >= 2:
        badges.append(
            {
                "id": "participant_many",
                "title": f"Участник {len(achs)} соревнований ФСП",
                "level": None,
                "verified": True,
            }
        )
    elif len(achs) == 1:
        badges.append(
            {
                "id": "participant",
                "title": "Участник соревнования ФСП",
                "level": None,
                "verified": True,
            }
        )
    return badges


def registry_achievements(fsp: str) -> list[J]:
    """Достижения участника из мока реестра → формат кэша платформы (схема FspAchievement).

    Порядок — как в реестре (от старых к новым), поэтому id достижения в реестре
    восстанавливается как ACH-<номер>-<порядковый номер> (см. backend/app/fsp/fixtures_loader.py).
    """
    result = []
    for item in FSP_REGISTRY[fsp]["achievements"]:
        res, team = item["result"], item["team"]
        role = None
        if team:
            role = f"Капитан, {team['role']}" if team["is_captain"] else team["role"]
        ach = {
            "id": len(ACHIEVEMENTS) + 1,
            "fsp_id": fsp,
            "competition": item["competition"]["title"],
            "discipline": DISCIPLINE_FROM_REGISTRY[item["discipline"]["code"]],
            "level": item["level"]["code"],
            "date": item["date"],
            "place": res["place"] if res["kind"] == "place" else None,
            "diploma": DIPLOMA_LABEL[res["diploma_degree"]] if res["kind"] == "diploma" else None,
            "team": team["name"] if team else None,
            "role": role,
            "rating": float(item["rating_points"]),
            "protocol_url": item["competition"]["protocol_url"],
            "verified": item["verified"],
        }
        ACHIEVEMENTS.append(ach)
        result.append(ach)
    return result


def make_achievements(fsp: str, spec: str, grade: str) -> list[J]:
    """Старый генератор случайных достижений. Результат не используется (источник — реестр),
    но вызовы rng сохранены, чтобы не сдвинуть остальные фикстуры."""
    count = {
        "intern": 1,
        "junior": rng.randint(1, 2),
        "middle": rng.randint(1, 3),
        "senior": rng.randint(2, 4),
    }[grade]
    result = []
    for _ in range(count):
        discipline = rng.choice(SPEC_DISCIPLINES[spec])
        level = rng.choices(["regional", "national", "international"], [5, 4, 1])[0]
        year_days = rng.randint(40, 900)
        place = rng.choice([1, 2, 3, 4, 5, 7, 10, None])
        ach_date = (NOW - timedelta(days=year_days)).date()
        competition = rng.choice(COMPETITIONS[discipline])
        ach = {
            "id": len(_LEGACY_ACHIEVEMENTS) + 1,
            "fsp_id": fsp,
            "competition": f"{competition} {ach_date.year}",
            "discipline": discipline,
            "level": level,
            "date": ach_date.isoformat(),
            "place": place,
            "diploma": {1: "Диплом I степени", 2: "Диплом II степени", 3: "Диплом III степени"}.get(
                place or 0
            ),
            "team": rng.choice(
                ["Ультратех", "Байт-шторм", "Северный ветер", "Код 404", "Синтаксис", None]
            ),
            "role": rng.choice(["Капитан", "Разработчик", "Аналитик", "Тестировщик"]),
            "rating": round(rng.uniform(1200, 2400), 0) if discipline == "algorithmic" else None,
            "protocol_url": f"https://fsp-registry.example.com/protocols/{rng.randint(1000, 9999)}",
            "verified": True,
        }
        _LEGACY_ACHIEVEMENTS.append(ach)
        result.append(ach)
    return result


def topic_scores(spec: str, theta: float) -> list[J]:
    scores = []
    for topic in SPEC_TOPICS[spec]:
        p = 1 / (1 + math.exp(-(theta + rng.uniform(-0.9, 0.9))))
        score = round(min(0.98, max(0.05, p)), 2)
        level = "strong" if score >= 0.7 else "weak" if score < 0.4 else "ok"
        scores.append({"topic": topic, "label": TOPIC_LABEL[topic], "score": score, "level": level})
    return scores


ABOUT = {
    "backend": "Пишу серверную часть: API, работа с базами, очереди. Люблю понятный код и тесты.",
    "frontend": "Делаю интерфейсы, которые удобно использовать. Слежу за производительностью.",
    "mobile": "Разрабатываю мобильные приложения от прототипа до публикации в сторах.",
    "data_ml": "Работаю с данными: от SQL-выгрузок до обучения и вывода моделей в прод.",
    "qa": "Тестирую веб и API, пишу автотесты, выстраиваю процессы качества.",
    "devops": "Настраиваю CI/CD, контейнеры и мониторинг, чтобы релизы были скучными.",
}


def build_people() -> None:
    specs = SPEC_PLAN[:]
    grades = GRADE_PLAN[:]
    rng.shuffle(specs)
    rng.shuffle(grades)
    # Кандидат 1 — демо: Backend · Middle с ФСП. Кандидат 26 — демо без ФСП: Frontend · Junior.
    for idx, (s, g) in ((0, ("backend", "middle")), (25, ("frontend", "junior"))):
        j = next(k for k in range(len(specs)) if specs[k] == s and k != idx and k >= 1)
        specs[idx], specs[j] = specs[j], specs[idx]
        j = next(k for k in range(len(grades)) if grades[k] == g and k != idx and k >= 1)
        grades[idx], grades[j] = grades[j], grades[idx]
    # 38 графиков; 39 и 40 — регистрация без теста
    specs += ["backend", "qa"]
    used_names: set[str] = set()

    for i in range(1, N_CANDIDATES + 1):
        spec = specs[i - 1]
        graded = i <= 38
        grade = grades[i - 1] if graded else None
        female = rng.random() < 0.35
        while True:
            if i == 1:
                first, surname, female = "Алексей", "Смирнов", False
            elif female:
                first, surname = rng.choice(FEMALE_FIRST), female_surname(rng.choice(SURNAMES))
            else:
                first, surname = rng.choice(MALE_FIRST), rng.choice(SURNAMES)
            full = f"{first} {surname}"
            if full not in used_names:
                used_names.add(full)
                break
        fsp = fsp_id_for(i)
        if fsp:
            # ФИО участника ФСП — из реестра (имена выше всё равно разыгрываются, чтобы rng
            # не сдвинулся и остальные фикстуры не изменились)
            first, surname = FSP_REGISTRY[fsp]["first_name"], FSP_REGISTRY[fsp]["last_name"]
            full = f"{first} {surname}"
        login = f"{translit(first)[0]}.{translit(surname)}.{i:02d}"
        email = {1: "candidate@example.com", 26: "candidate.nofsp@example.com"}.get(
            i, f"{login}@example.com"
        )
        created = days_ago(rng.randint(5, 60), hour=rng.randint(9, 20))
        USERS.append(
            {
                "id": i,
                "email": email,
                "role": "candidate",
                "full_name": full,
                "email_verified": True,
                "blocked": i == 36,
                "created_at": iso(created),
                "last_login_at": iso(days_ago(rng.uniform(0, 4), hour=rng.randint(8, 22))),
            }
        )

        g_for_ranges = grade or "junior"
        theta = round(THETA_CENTER[grade] + rng.uniform(-0.35, 0.35), 2) if grade else None
        if i == 1:
            theta = 0.42
        stack = rng.sample(SPEC_SKILLS[spec], k=min(len(SPEC_SKILLS[spec]), rng.randint(4, 7)))
        if spec == "backend" and i == 1:
            stack = ["python", "fastapi", "postgresql", "redis", "docker", "kafka"]
        lo, hi = SALARY_RANGE[g_for_ranges]
        exp_lo, exp_hi = EXPERIENCE[g_for_ranges]
        if fsp and i <= 20:
            make_achievements(fsp, spec, g_for_ranges)  # только расход rng, см. docstring
        achs = registry_achievements(fsp) if fsp else []
        links = []
        if rng.random() < 0.6:
            links.append(
                {"type": "github", "url": f"https://github.com/example-{translit(first)}{i}"}
            )
        if rng.random() < 0.2:
            links.append({"type": "portfolio", "url": f"https://portfolio.example.com/{i}"})
        privacy = {
            "show_city": rng.random() < 0.85,
            "show_experience": rng.random() < 0.9,
            "show_links": rng.random() < 0.4,
            "show_fsp_achievements": rng.random() < 0.9,
        }
        if i == 1:
            privacy = {
                "show_city": True,
                "show_experience": True,
                "show_links": False,
                "show_fsp_achievements": True,
            }
        last_test = days_ago(rng.randint(5, 50)) if graded else None
        grade_changed = last_test
        if i == 1:
            grade_changed = last_test = datetime(2026, 9, 10, 15, 30, tzinfo=MSK)
        candidate = {
            "id": i,
            "user_id": i,
            "pseudonym": pseudonym(i),
            "full_name": full,
            "email": email,
            "phone": f"+7 900 {100 + i:03d}-{rng.randint(10, 99)}-{rng.randint(10, 99)}",
            "telegram": f"@example_{translit(first)}{i}" if rng.random() < 0.8 or i == 1 else None,
            "city": "Казань" if i == 1 else rng.choice(CITIES),
            "work_formats": (
                ["remote", "hybrid"]
                if i == 1
                else sorted(rng.sample(["office", "hybrid", "remote"], k=rng.randint(1, 3)))
            ),
            "specialization": spec,
            "grade": grade,
            "category": cat_id(spec, grade) if grade else None,
            "category_label": cat_label(spec, grade) if grade else None,
            "theta": theta,
            "theta_se": round(rng.uniform(0.25, 0.34), 2) if graded else None,
            "topic_scores": topic_scores(spec, theta) if theta is not None else [],
            "stack": stack,
            "roles_in_team": rng.sample(TEAM_ROLES[:6], k=rng.randint(1, 2)),
            "experience_years": round(rng.uniform(exp_lo, exp_hi) * 2) / 2,
            "soft_skills": rng.sample(SOFT_SKILLS, k=rng.randint(2, 4)),
            "about": ABOUT[spec],
            "links": links,
            "min_salary": 180_000 if i == 1 else round_to(rng.uniform(lo, hi)),
            "fsp_id": fsp,
            "fsp_score": fsp_score(achs),
            "fsp_badges": badges_for(achs),
            "privacy": privacy,
            "job_search_paused": i == 38,
            "publication_consent": i != 37,
            "freshness": round(rng.uniform(0.1, 0.95), 2),
            "profile_completeness": 0,
            "last_test_at": iso(last_test) if last_test else None,
            "grade_changed_at": iso(grade_changed) if grade_changed else None,
            "created_at": iso(created),
        }
        if i == 1:
            candidate["freshness"] = 0.72
        filled = [
            candidate["phone"],
            candidate["telegram"],
            candidate["city"],
            candidate["grade"],
            candidate["links"],
            candidate["fsp_id"],
            candidate["about"],
            candidate["min_salary"],
            len(stack) >= 4,
            candidate["soft_skills"],
        ]
        candidate["profile_completeness"] = round(100 * sum(bool(x) for x in filled) / 10)
        CANDIDATES.append(candidate)

    for idx, (company_id, full, position, is_admin) in enumerate(RECRUITER_DEFS, start=1):
        user_id = 40 + idx
        first, surname = full.split()
        email = (
            "recruiter@example.com"
            if idx == 1
            else (f"{translit(first)[0]}.{translit(surname)}.hr@example.com")
        )
        USERS.append(
            {
                "id": user_id,
                "email": email,
                "role": "recruiter",
                "full_name": full,
                "email_verified": True,
                "blocked": False,
                "created_at": iso(days_ago(rng.randint(15, 100))),
                "last_login_at": iso(days_ago(rng.uniform(0, 3))),
            }
        )
        RECRUITERS.append(
            {
                "id": idx,
                "user_id": user_id,
                "company_id": company_id,
                "full_name": full,
                "position": position,
                "email": email,
                "phone": f"+7 900 {200 + idx:03d}-00-{10 + idx}",
                "telegram": f"@hr_{translit(surname)}",
                "is_company_admin": is_admin,
            }
        )
    for user_id, email, full in (
        (48, "admin@example.com", "Администратор платформы"),
        (49, "moderator@example.com", "Модератор ФСП"),
    ):
        USERS.append(
            {
                "id": user_id,
                "email": email,
                "role": "admin",
                "full_name": full,
                "email_verified": True,
                "blocked": False,
                "created_at": iso(days_ago(150)),
                "last_login_at": iso(days_ago(0.2)),
            }
        )


# ---------------------------------------------------------------- банк задач

FORMAT_TIME = {
    "single_choice": 60,
    "multiple_choice": 90,
    "numeric": 120,
    "short_text": 90,
    "code_output": 120,
    "find_error_line": 120,
    "ordering": 90,
}
GRADE_B = {"intern": -1.5, "junior": -0.5, "middle": 0.5, "senior": 1.5}


def shuffled_options(
    r: random.Random, correct: list[str], wrong: list[str]
) -> tuple[list[J], list[str]]:
    texts = correct + wrong
    r.shuffle(texts)
    letters = "abcdef"
    options = [{"id": letters[k], "text": t} for k, t in enumerate(texts)]
    correct_ids = [o["id"] for o in options if o["text"] in correct]
    return options, correct_ids


def gen_little(r: random.Random) -> J:
    rps, ms = r.choice([100, 200, 250, 400, 500, 800]), r.choice([20, 40, 50, 80, 120, 150])
    return {
        "prompt": f"Сервис принимает {rps} запросов в секунду, среднее время ответа {ms} мс. "
        "Сколько запросов в среднем обрабатывается одновременно (закон Литтла)?",
        "unit": "запросов",
        "answer": {"value": rps * ms / 1000},
    }


def gen_py_slice(r: random.Random) -> J:
    xs = [r.randint(1, 9) for _ in range(5)]
    k = r.randint(2, 4)
    start = r.randint(1, 2)
    code = f"xs = {xs}\nprint(sum(xs[{start}:]) * {k})"
    return {
        "prompt": "Что выведет код?",
        "code": code,
        "answer": {"text": str(sum(xs[start:]) * k)},
    }


def gen_js_output(r: random.Random) -> J:
    a, b = r.randint(2, 9), r.randint(2, 9)
    code = f"const arr = [{a}, {b}, {a + b}];\nconst res = arr.map(x => x * 2).filter(x => x > {2 * a});\nconsole.log(res.length);"
    res = len([x * 2 for x in (a, b, a + b) if x * 2 > 2 * a])
    return {"prompt": "Что выведет код?", "code": code, "answer": {"text": str(res)}}


def gen_http_status(r: random.Random) -> J:
    res = r.choice(["заказ", "пользователь", "товар", "счёт", "отзыв"])
    opts, ids = shuffled_options(
        r, ["404 Not Found"], ["400 Bad Request", "409 Conflict", "500 Internal Server Error"]
    )
    return {
        "prompt": f"Клиент запрашивает {res} по id, которого нет в базе. Какой код ответа вернуть?",
        "options": opts,
        "answer": {"choice_ids": ids},
    }


def gen_isolation(r: random.Random) -> J:
    opts, ids = shuffled_options(
        r, ["REPEATABLE READ", "SERIALIZABLE"], ["READ UNCOMMITTED", "READ COMMITTED"]
    )
    table = r.choice(["orders", "payments", "accounts", "invoices"])
    return {
        "prompt": f"Транзакция дважды читает строку из таблицы {table}. Какие уровни изоляции "
        "гарантируют, что значение не изменится между чтениями?",
        "options": opts,
        "answer": {"choice_ids": ids},
    }


def gen_sql_error(r: random.Random) -> J:
    table = r.choice(["orders", "users", "events", "payments"])
    col = r.choice(["amount", "total", "price"])
    lines = [
        f"SELECT customer_id, SUM({col}) AS s",
        f"FROM {table}",
        f"WHERE SUM({col}) > {r.randint(10, 500)}",
        "GROUP BY customer_id",
        "ORDER BY s DESC;",
    ]
    return {
        "prompt": "Запрос падает с ошибкой. В какой строке ошибка?",
        "code": "\n".join(lines),
        "answer": {"line": 3},
    }


def gen_py_error(r: random.Random) -> J:
    n = r.randint(3, 9)
    name = r.choice(["items", "values", "data", "nums"])
    lines = [
        f"def total({name}):",
        "    s = 0",
        f"    for i in range(len({name}) + 1):",
        f"        s += {name}[i]",
        "    return s",
        f"print(total(list(range({n}))))",
    ]
    return {
        "prompt": "Код падает с ошибкой. В какой строке причина?",
        "code": "\n".join(lines),
        "answer": {"line": 3},
    }


def gen_order(r: random.Random, steps: list[str]) -> J:
    ids = [f"s{k + 1}" for k in range(len(steps))]
    items = list(zip(ids, steps, strict=True))
    shuffled = items[:]
    r.shuffle(shuffled)
    return {
        "prompt": "Расположите шаги в правильном порядке.",
        "steps": [{"id": i, "text": t} for i, t in shuffled],
        "answer": {"order": ids},
    }


def gen_choice(r: random.Random, prompt: str, correct: list[str], wrong: list[str]) -> J:
    opts, ids = shuffled_options(r, correct, wrong)
    return {"prompt": prompt, "options": opts, "answer": {"choice_ids": ids}}


def gen_mean(r: random.Random) -> J:
    xs = [r.randint(1, 20) for _ in range(5)]
    return {
        "prompt": f"Выборка: {xs}. Чему равно выборочное среднее?",
        "unit": None,
        "answer": {"value": round(statistics.mean(xs), 2)},
    }


def gen_precision(r: random.Random) -> J:
    tp, fp = r.randint(20, 90), r.randint(5, 40)
    return {
        "prompt": f"Модель отметила {tp + fp} объектов как положительные, из них {tp} "
        "действительно положительные. Чему равна precision? (до 2 знаков)",
        "answer": {"value": round(tp / (tp + fp), 2)},
    }


def gen_boundary(r: random.Random) -> J:
    lo, hi = r.choice([(1, 100), (18, 65), (5, 50), (10, 99)])
    return {
        "prompt": f"Поле принимает целые от {lo} до {hi} включительно. Сколько значений "
        "нужно проверить по методу граничных значений (по два на каждую границу: "
        "на границе и за ней)?",
        "answer": {"value": 4},
    }


def gen_short(prompt: str, answer: str) -> Any:
    return lambda r: {"prompt": prompt, "answer": {"text": answer}}


def gen_cron(r: random.Random) -> J:
    minute, hour = r.choice([0, 15, 30, 45]), r.randint(0, 23)
    return {
        "prompt": f"Задача должна запускаться каждый день в {hour:02d}:{minute:02d}. "
        "Запишите cron-выражение (5 полей).",
        "answer": {"text": f"{minute} {hour} * * *"},
    }


def gen_chmod(r: random.Random) -> J:
    u, g, o = r.choice([7, 6, 5]), r.choice([5, 4, 0]), r.choice([4, 0])
    return {
        "prompt": f"Права файла: chmod {u}{g}{o}. Сколько бит прав установлено всего?",
        "answer": {"value": sum(bin(x).count("1") for x in (u, g, o))},
    }


def gen_layout(r: random.Random) -> J:
    w, p, b = r.choice([200, 240, 300]), r.choice([10, 16, 20]), r.choice([1, 2, 4])
    return {
        "prompt": f"У блока width: {w}px, padding: {p}px, border: {b}px, box-sizing: content-box. "
        "Какая итоговая ширина блока в пикселях?",
        "unit": "px",
        "answer": {"value": w + 2 * p + 2 * b},
    }


# (spec, topic_code, grade, format, title, generator, variants_count)
ITEM_DEFS: list[tuple[str, str, str, str, str, Any, int]] = [
    (
        "backend",
        "http_api",
        "junior",
        "single_choice",
        "Код ответа для отсутствующего ресурса",
        gen_http_status,
        60,
    ),
    (
        "backend",
        "databases",
        "middle",
        "multiple_choice",
        "Уровни изоляции транзакций",
        gen_isolation,
        96,
    ),
    (
        "backend",
        "concurrency",
        "middle",
        "numeric",
        "Закон Литтла для пропускной способности",
        gen_little,
        36,
    ),
    (
        "backend",
        "algorithms",
        "intern",
        "find_error_line",
        "Ошибка выхода за границы списка",
        gen_py_error,
        70,
    ),
    (
        "backend",
        "architecture",
        "senior",
        "ordering",
        "Шаги паттерна Saga при отмене заказа",
        lambda r: gen_order(
            r,
            [
                "Сервис заказов создаёт заказ",
                "Сервис оплаты списывает деньги",
                "Склад сообщает об отсутствии товара",
                "Сервис оплаты выполняет компенсацию — возврат",
                "Заказ переводится в статус «Отменён»",
            ],
        ),
        120,
    ),
    (
        "frontend",
        "js_core",
        "junior",
        "code_output",
        "map и filter над массивом",
        gen_js_output,
        64,
    ),
    (
        "frontend",
        "react",
        "middle",
        "single_choice",
        "Зависимости useEffect",
        lambda r: gen_choice(
            r,
            f"Эффект должен выполниться один раз после монтирования компонента "
            f"{r.choice(['Profile', 'Cart', 'Feed', 'Search'])}. "
            "Какой массив зависимостей передать?",
            ["Пустой массив []"],
            ["Не передавать массив", "[props]", "[state, setState]"],
        ),
        96,
    ),
    ("frontend", "css_layout", "intern", "numeric", "Блочная модель CSS", gen_layout, 27),
    (
        "frontend",
        "browser",
        "senior",
        "ordering",
        "Критический путь рендеринга",
        lambda r: gen_order(
            r,
            [
                "Разбор HTML в DOM",
                "Разбор CSS в CSSOM",
                "Построение дерева рендеринга",
                "Layout — расчёт геометрии",
                "Paint — отрисовка",
            ],
        ),
        120,
    ),
    (
        "frontend",
        "typescript",
        "middle",
        "short_text",
        "Утилитарные типы TypeScript",
        gen_short(
            "Какой утилитарный тип делает все поля объекта необязательными? (одно слово)", "Partial"
        ),
        1,
    ),
    (
        "mobile",
        "lifecycle",
        "junior",
        "single_choice",
        "Жизненный цикл Activity",
        lambda r: gen_choice(
            r,
            "Какой метод Activity вызывается, когда пользователь сворачивает "
            f"приложение «{r.choice(['Заметки', 'Банк', 'Погода', 'Карты'])}»?",
            ["onStop()"],
            ["onCreate()", "onDestroy()", "onRestart()"],
        ),
        96,
    ),
    (
        "mobile",
        "networking",
        "middle",
        "multiple_choice",
        "Хранение данных на устройстве",
        lambda r: gen_choice(
            r,
            "Где безопасно хранить токен доступа в мобильном приложении?",
            ["Keychain (iOS)", "EncryptedSharedPreferences (Android)"],
            ["Обычные SharedPreferences", "Файл в общей папке"],
        ),
        96,
    ),
    (
        "mobile",
        "language",
        "intern",
        "code_output",
        "Срезы списков (Kotlin-подобный псевдокод)",
        gen_py_slice,
        500,
    ),
    (
        "mobile",
        "release",
        "senior",
        "ordering",
        "Публикация релиза в стор",
        lambda r: gen_order(
            r,
            [
                "Поднять версию сборки",
                "Собрать подписанный релиз",
                "Загрузить сборку во внутреннее тестирование",
                "Пройти ревью стора",
                "Выпустить на 10% пользователей",
            ],
        ),
        120,
    ),
    (
        "mobile",
        "ui",
        "middle",
        "short_text",
        "Навигация в Jetpack Compose",
        gen_short(
            "Как называется компонент Compose, который хранит стек экранов навигации? "
            "(одно слово, NavHost или NavController)",
            "NavController",
        ),
        1,
    ),
    ("data_ml", "statistics", "intern", "numeric", "Выборочное среднее", gen_mean, 5000),
    ("data_ml", "metrics", "middle", "numeric", "Precision по матрице ошибок", gen_precision, 2000),
    (
        "data_ml",
        "ml_basics",
        "junior",
        "single_choice",
        "Переобучение",
        lambda r: gen_choice(
            r,
            f"На обучении точность {r.randint(95, 99)}%, на валидации "
            f"{r.randint(60, 70)}%. Что это?",
            ["Переобучение"],
            ["Недообучение", "Утечка в тест", "Норма"],
        ),
        96,
    ),
    (
        "data_ml",
        "sql_data",
        "middle",
        "find_error_line",
        "GROUP BY в агрегирующем запросе",
        gen_sql_error,
        72,
    ),
    (
        "data_ml",
        "deep_learning",
        "senior",
        "multiple_choice",
        "Борьба с затуханием градиента",
        lambda r: gen_choice(
            r,
            "Что помогает против затухания градиента в глубокой сети?",
            ["Residual-связи", "Нормализация слоёв"],
            ["Сигмоида во всех слоях", "Увеличение глубины без изменений"],
        ),
        96,
    ),
    ("qa", "test_design", "junior", "numeric", "Граничные значения", gen_boundary, 4),
    (
        "qa",
        "api_testing",
        "middle",
        "single_choice",
        "Идемпотентность методов HTTP",
        lambda r: gen_choice(
            r,
            f"Какой метод НЕ идемпотентен при создании ресурса "
            f"/{r.choice(['orders', 'users', 'tickets'])}?",
            ["POST"],
            ["GET", "PUT", "DELETE"],
        ),
        72,
    ),
    (
        "qa",
        "process",
        "intern",
        "ordering",
        "Жизненный цикл бага",
        lambda r: gen_order(r, ["Новый", "Назначен", "Исправлен", "Проверен", "Закрыт"]),
        120,
    ),
    ("qa", "automation", "middle", "find_error_line", "Ошибка в автотесте", gen_py_error, 70),
    (
        "qa",
        "performance",
        "senior",
        "numeric",
        "Пропускная способность под нагрузкой",
        gen_little,
        36,
    ),
    ("devops", "linux", "junior", "numeric", "Права доступа в Linux", gen_chmod, 18),
    ("devops", "ci_cd", "middle", "short_text", "Расписание cron", gen_cron, 96),
    (
        "devops",
        "containers",
        "middle",
        "single_choice",
        "Kubernetes: перезапуск подов",
        lambda r: gen_choice(
            r,
            f"Под сервиса {r.choice(['api', 'worker', 'billing'])} падает "
            "при старте. Какая проба не даст трафику идти в неготовый под?",
            ["readinessProbe"],
            ["livenessProbe", "startupProbe", "nodeSelector"],
        ),
        72,
    ),
    (
        "devops",
        "monitoring",
        "senior",
        "multiple_choice",
        "Сигналы SRE",
        lambda r: gen_choice(
            r,
            "Какие из метрик входят в «четыре золотых сигнала»?",
            ["Задержка (latency)", "Насыщение (saturation)"],
            ["Число коммитов", "Покрытие тестами"],
        ),
        96,
    ),
    (
        "devops",
        "iac",
        "junior",
        "ordering",
        "Цикл работы Terraform",
        lambda r: gen_order(
            r, ["terraform init", "terraform plan", "terraform apply", "terraform destroy"]
        ),
        24,
    ),
]
ITEMS: list[J] = []


def expected_p(a: float, b: float, theta: float) -> float:
    return 1 / (1 + math.exp(-a * (theta - b)))


def build_items() -> None:
    statuses = ["active"] * 30
    for k in (4, 14):
        statuses[k] = "pilot"
    for k in (9, 26):
        statuses[k] = "draft"
    for k in (20, 22):
        statuses[k] = "retired"
    leak = {12, 20, 27}
    for idx, (spec, topic_code, grade, fmt, title, gen, variants) in enumerate(ITEM_DEFS, start=1):
        topic = f"{spec}.{topic_code}"
        a = round(rng.uniform(0.8, 2.0), 2)
        b = round(GRADE_B[grade] + rng.uniform(-0.3, 0.3), 2)
        status = statuses[idx - 1]
        exposures = (
            0
            if status == "draft"
            else rng.randint(15, 60)
            if status == "pilot"
            else rng.randint(80, 900)
        )
        exp_rate = round(expected_p(a, b, 0.2), 2)
        is_leak = (idx - 1) in leak
        obs_rate = (
            None
            if exposures == 0
            else round(
                min(
                    0.98,
                    exp_rate + (rng.uniform(0.25, 0.35) if is_leak else rng.uniform(-0.05, 0.05)),
                ),
                2,
            )
        )
        variants_preview = []
        for v in range(3):
            seed = 1000 * idx + 17 * v + 3
            content = gen(random.Random(seed))
            view = {
                "instance_id": f"it-{idx:04d}-s{seed}",
                "format": fmt,
                "topic": topic,
                "topic_label": TOPIC_LABEL[topic],
                "prompt": content["prompt"],
                "code": content.get("code"),
                "options": content.get("options"),
                "steps": content.get("steps"),
                "unit": content.get("unit"),
                "time_limit_sec": FORMAT_TIME[fmt],
                "seed": seed,
                "correct_answer": {
                    "choice_ids": None,
                    "value": None,
                    "text": None,
                    "line": None,
                    "order": None,
                    **content["answer"],
                },
            }
            variants_preview.append(view)
        ITEMS.append(
            {
                "id": idx,
                "code": f"{spec[:2]}-{topic_code[:4]}-{idx:03d}",
                "title": title,
                "description": f"Параметрический шаблон: «{title}». Числа, имена и порядок вариантов "
                "меняются от seed, ответ вычисляет генератор.",
                "specialization": spec,
                "topic": topic,
                "topic_label": TOPIC_LABEL[topic],
                "target_grade": grade,
                "format": fmt,
                "a": a,
                "b": b,
                "status": status,
                "source": "llm_vacancy" if status == "draft" else "expert",
                "exposures": exposures,
                "correct_rate": obs_rate,
                "expected_correct_rate": None if exposures == 0 else exp_rate,
                "leak_flag": is_leak,
                "leak_score": round(rng.uniform(3.1, 4.5), 2)
                if is_leak
                else round(rng.uniform(0, 1.2), 2),
                "variants_count": variants,
                "created_at": iso(days_ago(rng.randint(3, 40))),
                "preview_variants": variants_preview,
            }
        )


# ---------------------------------------------------------------- тесты и грейды

TEST_SESSIONS: list[J] = []
GRADE_HISTORY: list[J] = []


def add_history(
    cand_id: int,
    at: datetime,
    event: str,
    spec: str | None,
    g_from: str | None,
    g_to: str | None,
    session: int | None,
    comment: str,
) -> None:
    GRADE_HISTORY.append(
        {
            "id": len(GRADE_HISTORY) + 1,
            "candidate_id": cand_id,
            "at": iso(at),
            "event": event,
            "specialization": spec,
            "grade_from": g_from,
            "grade_to": g_to,
            "test_session_id": session,
            "comment": comment,
        }
    )


def session_record(
    cand: J, kind: str, target: str, start: datetime, theta: float, passed: bool, result_grade: str
) -> J:
    se = round(rng.uniform(0.27, 0.34), 2)
    rec = {
        "id": len(TEST_SESSIONS) + 1,
        "candidate_id": cand["id"],
        "specialization": cand["specialization"],
        "target_grade": target,
        "kind": kind,
        "status": "finished",
        "started_at": iso(start),
        "finished_at": iso(start + timedelta(minutes=rng.randint(18, 35))),
        "items_answered": rng.randint(11, 15),
        "max_items": 15,
        "theta": theta,
        "se": se,
        "ci_low": round(theta - 1.96 * se, 2),
        "ci_high": round(theta + 1.96 * se, 2),
        "result_grade": result_grade,
        "result_category": cat_id(cand["specialization"], result_grade),
        "passed": passed,
        "topic_scores": cand["topic_scores"]
        if passed
        else topic_scores(cand["specialization"], theta),
    }
    TEST_SESSIONS.append(rec)
    return rec


def build_tests() -> None:
    for cand in CANDIDATES:
        spec, grade = cand["specialization"], cand["grade"]
        created = datetime.fromisoformat(cand["created_at"])
        add_history(
            cand["id"],
            created + timedelta(hours=1),
            "survey",
            spec,
            None,
            None,
            None,
            f"Опрос рекомендовал специализацию {SPEC_LABEL[spec]}",
        )
        if grade is None:
            continue
        last_test = datetime.fromisoformat(cand["last_test_at"])
        gi = GRADE_IDS.index(grade)
        # иногда сначала неудачная попытка на грейд выше
        if gi < 3 and rng.random() < 0.3:
            failed_at = last_test - timedelta(days=rng.randint(1, 3))
            higher = GRADE_IDS[gi + 1]
            s = session_record(
                cand, "placement", higher, failed_at, round(cand["theta"] - 0.1, 2), False, grade
            )
            add_history(
                cand["id"],
                failed_at,
                "test_failed",
                spec,
                None,
                higher,
                s["id"],
                f"Заявленный грейд {GRADE_LABEL[higher]} не подтверждён",
            )
            add_history(
                cand["id"],
                failed_at,
                "offer_lower",
                spec,
                higher,
                grade,
                s["id"],
                f"Предложено пройти тест на {GRADE_LABEL[grade]}",
            )
            kind = "lower"
        else:
            kind = "placement"
        s = session_record(cand, kind, grade, last_test, cand["theta"], True, grade)
        add_history(
            cand["id"],
            last_test,
            "test_passed",
            spec,
            None,
            grade,
            s["id"],
            f"Подтверждён грейд {GRADE_LABEL[grade]}, θ = {cand['theta']}",
        )
        add_history(
            cand["id"],
            last_test,
            "grade_changed",
            spec,
            None,
            grade,
            s["id"],
            f"Присвоена категория {cat_label(spec, grade)}",
        )
        if gi < 3 and cand["theta"] - THETA_CENTER[grade] > 0.25:
            add_history(
                cand["id"],
                last_test,
                "offer_higher",
                spec,
                grade,
                GRADE_IDS[gi + 1],
                s["id"],
                "Уверенный результат: можно попробовать грейд выше после окончания кулдауна",
            )
    # незавершённый тест у кандидата 39 (онбординг)
    cand = CANDIDATES[38]
    TEST_SESSIONS.append(
        {
            "id": len(TEST_SESSIONS) + 1,
            "candidate_id": cand["id"],
            "specialization": cand["specialization"],
            "target_grade": "junior",
            "kind": "placement",
            "status": "in_progress",
            "started_at": iso(NOW - timedelta(minutes=7)),
            "finished_at": None,
            "items_answered": 4,
            "max_items": 15,
            "theta": None,
            "se": None,
            "ci_low": None,
            "ci_high": None,
            "result_grade": None,
            "result_category": None,
            "passed": None,
            "topic_scores": [],
        }
    )


# ---------------------------------------------------------------- потребности, вакансии


def eligible(c: J) -> bool:
    return bool(c["grade"]) and c["publication_consent"] and not c["job_search_paused"]


def count_in_category(category: str) -> int:
    return sum(1 for c in CANDIDATES if eligible(c) and c["category"] == category)


NEED_DEFS = [
    # company, recruiter, title, raw_text, spec, grade, req, des, team, format, city, from, to, status, days
    (
        1,
        1,
        "Middle Python-разработчик в платёжный шлюз",
        "Нужен мидл на Python в платёжный шлюз, гибрид или удалёнка, 200–280к",
        "backend",
        "middle",
        ["python", "postgresql"],
        ["kafka", "redis"],
        "Платёжный шлюз, команда 6 человек",
        "remote",
        None,
        200_000,
        280_000,
        "active",
        6,
    ),
    (
        1,
        2,
        "Senior Go-разработчик",
        "нужен сеньор на Go в финтех, удалёнка, 300–400к",
        "backend",
        "senior",
        ["go", "postgresql"],
        ["kafka", "kubernetes"],
        "Ядро процессинга",
        "remote",
        None,
        300_000,
        400_000,
        "active",
        3,
    ),
    (
        2,
        4,
        "Junior Data Scientist",
        "Ищем джуна в DS: pandas, sklearn, SQL. Питер, гибрид, 90–130к",
        "data_ml",
        "junior",
        ["python", "pandas", "sql"],
        ["scikit_learn"],
        "Прогноз спроса для магазинов",
        "hybrid",
        "Санкт-Петербург",
        90_000,
        130_000,
        "active",
        8,
    ),
    (
        2,
        5,
        "QA Automation Middle",
        "Автотестировщик мидл, Playwright или Selenium, удалённо, 160–220к",
        "qa",
        "middle",
        ["python", "playwright"],
        ["allure", "postman"],
        "Команда качества",
        "remote",
        None,
        160_000,
        220_000,
        "active",
        4,
    ),
    (
        3,
        6,
        "DevOps-инженер",
        "DevOps мидл, k8s, terraform, офис Новосибирск, 180–250к",
        "devops",
        "middle",
        ["kubernetes", "terraform"],
        ["prometheus"],
        "Платформенная команда",
        "office",
        "Новосибирск",
        180_000,
        250_000,
        "closed",
        15,
    ),
]
NEEDS: list[J] = []
VACANCY_DEFS = [
    (
        1,
        "Middle Python-разработчик",
        "backend",
        "middle",
        ["python", "fastapi", "postgresql"],
        ["kafka"],
        "hybrid",
        "Москва",
        200_000,
        280_000,
        "published",
    ),
    (
        1,
        "Senior Android-разработчик",
        "mobile",
        "senior",
        ["kotlin", "jetpack_compose"],
        ["android_sdk"],
        "remote",
        None,
        320_000,
        420_000,
        "published",
    ),
    (
        1,
        "Frontend-разработчик (React)",
        "frontend",
        "junior",
        ["react", "typescript"],
        ["redux"],
        "hybrid",
        "Москва",
        100_000,
        150_000,
        "published",
    ),
    (
        2,
        "ML-инженер",
        "data_ml",
        "middle",
        ["python", "pytorch", "sql"],
        ["mlflow", "airflow"],
        "remote",
        None,
        230_000,
        310_000,
        "published",
    ),
    (
        2,
        "Аналитик данных (стажёр)",
        "data_ml",
        "intern",
        ["sql", "pandas"],
        ["jupyter"],
        "office",
        "Санкт-Петербург",
        45_000,
        65_000,
        "published",
    ),
    (
        2,
        "QA-инженер",
        "qa",
        "junior",
        ["postman", "sql"],
        ["selenium"],
        "hybrid",
        "Санкт-Петербург",
        80_000,
        120_000,
        "unpublished",
    ),
    (
        3,
        "DevOps-инженер",
        "devops",
        "middle",
        ["docker", "kubernetes", "terraform"],
        ["grafana"],
        "office",
        "Новосибирск",
        180_000,
        250_000,
        "published",
    ),
    (
        3,
        "Backend-разработчик Go",
        "backend",
        "junior",
        ["go", "postgresql"],
        ["redis"],
        "remote",
        None,
        110_000,
        160_000,
        "draft",
    ),
]
VACANCIES: list[J] = []


def build_needs_and_vacancies() -> None:
    for i, d in enumerate(NEED_DEFS, start=1):
        (
            company,
            rec,
            title,
            raw,
            spec,
            grade,
            req,
            des,
            team,
            fmt,
            city,
            sfrom,
            sto,
            status,
            days,
        ) = d
        NEEDS.append(
            {
                "id": i,
                "company_id": company,
                "recruiter_id": rec,
                "title": title,
                "raw_text": raw,
                "specialization": spec,
                "grade": grade,
                "skills_required": req,
                "skills_desired": des,
                "team_description": team,
                "work_format": fmt,
                "city": city,
                "salary_from": sfrom,
                "salary_to": sto,
                "category": cat_id(spec, grade),
                "category_label": cat_label(spec, grade),
                "status": status,
                "candidates_count": count_in_category(cat_id(spec, grade)),
                "created_at": iso(days_ago(days)),
            }
        )
    for i, d in enumerate(VACANCY_DEFS, start=1):
        company, title, spec, grade, req, des, fmt, city, sfrom, sto, status = d
        created = days_ago(rng.randint(5, 25))
        VACANCIES.append(
            {
                "id": i,
                "company_id": company,
                "company_name": COMPANY_NAME[company],
                "title": title,
                "description": f"{COMPANY_NAME[company]} ищет специалиста: {title.lower()}. "
                f"Стек: {', '.join(req + des)}. Формат: "
                f"{ {'office': 'офис', 'hybrid': 'гибрид', 'remote': 'удалёнка'}[fmt] }.",
                "specialization": spec,
                "grade": grade,
                "skills_required": req,
                "skills_desired": des,
                "work_format": fmt,
                "city": city,
                "salary_from": sfrom,
                "salary_to": sto,
                "category": cat_id(spec, grade),
                "category_label": cat_label(spec, grade),
                "status": status,
                "applications_count": 0,
                "created_at": iso(created),
                "published_at": iso(created + timedelta(hours=2)) if status != "draft" else None,
                "my_application_id": None,
            }
        )


# ---------------------------------------------------------------- приглашения и отклики

INVITATIONS: list[J] = []
INVITATION_EVENTS: list[J] = []
APPLICATIONS: list[J] = []
AUDIT: list[J] = []


def audit(
    at: datetime,
    actor: int | None,
    role: str | None,
    action: str,
    target_type: str,
    target_id: int | None,
    summary: str,
    details: J | None = None,
) -> None:
    AUDIT.append(
        {
            "id": 0,
            "at": iso(at),
            "actor_user_id": actor,
            "actor_role": role,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "summary": summary,
            "details": details or {},
        }
    )


def event(inv_id: int, typ: str, at: datetime, role: str | None) -> None:
    INVITATION_EVENTS.append(
        {
            "id": len(INVITATION_EVENTS) + 1,
            "invitation_id": inv_id,
            "type": typ,
            "at": iso(at),
            "actor_role": role,
        }
    )


INVITATION_PLAN = [
    # (candidate_id, recruiter_id, status, decline_reason, created_days_ago)
    (1, 1, "accepted", None, 9),
    (1, 4, "sent", None, 1),
    (1, 6, "declined", "not_interested_domain", 12),
    (1, 5, "viewed", None, 3),
    (2, 1, "viewed", None, 2),
    (3, 2, "sent", None, 1),
    (4, 1, "declined", "salary_too_low", 10),
    (5, 2, "accepted", None, 14),
    (6, 1, "expired", None, 15),
    (7, 3, "withdrawn", None, 8),
    (8, 4, "accepted", None, 11),
    (9, 5, "sent", None, 2),
    (10, 4, "declined", "wrong_stack", 6),
    (11, 6, "viewed", None, 4),
    (12, 7, "expired", None, 20),
    (13, 5, "accepted", None, 13),
    (14, 2, "viewed", None, 5),
    (15, 4, "declined", "not_looking", 7),
    (16, 1, "accepted", None, 16),
    (21, 3, "sent", None, 0),
]


def build_invitations() -> None:
    rec_by_id = {r["id"]: r for r in RECRUITERS}
    cand_by_id = {c["id"]: c for c in CANDIDATES}
    for idx, (cid, rid, status, reason, ago) in enumerate(INVITATION_PLAN, start=1):
        cand, rec = cand_by_id[cid], rec_by_id[rid]
        created = days_ago(ago, hour=10 + idx % 8)
        min_sal = cand["min_salary"] or 100_000
        sal_to = round_to(min_sal * rng.uniform(1.05, 1.35))
        sal_from = round_to(min(sal_to, min_sal * rng.uniform(0.85, 1.0)))
        if reason == "salary_too_low":
            sal_to = round_to(min_sal * 1.0) + 10_000
            sal_from = round_to(min_sal * 0.8)
        viewed = created + timedelta(hours=rng.randint(1, 20)) if status != "sent" else None
        if status == "expired":
            viewed = None
        if status == "withdrawn":
            viewed = None
        responded = (
            viewed + timedelta(hours=rng.randint(1, 30))
            if status in ("accepted", "declined") and viewed
            else None
        )
        expires = created + timedelta(days=7)
        withdrawn = created + timedelta(days=2) if status == "withdrawn" else None
        contact_type = rng.choice(["telegram", "email", "phone"])
        contact_value = {"telegram": rec["telegram"], "email": rec["email"], "phone": rec["phone"]}[
            contact_type
        ]
        INVITATIONS.append(
            {
                "id": idx,
                "candidate_id": cid,
                "recruiter_id": rid,
                "company_id": rec["company_id"],
                "company_name": COMPANY_NAME[rec["company_id"]],
                "recruiter_name": rec["full_name"],
                "need_id": next(
                    (
                        n["id"]
                        for n in NEEDS
                        if n["company_id"] == rec["company_id"]
                        and n["category"] == cand["category"]
                    ),
                    None,
                ),
                "vacancy_id": next(
                    (
                        v["id"]
                        for v in VACANCIES
                        if v["company_id"] == rec["company_id"]
                        and v["category"] == cand["category"]
                        and v["status"] == "published"
                    ),
                    None,
                ),
                "category": cand["category"],
                "category_label": cand["category_label"],
                "description": f"{COMPANY_NAME[rec['company_id']]} приглашает на позицию "
                f"{cand['category_label']}. Расскажем о задачах на созвоне.",
                "salary_from": sal_from,
                "salary_to": sal_to,
                "contact_method": {"type": contact_type, "value": contact_value},
                "task_text": (
                    "Опишите, как бы вы спроектировали сервис уведомлений (до 10 предложений)."
                    if idx % 4 == 0
                    else None
                ),
                "status": status,
                "decline_reason": reason,
                "decline_comment": "Сейчас рассматриваю другие сферы"
                if reason == "not_interested_domain"
                else None,
                "created_at": iso(created),
                "viewed_at": iso(viewed) if viewed else None,
                "responded_at": iso(responded) if responded else None,
                "expires_at": iso(expires),
                "withdrawn_at": iso(withdrawn) if withdrawn else None,
            }
        )
        event(idx, "created", created, "recruiter")
        if viewed:
            event(idx, "viewed", viewed, "candidate")
        if status == "accepted" and responded:
            event(idx, "accepted", responded, "candidate")
            event(idx, "contacts_revealed", responded, None)
            audit(
                responded,
                rec["user_id"],
                "recruiter",
                "contacts_revealed",
                "invitation",
                idx,
                f"Раскрыты контакты: {cand['pseudonym']} ↔ {COMPANY_NAME[rec['company_id']]}",
                {"candidate_id": cid, "company_id": rec["company_id"]},
            )
        if status == "declined" and responded:
            event(idx, "declined", responded, "candidate")
        if status == "expired":
            event(idx, "expired", expires, None)
        if status == "withdrawn" and withdrawn:
            event(idx, "withdrawn", withdrawn, "recruiter")

    plan = [
        (1, 4, "viewed"),
        (1, 1, "invited"),
        (2, 1, "new"),
        (3, 1, "rejected"),
        (26, 3, "new"),
        (17, 4, "new"),
        (18, 4, "viewed"),
        (19, 5, "new"),
        (22, 7, "viewed"),
        (24, 7, "new"),
        (27, 2, "new"),
        (28, 3, "rejected"),
    ]
    for idx, (cid, vid, status) in enumerate(plan, start=1):
        vac = next(v for v in VACANCIES if v["id"] == vid)
        created = days_ago(rng.randint(0, 6), hour=9 + idx % 10)
        APPLICATIONS.append(
            {
                "id": idx,
                "vacancy_id": vid,
                "candidate_id": cid,
                "vacancy_title": vac["title"],
                "company_id": vac["company_id"],
                "company_name": vac["company_name"],
                "cover_letter": "Здравствуйте! Интересна вакансия, готов обсудить детали.",
                "status": status,
                "created_at": iso(created),
                "updated_at": iso(
                    created + timedelta(hours=rng.randint(1, 20)) if status != "new" else created
                ),
            }
        )
        vac["applications_count"] += 1


# ---------------------------------------------------------------- задания, жалобы, журнал

TASK_DEFS = [
    (
        1,
        1,
        "Кэш для медленного API",
        "Сервис справочников отвечает 2 секунды. Как ускорить "
        "ответы без потери актуальности данных?",
        "backend:middle",
    ),
    (
        1,
        2,
        "Идемпотентность платежей",
        "Клиент может повторить запрос оплаты при таймауте. Как не списать деньги дважды?",
        "backend:senior",
    ),
    (
        1,
        3,
        "Состояние формы в React",
        "Форма из 20 полей тормозит при вводе. Что проверить и как исправить?",
        "frontend:junior",
    ),
    (
        2,
        4,
        "Утечка в признаках",
        "Модель прогноза спроса подозрительно точна на валидации. Где искать утечку?",
        "data_ml:middle",
    ),
    (
        2,
        5,
        "Флаки-тесты",
        "Набор автотестов падает в 10% прогонов без изменений кода. Ваш план расследования?",
        "qa:middle",
    ),
    (
        3,
        6,
        "Откат релиза в Kubernetes",
        "После выката сервис отдаёт 5xx. Опишите быстрый и безопасный откат.",
        "devops:middle",
    ),
]
REGULAR_TASKS: list[J] = []
SUBMISSIONS: list[J] = []


def build_tasks() -> None:
    for i, (company, rec, title, statement, category) in enumerate(TASK_DEFS, start=1):
        spec, grade = category.split(":")
        REGULAR_TASKS.append(
            {
                "id": i,
                "company_id": company,
                "company_name": COMPANY_NAME[company],
                "recruiter_id": rec,
                "title": title,
                "statement": statement,
                "category": category,
                "category_label": cat_label(spec, grade),
                "deadline_days": 7,
                "status": "active",
                "submissions_count": 0,
                "created_at": iso(days_ago(rng.randint(10, 30))),
            }
        )
    answers = {
        "text": "Сначала замерил бы, где теряется время, затем добавил кэш.",
        "code": "@lru_cache(maxsize=1024)\ndef get_dict(key): ...",
        "approach": "Ключ идемпотентности в заголовке, уникальный индекс в БД, повтор "
        "возвращает сохранённый результат.",
    }
    sid = 0
    for cand in CANDIDATES:
        if not cand["category"]:
            continue
        tasks = [t for t in REGULAR_TASKS if t["category"].split(":")[0] == cand["specialization"]]
        if not tasks:
            continue
        n = 3 if cand["id"] == 1 else rng.choice([0, 0, 1, 1, 2])
        for k in range(n):
            task = tasks[k % len(tasks)]
            sid += 1
            assigned = days_ago(3 + 9 * (n - 1 - k))
            is_active = k == n - 1 and (cand["id"] == 1 or rng.random() < 0.5)
            status = (
                "assigned"
                if is_active
                else rng.choice(["graded", "graded", "submitted", "expired"])
            )
            kind = rng.choice(["text", "code", "approach"])
            submitted = (
                assigned + timedelta(days=rng.randint(1, 4))
                if status in ("graded", "submitted")
                else None
            )
            score = rng.randint(1, 3) if status == "graded" else None
            SUBMISSIONS.append(
                {
                    "id": sid,
                    "task_id": task["id"],
                    "candidate_id": cand["id"],
                    "task_title": task["title"],
                    "statement": task["statement"],
                    "company_name": task["company_name"],
                    "status": status,
                    "assigned_at": iso(assigned),
                    "due_at": iso(assigned + timedelta(days=7)),
                    "answer_kind": kind if submitted else None,
                    "answer_text": answers[kind] if submitted else None,
                    "submitted_at": iso(submitted) if submitted else None,
                    "score": score,
                    "grader_comment": {
                        1: "Направление верное, мало деталей",
                        2: "Хороший разбор",
                        3: "Отлично, с учётом крайних случаев",
                    }.get(score or 0),
                    "graded_at": iso(submitted + timedelta(days=1))
                    if score is not None and submitted
                    else None,
                }
            )
            task["submissions_count"] += 1


REPORTS: list[J] = []
CONSENTS: list[J] = []


def build_misc() -> None:
    report_defs = [
        (
            3,
            11,
            11,
            None,
            "fake_vacancy",
            "После созвона попросили оплатить «обучение» за 15 000 ₽.",
            "new",
            None,
            1,
        ),
        (
            3,
            12,
            12,
            None,
            "salary_mismatch",
            "В приглашении 180 тысяч, на звонке сказали 90.",
            "in_review",
            None,
            3,
        ),
        (3, 22, None, 7, "spam", "Одно и то же приглашение приходит каждый день.", "new", None, 2),
        (
            2,
            15,
            15,
            None,
            "rude",
            "Грубо разговаривали на собеседовании.",
            "rejected",
            "Проверили переписку: нарушений не найдено.",
            6,
        ),
    ]
    for i, (company, cand, inv, vac, reason, text, status, resolution, ago) in enumerate(
        report_defs, 1
    ):
        created = days_ago(ago)
        REPORTS.append(
            {
                "id": i,
                "company_id": company,
                "company_name": COMPANY_NAME[company],
                "reporter_candidate_id": cand,
                "invitation_id": inv,
                "vacancy_id": vac,
                "reason": reason,
                "text": text,
                "status": status,
                "resolution": resolution,
                "created_at": iso(created),
                "resolved_at": iso(created + timedelta(days=1))
                if status in ("resolved", "rejected")
                else None,
            }
        )
    for u in USERS:
        created = datetime.fromisoformat(u["created_at"])
        CONSENTS.append(
            {
                "id": 0,
                "user_id": u["id"],
                "type": "processing",
                "version": CONSENT_VERSION,
                "granted": True,
                "granted_at": iso(created),
                "revoked_at": None,
            }
        )
        if u["role"] == "candidate":
            cand = CANDIDATES[u["id"] - 1]
            granted = cand["publication_consent"]
            CONSENTS.append(
                {
                    "id": 0,
                    "user_id": u["id"],
                    "type": "publication",
                    "version": CONSENT_VERSION,
                    "granted": granted,
                    "granted_at": iso(created) if granted or u["id"] == 37 else None,
                    "revoked_at": iso(days_ago(2)) if not granted else None,
                }
            )
    for i, c in enumerate(CONSENTS, 1):
        c["id"] = i

    for h in GRADE_HISTORY:
        if h["event"] == "grade_changed":
            audit(
                datetime.fromisoformat(h["at"]),
                None,
                None,
                "grade_changed",
                "candidate",
                h["candidate_id"],
                h["comment"],
                {"grade_to": h["grade_to"]},
            )
    for it in ITEMS:
        if it["leak_flag"]:
            audit(
                days_ago(rng.randint(1, 5)),
                None,
                None,
                "item_leak_flagged",
                "item",
                it["id"],
                f"Возможная утечка шаблона «{it['title']}»",
                {"leak_score": it["leak_score"]},
            )
        if it["status"] == "retired":
            audit(
                days_ago(rng.randint(0, 3)),
                48,
                "admin",
                "item_retired",
                "item",
                it["id"],
                f"Шаблон «{it['title']}» выведен из оборота",
            )
    audit(
        days_ago(4),
        48,
        "admin",
        "user_blocked",
        "user",
        36,
        "Пользователь заблокирован: подозрение на передачу ответов",
        {"reason": "cheating"},
    )
    audit(
        days_ago(10),
        48,
        "admin",
        "settings_updated",
        "settings",
        None,
        "Квота приглашений изменена: 15 → 20",
        {"invitation_quota": [15, 20]},
    )
    audit(
        days_ago(2),
        37,
        "candidate",
        "consent_revoked",
        "consent",
        None,
        "Отозвано согласие на публикацию профиля",
        {"type": "publication"},
    )
    AUDIT.sort(key=lambda a: a["at"])
    for i, a in enumerate(AUDIT, 1):
        a["id"] = i


SURVEY_QUESTIONS: list[J] = [
    {
        "id": "q1",
        "text": "Чем вам больше всего нравится заниматься?",
        "kind": "single",
        "required": True,
        "options": [
            {
                "id": "q1_api",
                "label": "Писать серверную логику и API",
                "specializations": ["backend"],
            },
            {
                "id": "q1_ui",
                "label": "Делать интерфейсы в браузере",
                "specializations": ["frontend"],
            },
            {
                "id": "q1_apps",
                "label": "Делать мобильные приложения",
                "specializations": ["mobile"],
            },
            {
                "id": "q1_data",
                "label": "Искать закономерности в данных",
                "specializations": ["data_ml"],
            },
            {
                "id": "q1_bugs",
                "label": "Находить ошибки и ломать системы",
                "specializations": ["qa"],
            },
            {
                "id": "q1_infra",
                "label": "Настраивать серверы и автоматизацию",
                "specializations": ["devops"],
            },
        ],
    },
    {
        "id": "q2",
        "text": "Какие технологии вы использовали в последних проектах?",
        "kind": "multi",
        "required": True,
        "options": [
            {"id": "q2_python", "label": "Python", "specializations": ["backend", "data_ml", "qa"]},
            {"id": "q2_go_java", "label": "Go / Java / C#", "specializations": ["backend"]},
            {"id": "q2_js", "label": "JavaScript / TypeScript", "specializations": ["frontend"]},
            {"id": "q2_mobile", "label": "Kotlin / Swift / Flutter", "specializations": ["mobile"]},
            {"id": "q2_sql", "label": "SQL", "specializations": ["backend", "data_ml"]},
            {
                "id": "q2_ml",
                "label": "pandas / PyTorch / scikit-learn",
                "specializations": ["data_ml"],
            },
            {
                "id": "q2_tests",
                "label": "Selenium / Playwright / Postman",
                "specializations": ["qa"],
            },
            {
                "id": "q2_ops",
                "label": "Docker / Kubernetes / Terraform",
                "specializations": ["devops"],
            },
        ],
    },
    {
        "id": "q3",
        "text": "Какая задача из списка вам ближе?",
        "kind": "single",
        "required": True,
        "options": [
            {
                "id": "q3_db",
                "label": "Ускорить медленный запрос к базе",
                "specializations": ["backend"],
            },
            {
                "id": "q3_render",
                "label": "Убрать лишние перерисовки страницы",
                "specializations": ["frontend"],
            },
            {
                "id": "q3_offline",
                "label": "Сделать офлайн-режим приложения",
                "specializations": ["mobile"],
            },
            {"id": "q3_model", "label": "Улучшить качество модели", "specializations": ["data_ml"]},
            {
                "id": "q3_regress",
                "label": "Составить регресс-набор тестов",
                "specializations": ["qa"],
            },
            {
                "id": "q3_deploy",
                "label": "Сделать выкладку без простоя",
                "specializations": ["devops"],
            },
        ],
    },
    {
        "id": "q4",
        "text": "Сколько лет коммерческого опыта в IT?",
        "kind": "single",
        "required": True,
        "options": [
            {"id": "q4_0", "label": "Нет опыта", "specializations": []},
            {"id": "q4_1", "label": "До 2 лет", "specializations": []},
            {"id": "q4_3", "label": "2–5 лет", "specializations": []},
            {"id": "q4_5", "label": "Больше 5 лет", "specializations": []},
        ],
    },
    {
        "id": "q5",
        "text": "Какую роль в команде вы обычно берёте?",
        "kind": "single",
        "required": False,
        "options": [
            {"id": "q5_dev", "label": "Исполнитель задач", "specializations": []},
            {"id": "q5_lead", "label": "Веду задачи других и ревьюю", "specializations": []},
            {
                "id": "q5_arch",
                "label": "Проектирую решения",
                "specializations": ["backend", "devops"],
            },
        ],
    },
    {
        "id": "q6",
        "text": "Что вам интереснее изучать дальше?",
        "kind": "multi",
        "required": False,
        "options": [
            {
                "id": "q6_arch",
                "label": "Архитектуру распределённых систем",
                "specializations": ["backend", "devops"],
            },
            {
                "id": "q6_ux",
                "label": "UX и доступность интерфейсов",
                "specializations": ["frontend", "mobile"],
            },
            {"id": "q6_dl", "label": "Нейросети и LLM", "specializations": ["data_ml"]},
            {"id": "q6_auto", "label": "Автоматизацию тестирования", "specializations": ["qa"]},
            {
                "id": "q6_sec",
                "label": "Безопасность",
                "specializations": ["backend", "devops", "qa"],
            },
        ],
    },
    {
        "id": "q7",
        "text": "Где вы чаще всего запускаете свой код?",
        "kind": "single",
        "required": False,
        "options": [
            {"id": "q7_server", "label": "На сервере", "specializations": ["backend", "devops"]},
            {"id": "q7_browser", "label": "В браузере", "specializations": ["frontend"]},
            {"id": "q7_phone", "label": "На телефоне", "specializations": ["mobile"]},
            {"id": "q7_notebook", "label": "В Jupyter-ноутбуке", "specializations": ["data_ml"]},
        ],
    },
    {
        "id": "q8",
        "text": "Опишите в двух словах последний проект",
        "kind": "text",
        "required": False,
        "options": [],
    },
]

VALIDATION_CHARTS: list[J] = []


def build_validation() -> None:
    r = random.Random(SEED + 1)
    VALIDATION_CHARTS.append(
        {
            "id": "grade_accuracy",
            "title": "Точность определения грейда",
            "description": "Доля кандидатов, у которых грейд по тесту совпал с истинным (точно и ±1).",
            "chart_type": "bar",
            "x_label": "Грейд",
            "y_label": "Доля",
            "series": [
                {
                    "name": "Точно",
                    "points": [
                        {"x": GRADE_LABEL[g], "y": v}
                        for g, v in zip(GRADE_IDS, [0.81, 0.74, 0.71, 0.83], strict=True)
                    ],
                },
                {
                    "name": "±1 грейд",
                    "points": [
                        {"x": GRADE_LABEL[g], "y": v}
                        for g, v in zip(GRADE_IDS, [0.99, 0.97, 0.98, 0.99], strict=True)
                    ],
                },
            ],
            "summary": {"exact": 0.76, "within_one": 0.98},
            "is_stub": True,
        }
    )
    VALIDATION_CHARTS.append(
        {
            "id": "retest_stability",
            "title": "Стабильность при повторном тесте",
            "description": "Совпадение грейда при повторном прохождении (другие варианты задач).",
            "chart_type": "bar",
            "x_label": "Специализация",
            "y_label": "Доля совпадений",
            "series": [
                {
                    "name": "Совпадение",
                    "points": [
                        {"x": SPEC_LABEL[s["id"]], "y": round(r.uniform(0.78, 0.9), 2)}
                        for s in SPECIALIZATIONS
                    ],
                }
            ],
            "summary": {"agreement": 0.84, "cohen_kappa": 0.77},
            "is_stub": True,
        }
    )
    pts = []
    for it in ITEMS:
        pts.append(
            {
                "x": it["a"],
                "y": round(min(0.7, max(0.05, it["a"] * 0.28 + r.uniform(-0.08, 0.08))), 2),
            }
        )
    VALIDATION_CHARTS.append(
        {
            "id": "item_discrimination",
            "title": "Различающая сила задач",
            "description": "IRT-параметр a против точечно-бисериальной корреляции по каждому шаблону.",
            "chart_type": "scatter",
            "x_label": "a (IRT)",
            "y_label": "Точечно-бисериальная корреляция",
            "series": [{"name": "Шаблоны", "points": pts}],
            "summary": {"mean_point_biserial": round(statistics.mean(p["y"] for p in pts), 2)},
            "is_stub": True,
        }
    )
    pts = []
    for _ in range(60):
        t = round(r.gauss(0, 1), 2)
        pts.append({"x": t, "y": round(t + r.gauss(0, 0.38), 2)})
    VALIDATION_CHARTS.append(
        {
            "id": "theta_recovery",
            "title": "Восстановление уровня θ",
            "description": "Истинный уровень синтетического кандидата против оценки теста.",
            "chart_type": "scatter",
            "x_label": "Истинный θ",
            "y_label": "Оценка θ",
            "series": [{"name": "Кандидаты", "points": pts}],
            "summary": {"correlation": 0.91, "mean_test_length": 12.4},
            "is_stub": True,
        }
    )
    VALIDATION_CHARTS.append(
        {
            "id": "test_length",
            "title": "Длина адаптивного теста",
            "description": "Распределение числа задач до остановки (SE < 0,35 или 15 задач).",
            "chart_type": "histogram",
            "x_label": "Задач в тесте",
            "y_label": "Кандидатов",
            "series": [
                {
                    "name": "Тесты",
                    "points": [
                        {"x": n, "y": c}
                        for n, c in zip(
                            range(8, 16), [12, 41, 96, 160, 210, 180, 140, 161], strict=True
                        )
                    ],
                }
            ],
            "summary": {"mean": 12.4, "share_max_length": 0.16},
            "is_stub": True,
        }
    )
    VALIDATION_CHARTS.append(
        {
            "id": "precision_at_10",
            "title": "Качество подбора: precision@10 и nDCG@10",
            "description": "Наш подбор против базовой линии «поиск по ключевым словам резюме».",
            "chart_type": "bar",
            "x_label": "Метрика",
            "y_label": "Значение",
            "series": [
                {
                    "name": "fsp-talent",
                    "points": [{"x": "precision@10", "y": 0.71}, {"x": "nDCG@10", "y": 0.78}],
                },
                {
                    "name": "Ключевые слова",
                    "points": [{"x": "precision@10", "y": 0.42}, {"x": "nDCG@10", "y": 0.47}],
                },
            ],
            "summary": {
                "precision_at_10": 0.71,
                "ndcg_at_10": 0.78,
                "baseline_precision_at_10": 0.42,
                "baseline_ndcg_at_10": 0.47,
            },
            "is_stub": True,
        }
    )
    VALIDATION_CHARTS.append(
        {
            "id": "leak_detector",
            "title": "Детектор утечек",
            "description": "Симуляция: 20% шаблонов слиты, 10% кандидатов — «читеры». Завышение грейда "
            "без защиты и с защитой по неделям.",
            "chart_type": "line",
            "x_label": "Неделя",
            "y_label": "Доля завышенных грейдов",
            "series": [
                {
                    "name": "Без защиты",
                    "points": [
                        {"x": w, "y": v}
                        for w, v in zip(
                            range(1, 7), [0.04, 0.09, 0.15, 0.21, 0.26, 0.3], strict=True
                        )
                    ],
                },
                {
                    "name": "С защитой",
                    "points": [
                        {"x": w, "y": v}
                        for w, v in zip(
                            range(1, 7), [0.04, 0.05, 0.04, 0.03, 0.03, 0.02], strict=True
                        )
                    ],
                },
            ],
            "summary": {"recall": 0.9, "precision": 0.82},
            "is_stub": True,
        }
    )


VACANCY_TESTS: list[J] = []


def build_vacancy_tests() -> None:
    by_code = {it["topic"]: it for it in ITEMS if it["status"] in ("active", "pilot")}
    VACANCY_TESTS.append(
        {
            "id": 1,
            "vacancy_title": "Middle Python-разработчик (платежи)",
            "vacancy_text": "Ищем Middle Python-разработчика в команду платежей. FastAPI, PostgreSQL, "
            "Redis, Kafka. Нужно понимать транзакции, конкурентный доступ и уметь "
            "проектировать REST API. Плюсом будет опыт с OAuth 2.0.",
            "specialization": "backend",
            "grade": "middle",
            "parser": "rules",
            "topics": [
                {
                    "topic": "backend.http_api",
                    "label": TOPIC_LABEL["backend.http_api"],
                    "matched_by": ["REST API", "FastAPI"],
                    "confidence": 0.9,
                    "covered": True,
                },
                {
                    "topic": "backend.databases",
                    "label": TOPIC_LABEL["backend.databases"],
                    "matched_by": ["PostgreSQL", "транзакции"],
                    "confidence": 0.95,
                    "covered": True,
                },
                {
                    "topic": "backend.concurrency",
                    "label": TOPIC_LABEL["backend.concurrency"],
                    "matched_by": ["конкурентный доступ"],
                    "confidence": 0.7,
                    "covered": True,
                },
                {
                    "topic": "backend.security",
                    "label": TOPIC_LABEL["backend.security"],
                    "matched_by": ["OAuth 2.0"],
                    "confidence": 0.6,
                    "covered": False,
                },
            ],
            "items": [
                {
                    "item_id": by_code[t]["id"],
                    "code": by_code[t]["code"],
                    "title": by_code[t]["title"],
                    "topic": t,
                    "reason": f"Тема «{TOPIC_LABEL[t]}» найдена в тексте вакансии",
                }
                for t in ("backend.http_api", "backend.databases", "backend.concurrency")
            ],
            "drafts": [
                {
                    "topic": "backend.security",
                    "label": TOPIC_LABEL["backend.security"],
                    "title": "Поток Authorization Code в OAuth 2.0",
                    "format": "ordering",
                    "prompt": "Расположите шаги потока Authorization Code + PKCE в правильном порядке.",
                    "status": "draft",
                }
            ],
            "explanation": [
                "Грейд Middle взят из заголовка вакансии",
                "3 темы покрыты активными шаблонами банка",
                "Для темы «Безопасность веб-приложений» шаблонов нет — создан черновик, "
                "после одобрения админом он пойдёт в тесты как непроверочный",
            ],
        }
    )
    VACANCY_TESTS.append(
        {
            "id": 2,
            "vacancy_title": "Junior Data Scientist",
            "vacancy_text": "Junior DS в ритейл: pandas, scikit-learn, SQL, базовая статистика, "
            "метрики качества классификации.",
            "specialization": "data_ml",
            "grade": "junior",
            "parser": "rules",
            "topics": [
                {
                    "topic": "data_ml.statistics",
                    "label": TOPIC_LABEL["data_ml.statistics"],
                    "matched_by": ["статистика"],
                    "confidence": 0.85,
                    "covered": True,
                },
                {
                    "topic": "data_ml.ml_basics",
                    "label": TOPIC_LABEL["data_ml.ml_basics"],
                    "matched_by": ["scikit-learn"],
                    "confidence": 0.9,
                    "covered": True,
                },
                {
                    "topic": "data_ml.metrics",
                    "label": TOPIC_LABEL["data_ml.metrics"],
                    "matched_by": ["метрики качества"],
                    "confidence": 0.8,
                    "covered": True,
                },
            ],
            "items": [
                {
                    "item_id": by_code[t]["id"],
                    "code": by_code[t]["code"],
                    "title": by_code[t]["title"],
                    "topic": t,
                    "reason": f"Тема «{TOPIC_LABEL[t]}» найдена в тексте вакансии",
                }
                for t in ("data_ml.statistics", "data_ml.ml_basics", "data_ml.metrics")
            ],
            "drafts": [],
            "explanation": ["Грейд Junior взят из заголовка вакансии", "Все темы покрыты банком"],
        }
    )


PLATFORM_SETTINGS = [
    {
        "id": "default",
        "grade_thresholds": [
            {"specialization": s["id"], "junior_from": -1.0, "middle_from": 0.0, "senior_from": 1.0}
            for s in SPECIALIZATIONS
        ],
        "grade_change_cooldown_days": 90,
        "retry_cooldown_days": 30,
        "invitation_quota": 20,
        "invitation_ttl_days": 7,
        "cat_se_stop": 0.35,
        "cat_max_items": 15,
        "exposure_max_share": 0.25,
        "ranking_weights": {
            "stack": 0.3,
            "theta": 0.25,
            "fsp": 0.15,
            "freshness": 0.1,
            "salary": 0.1,
            "work_format": 0.1,
        },
        "consent_version": CONSENT_VERSION,
    }
]

DEMO_ACCOUNTS = [
    {
        "id": 1,
        "role": "candidate",
        "email": "candidate@example.com",
        "password": "demo1234",
        "user_id": 1,
        "is_default": True,
        "description": "Соискатель с ФСП ID: Backend · Middle, есть приглашения и задание",
    },
    {
        "id": 2,
        "role": "candidate",
        "email": "candidate.nofsp@example.com",
        "password": "demo1234",
        "user_id": 26,
        "is_default": False,
        "description": "Соискатель без истории ФСП: Frontend · Junior",
    },
    {
        "id": 3,
        "role": "recruiter",
        "email": "recruiter@example.com",
        "password": "demo1234",
        "user_id": 41,
        "is_default": True,
        "description": "Рекрутер компании «Северный код», есть потребности и приглашения",
    },
    {
        "id": 4,
        "role": "admin",
        "email": "admin@example.com",
        "password": "demo1234",
        "user_id": 48,
        "is_default": True,
        "description": "Администратор платформы",
    },
]


def write(name: str, data: list[J]) -> None:
    ids = [d["id"] for d in data]
    assert len(ids) == len(set(ids)), f"{name}: повторяющиеся id"
    path = OUT_DIR / f"{name}.json"
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"{name}.json: {len(data)}")


def main() -> None:
    build_people()
    build_items()
    build_tests()
    build_needs_and_vacancies()
    build_invitations()
    build_tasks()
    build_misc()
    build_validation()
    build_vacancy_tests()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, data in [
        ("specializations", SPECIALIZATIONS),
        ("grades", GRADES),
        ("categories", CATEGORIES),
        ("topics", TOPICS),
        ("skills", SKILLS),
        ("decline_reasons", DECLINE_REASONS),
        ("users", USERS),
        ("demo_accounts", DEMO_ACCOUNTS),
        ("consents", CONSENTS),
        ("companies", COMPANIES),
        ("recruiters", RECRUITERS),
        ("candidates", CANDIDATES),
        ("fsp_achievements", ACHIEVEMENTS),
        ("survey_questions", SURVEY_QUESTIONS),
        ("items", ITEMS),
        ("test_sessions", TEST_SESSIONS),
        ("grade_history", GRADE_HISTORY),
        ("needs", NEEDS),
        ("vacancies", VACANCIES),
        ("applications", APPLICATIONS),
        ("invitations", INVITATIONS),
        ("invitation_events", INVITATION_EVENTS),
        ("regular_tasks", REGULAR_TASKS),
        ("task_submissions", SUBMISSIONS),
        ("reports", REPORTS),
        ("audit_log", AUDIT),
        ("platform_settings", PLATFORM_SETTINGS),
        ("validation_charts", VALIDATION_CHARTS),
        ("vacancy_tests", VACANCY_TESTS),
    ]:
        write(name, data)


if __name__ == "__main__":
    main()

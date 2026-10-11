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
CONSENT_DATE = datetime(2026, 10, 1, 9, 0, tzinfo=MSK)  # дата этой версии текста согласия

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
    {"id": "salary_too_low", "label": "Зарплата ниже ожиданий"},
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
                {
                    "id": f"{level}_winner",
                    "title": LEVEL_WINNER[level],
                    "level": level,
                    "verified": True,
                }
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
        badges.append(
            {"id": "captain", "title": "Капитан команды", "level": None, "verified": True}
        )
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


def topic_scores(spec: str, theta: float, r: random.Random | None = None) -> list[J]:
    r = r or rng
    scores = []
    for topic in SPEC_TOPICS[spec]:
        p = 1 / (1 + math.exp(-(theta + r.uniform(-0.9, 0.9))))
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
                # флаг ставится при z ≥ 3,5 (z_threshold детектора) — у демо-флагов z выше порога
                "leak_score": round(rng.uniform(3.6, 4.5), 2)
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
    cand: J,
    kind: str,
    target: str,
    start: datetime,
    theta: float,
    passed: bool,
    result_grade: str,
    r: random.Random | None = None,
) -> J:
    r = r or rng
    se = round(r.uniform(0.27, 0.34), 2)
    rec = {
        "id": len(TEST_SESSIONS) + 1,
        "candidate_id": cand["id"],
        "specialization": cand["specialization"],
        "target_grade": target,
        "kind": kind,
        "status": "finished",
        "started_at": iso(start),
        "finished_at": iso(start + timedelta(minutes=r.randint(18, 35))),
        "items_answered": r.randint(11, 15),
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
        else topic_scores(cand["specialization"], theta, r),
    }
    TEST_SESSIONS.append(rec)
    return rec


def build_tests() -> None:
    for cand in CANDIDATES:
        add_tests(cand, rng)
    add_unfinished_test()


def add_tests(cand: J, r: random.Random) -> None:
    """Опрос, тест (иногда сначала неудачная попытка на грейд выше) и история грейда."""
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
        return
    last_test = datetime.fromisoformat(cand["last_test_at"])
    gi = GRADE_IDS.index(grade)
    # иногда сначала неудачная попытка на грейд выше
    if gi < 3 and r.random() < 0.3:
        failed_at = last_test - timedelta(days=r.randint(1, 3))
        higher = GRADE_IDS[gi + 1]
        s = session_record(
            cand, "placement", higher, failed_at, round(cand["theta"] - 0.1, 2), False, grade, r
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
    s = session_record(cand, kind, grade, last_test, cand["theta"], True, grade, r)
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


def add_unfinished_test() -> None:
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


# ---------------------------------------------------------------- демо-банк кандидатов
#
# Кандидаты 1–40 — «сюжетные» (демо-учётки, жалобы, отклики, тесты движка ссылаются на них).
# К ним добавлен банк из кандидатов с id от 50: у всех грейд подтверждён тестом и дано
# согласие на публикацию, чтобы в каждой категории подборка была не пустой. Свой генератор
# случайных чисел — данные кандидатов 1–40 и всё остальное от банка не зависят.

EXTRA_FIRST_ID = 50
xrng = random.Random(SEED + 500)

# Сколько кандидатов в выдаче должно быть в категории вместе с кандидатами 1–40
CATEGORY_TARGET: dict[str, dict[str, int]] = {
    "backend": {"intern": 9, "junior": 15, "middle": 18, "senior": 14},
    "frontend": {"intern": 8, "junior": 14, "middle": 15, "senior": 12},
    "data_ml": {"intern": 8, "junior": 13, "middle": 14, "senior": 12},
    "mobile": {"intern": 6, "junior": 8, "middle": 9, "senior": 7},
    "qa": {"intern": 6, "junior": 9, "middle": 10, "senior": 7},
    "devops": {"intern": 6, "junior": 8, "middle": 10, "senior": 8},
}
# Участники реестра FSP-000101…180 (все с историей) — по одному на кандидата банка
EXTRA_FSP_IDS = [f"FSP-{n:06d}" for n in range(101, 181)]

# Стек: (ядро, дополнительные технологии, вес шаблона)
STACK_TEMPLATES: dict[str, list[tuple[list[str], list[str], int]]] = {
    "backend": [
        (
            ["python", "fastapi", "postgresql"],
            ["redis", "docker", "kafka", "sql", "pytest", "rabbitmq", "kubernetes"],
            3,
        ),
        (["python", "django", "postgresql"], ["redis", "docker", "rabbitmq", "sql", "nginx"], 2),
        (
            ["go", "postgresql", "docker"],
            ["grpc", "kafka", "redis", "kubernetes", "clickhouse", "linux"],
            2,
        ),
        (
            ["java", "spring", "postgresql"],
            ["kafka", "docker", "kubernetes", "redis", "mysql", "rabbitmq"],
            2,
        ),
        (["kotlin", "spring", "postgresql"], ["kafka", "docker", "redis", "grpc"], 1),
        (["csharp", "postgresql", "docker"], ["rabbitmq", "redis", "sql", "kubernetes"], 1),
        (["php", "mysql", "redis"], ["nginx", "docker", "rabbitmq", "linux"], 1),
        (
            ["nodejs", "typescript", "postgresql"],
            ["mongodb", "redis", "docker", "graphql", "kafka"],
            1,
        ),
    ],
    "frontend": [
        (
            ["javascript", "typescript", "react"],
            ["redux", "nextjs", "vite", "jest", "html_css", "tailwind", "playwright", "graphql"],
            4,
        ),
        (["typescript", "vue", "html_css"], ["vite", "jest", "tailwind", "webpack", "cypress"], 2),
        (["typescript", "angular", "html_css"], ["webpack", "jest", "cypress"], 1),
        (["javascript", "react", "html_css"], ["redux", "webpack", "jest", "nodejs"], 2),
        (
            ["typescript", "react", "nextjs"],
            ["nodejs", "graphql", "tailwind", "playwright", "vite"],
            2,
        ),
    ],
    "mobile": [
        (["kotlin", "android_sdk", "jetpack_compose"], ["java", "flutter"], 3),
        (["swift", "ios_sdk", "swiftui"], ["kotlin", "flutter"], 3),
        (["flutter", "dart"], ["kotlin", "swift", "android_sdk"], 2),
        (["react_native", "typescript"], ["javascript", "redux"], 1),
        (["kotlin", "java", "android_sdk"], ["jetpack_compose"], 1),
    ],
    "data_ml": [
        (
            ["python", "pandas", "scikit_learn", "sql"],
            ["numpy", "jupyter", "postgresql", "mlflow", "airflow", "clickhouse"],
            4,
        ),
        (["python", "pytorch", "numpy"], ["pandas", "mlflow", "jupyter", "sql", "docker"], 3),
        (["python", "sql", "spark"], ["airflow", "clickhouse", "kafka", "pandas", "postgresql"], 2),
        (["python", "tensorflow", "pandas"], ["numpy", "jupyter", "sql"], 1),
    ],
    "qa": [
        (["python", "pytest", "playwright"], ["allure", "postman", "sql", "selenium", "jmeter"], 3),
        (["java", "selenium", "testrail"], ["allure", "postman", "sql", "jmeter"], 2),
        (["postman", "sql", "testrail"], ["javascript", "jmeter", "selenium"], 2),
        (["javascript", "cypress", "jest"], ["playwright", "postman", "allure"], 1),
    ],
    "devops": [
        (
            ["docker", "kubernetes", "terraform"],
            ["helm", "prometheus", "grafana", "gitlab_ci", "aws", "ansible", "linux"],
            3,
        ),
        (
            ["linux", "bash", "ansible"],
            ["docker", "nginx", "gitlab_ci", "prometheus", "grafana"],
            2,
        ),
        (
            ["docker", "gitlab_ci", "linux"],
            ["kubernetes", "helm", "github_actions", "prometheus", "terraform", "bash"],
            2,
        ),
        (
            ["kubernetes", "helm", "prometheus"],
            ["grafana", "terraform", "go", "aws", "github_actions"],
            2,
        ),
    ],
}
STACK_SIZE = {"intern": (3, 4), "junior": (4, 5), "middle": (5, 7), "senior": (6, 8)}
SPEC_SALARY_K = {
    "backend": 1.0,
    "frontend": 0.95,
    "mobile": 1.0,
    "data_ml": 1.05,
    "qa": 0.85,
    "devops": 1.05,
}
CITY_WEIGHTS = [30, 15, 8, 7, 8, 6, 4, 5, 6, 3]
WORK_FORMAT_CHOICES: list[tuple[list[str], int]] = [
    (["remote"], 4),
    (["hybrid", "remote"], 5),
    (["hybrid", "office"], 2),
    (["office"], 1),
    (["hybrid"], 2),
    (["hybrid", "office", "remote"], 3),
]
ABOUT_EXTRA = {
    "backend": [
        "Пишу серверную часть: API, работа с базами, очереди. Люблю понятный код и тесты.",
        "Проектирую API и схемы данных, оптимизирую медленные запросы, настраиваю фоновые задачи.",
        "Интересны нагруженные сервисы: кэширование, очереди, наблюдаемость.",
    ],
    "frontend": [
        "Делаю интерфейсы, которые удобно использовать. Слежу за производительностью.",
        "Собираю сложные формы, таблицы и дашборды, пишу компонентные тесты.",
        "Люблю аккуратный UI и доступность: клавиатура, контраст, скринридеры.",
    ],
    "mobile": [
        "Разрабатываю мобильные приложения от прототипа до публикации в сторах.",
        "Делаю нативные экраны, офлайн-режим и push-уведомления, слежу за размером сборки.",
        "Интересна производительность на слабых устройствах и стабильность релизов.",
    ],
    "data_ml": [
        "Работаю с данными: от SQL-выгрузок до обучения и вывода моделей в прод.",
        "Строю модели прогноза и классификации, считаю метрики и объясняю результат бизнесу.",
        "Готовлю данные и признаки, ставлю эксперименты, довожу модели до сервиса.",
    ],
    "qa": [
        "Тестирую веб и API, пишу автотесты, выстраиваю процессы качества.",
        "Составляю тест-планы и чек-листы, автоматизирую регресс, разбираю логи.",
        "Ищу ошибки на стыке сервисов: API, очереди, интеграции.",
    ],
    "devops": [
        "Настраиваю CI/CD, контейнеры и мониторинг, чтобы релизы были скучными.",
        "Описываю инфраструктуру кодом, поднимаю кластеры и слежу за их стоимостью.",
        "Отвечаю за наблюдаемость: метрики, логи, алерты по делу.",
    ],
}
ABOUT_GRADE = {
    "intern": "Учусь на старших курсах, ищу первую стажировку.",
    "junior": "Есть первый коммерческий опыт, хочу расти в сильной команде.",
    "middle": "Самостоятельно веду задачи от постановки до продакшена.",
    "senior": "Отвечаю за архитектуру, ревьюю код и помогаю расти коллегам.",
}
ROLE_POOL = {
    "intern": ["Разработчик"],
    "junior": ["Разработчик", "Ревьюер кода"],
    "middle": ["Разработчик", "Ревьюер кода", "Ментор"],
    "senior": ["Тимлид", "Архитектор", "Ментор", "Ревьюер кода"],
}
# Ожидаемое число достижений ФСП по грейду — для выбора участника реестра
FSP_COUNT_BY_GRADE = {"intern": 1, "junior": 2, "middle": 3, "senior": 5}
FSP_DISCIPLINE_FOR_SPEC = {
    "backend": {"product", "algorithmic", "cybersecurity"},
    "frontend": {"product", "algorithmic"},
    "mobile": {"product", "uas"},
    "data_ml": {"product", "algorithmic", "robotics"},
    "qa": {"product", "cybersecurity"},
    "devops": {"cybersecurity", "product", "uas"},
}


def unique_pseudonym(candidate_id: int, taken: set[str]) -> str:
    """Псевдоним из pseudonym(), а при совпадении (всего 4 hex-знака) — с солью."""
    value, salt = pseudonym(candidate_id), 0
    while value in taken:
        salt += 1
        digest = hashlib.sha1(f"fsp-talent-candidate-{candidate_id}-{salt}".encode()).hexdigest()
        value = f"Кандидат #{digest[:4].upper()}"
    taken.add(value)
    return value


def extra_stack(r: random.Random, spec: str, grade: str) -> list[str]:
    templates = STACK_TEMPLATES[spec]
    core, optional, _ = r.choices(templates, weights=[t[2] for t in templates])[0]
    lo, hi = STACK_SIZE[grade]
    size = r.randint(lo, hi)
    extra = r.sample(optional, k=max(0, min(len(optional), size - len(core))))
    return core + extra


def extra_roles(r: random.Random, spec: str, grade: str) -> list[str]:
    pool = ROLE_POOL[grade][:]
    if spec == "qa":
        pool = ["Тестировщик" if x == "Разработчик" else x for x in pool]
    if spec == "data_ml" and r.random() < 0.5:
        pool = ["Аналитик" if x == "Разработчик" else x for x in pool]
    k = 1 if grade == "intern" else r.randint(1, 2)
    return r.sample(pool, k=min(k, len(pool)))


def registry_primary(fsp: str) -> str:
    """Основная дисциплина участника реестра (в кодах платформы)."""
    codes = [
        DISCIPLINE_FROM_REGISTRY[a["discipline"]["code"]] for a in FSP_REGISTRY[fsp]["achievements"]
    ]
    return max(sorted(set(codes)), key=codes.count)


def build_extra_candidates() -> None:
    """Банк кандидатов: дополнить каждую категорию до CATEGORY_TARGET."""
    r = xrng
    known = {k["id"] for k in SKILLS}
    for templates in STACK_TEMPLATES.values():
        for core, optional, _ in templates:
            assert set(core + optional) <= known, set(core + optional) - known
    blocked = {u["id"] for u in USERS if u["blocked"]}
    have: dict[str, int] = {}
    for c in CANDIDATES:
        if eligible(c) and c["user_id"] not in blocked:
            have[c["category"]] = have.get(c["category"], 0) + 1
    slots = [
        (spec, grade)
        for spec, grades in CATEGORY_TARGET.items()
        for grade, target in grades.items()
        for _ in range(target - have.get(cat_id(spec, grade), 0))
    ]
    r.shuffle(slots)
    # ~40 % банка вместе с кандидатами 1–20 — с историей ФСП: участники FSP-000101…180
    with_fsp = set(r.sample(range(len(slots)), k=len(EXTRA_FSP_IDS)))
    free_fsp = EXTRA_FSP_IDS[:]
    used_names = {u["full_name"] for u in USERS}
    used_names |= {f"{p['first_name']} {p['last_name']}" for p in FSP_REGISTRY.values()}
    taken_pseudonyms = {c["pseudonym"] for c in CANDIDATES}

    for k, (spec, grade) in enumerate(slots):
        i = EXTRA_FIRST_ID + k
        fsp = None
        if k in with_fsp:
            allowed = FSP_DISCIPLINE_FOR_SPEC[spec]
            want = FSP_COUNT_BY_GRADE[grade]
            fsp = min(
                free_fsp,
                key=lambda f: (
                    registry_primary(f) not in allowed,
                    abs(len(FSP_REGISTRY[f]["achievements"]) - want),
                    f,
                ),
            )
            free_fsp.remove(fsp)
            first, surname = FSP_REGISTRY[fsp]["first_name"], FSP_REGISTRY[fsp]["last_name"]
            full = f"{first} {surname}"
        else:
            while True:
                if r.random() < 0.35:
                    first, surname = r.choice(FEMALE_FIRST), female_surname(r.choice(SURNAMES))
                else:
                    first, surname = r.choice(MALE_FIRST), r.choice(SURNAMES)
                full = f"{first} {surname}"
                if full not in used_names:
                    break
        used_names.add(full)
        email = f"{translit(first)[0]}.{translit(surname)}.{i}@example.com"
        last_test = days_ago(r.randint(4, 60), hour=r.randint(10, 21))
        created = last_test - timedelta(days=r.randint(1, 40), hours=r.randint(1, 6))
        USERS.append(
            {
                "id": i,
                "email": email,
                "role": "candidate",
                "full_name": full,
                "email_verified": True,
                "blocked": False,
                "created_at": iso(created),
                "last_login_at": iso(days_ago(r.uniform(0, 12), hour=r.randint(8, 22))),
            }
        )
        theta = round(THETA_CENTER[grade] + r.uniform(-0.35, 0.35), 2)
        stack = extra_stack(r, spec, grade)
        lo, hi = SALARY_RANGE[grade]
        exp_lo, exp_hi = EXPERIENCE[grade]
        achs = registry_achievements(fsp) if fsp else []
        links = []
        if r.random() < 0.6:
            links.append(
                {"type": "github", "url": f"https://github.com/example-{translit(first)}{i}"}
            )
        if r.random() < 0.2:
            links.append({"type": "portfolio", "url": f"https://portfolio.example.com/{i}"})
        privacy = {
            "show_city": r.random() < 0.85,
            "show_experience": r.random() < 0.9,
            "show_links": r.random() < 0.4,
            "show_fsp_achievements": r.random() < 0.9,
        }
        formats = r.choices(
            [f for f, _ in WORK_FORMAT_CHOICES], weights=[w for _, w in WORK_FORMAT_CHOICES]
        )[0]
        candidate = {
            "id": i,
            "user_id": i,
            "pseudonym": unique_pseudonym(i, taken_pseudonyms),
            "full_name": full,
            "email": email,
            "phone": f"+7 901 {i:03d}-{r.randint(10, 99)}-{r.randint(10, 99)}",
            "telegram": f"@example_{translit(first)}{i}" if r.random() < 0.8 else None,
            "city": r.choices(CITIES, weights=CITY_WEIGHTS)[0],
            "work_formats": sorted(formats),
            "specialization": spec,
            "grade": grade,
            "category": cat_id(spec, grade),
            "category_label": cat_label(spec, grade),
            "theta": theta,
            "theta_se": round(r.uniform(0.25, 0.34), 2),
            "topic_scores": topic_scores(spec, theta, r),
            "stack": stack,
            "roles_in_team": extra_roles(r, spec, grade),
            "experience_years": round(r.uniform(exp_lo, exp_hi) * 2) / 2,
            "soft_skills": r.sample(SOFT_SKILLS, k=r.randint(2, 4)),
            "about": f"{r.choice(ABOUT_EXTRA[spec])} {ABOUT_GRADE[grade]}",
            "links": links,
            "min_salary": round_to(r.uniform(lo, hi) * SPEC_SALARY_K[spec]),
            "fsp_id": fsp,
            "fsp_score": fsp_score(achs),
            "fsp_badges": badges_for(achs),
            "privacy": privacy,
            "job_search_paused": False,
            "publication_consent": True,
            "freshness": round(r.uniform(0.15, 0.9), 2),
            "profile_completeness": 0,
            "last_test_at": iso(last_test),
            "grade_changed_at": iso(last_test),
            "created_at": iso(created),
        }
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
        add_tests(candidate, r)


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
    (
        1,
        1,
        "Frontend-разработчик в личный кабинет банка",
        "Ищем мидла на React и TypeScript в личный кабинет мобильного банка, удалёнка, 180–250к",
        "frontend",
        "middle",
        ["react", "typescript"],
        ["redux", "jest"],
        "Личный кабинет и платежи физлиц, команда 5 человек",
        "remote",
        None,
        180_000,
        250_000,
        "active",
        2,
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
    # candidate@ принял приглашение «Вектора», а не «Северного кода» (компании recruiter@):
    # в подборке recruiter@ кандидат обезличен, и его можно пригласить на показе
    (1, 5, "accepted", None, 9),
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
        if status in ("sent", "viewed"):
            # активные приглашения демо не должны истекать до конца проверки
            expires = created.replace(month=12, day=30)
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
        (1, 4, "invited"),  # candidate@: «Вектор» пригласил по отклику, контакты открыты
        (92, 1, "viewed"),  # не candidate@: отклик открыл бы его контакты «Северному коду»
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
        if status == "invited":  # приглашая, рекрутер оставляет способ связи и пару слов
            rec = next(r for r in RECRUITERS if r["company_id"] == vac["company_id"])
            APPLICATIONS[-1]["contact_method"] = {"type": "telegram", "value": rec["telegram"]}
            APPLICATIONS[-1]["invite_message"] = (
                "Добрый день! Давайте созвонимся на 30 минут — напишите в Telegram, когда удобно."
            )
        vac["applications_count"] += 1


# Демо-учётки: жюри смотрит стенд после сдачи, поэтому у candidate@ и candidate.nofsp@
# по два приглашения «отправлено» со сроком до 20.11.2026 (обычный срок — 7 дней).
DEMO_INVITE_EXPIRES = datetime(2026, 11, 20, 18, 0, tzinfo=MSK)


def add_invitation(
    cid: int,
    rid: int,
    status: str,
    created: datetime,
    salary: tuple[int, int],
    contact_type: str,
    description: str,
    *,
    task_text: str | None = None,
    viewed: datetime | None = None,
    responded: datetime | None = None,
    reason: str | None = None,
    comment: str | None = None,
    expires: datetime | None = None,
) -> J:
    """Приглашение без случайных чисел (для демо-учёток) + события и запись журнала."""
    rec = next(r for r in RECRUITERS if r["id"] == rid)
    cand = next(c for c in CANDIDATES if c["id"] == cid)
    company = rec["company_id"]
    inv_id = len(INVITATIONS) + 1
    expires = expires or created + timedelta(days=7)
    inv = {
        "id": inv_id,
        "candidate_id": cid,
        "recruiter_id": rid,
        "company_id": company,
        "company_name": COMPANY_NAME[company],
        "recruiter_name": rec["full_name"],
        "need_id": next(
            (
                n["id"]
                for n in NEEDS
                if n["company_id"] == company and n["category"] == cand["category"]
            ),
            None,
        ),
        "vacancy_id": next(
            (
                v["id"]
                for v in VACANCIES
                if v["company_id"] == company
                and v["category"] == cand["category"]
                and v["status"] == "published"
            ),
            None,
        ),
        "category": cand["category"],
        "category_label": cand["category_label"],
        "description": description,
        "salary_from": salary[0],
        "salary_to": salary[1],
        "contact_method": {"type": contact_type, "value": rec[contact_type]},
        "task_text": task_text,
        "status": status,
        "decline_reason": reason,
        "decline_comment": comment,
        "created_at": iso(created),
        "viewed_at": iso(viewed) if viewed else None,
        "responded_at": iso(responded) if responded else None,
        "expires_at": iso(expires),
        "withdrawn_at": None,
    }
    INVITATIONS.append(inv)
    event(inv_id, "created", created, "recruiter")
    if viewed:
        event(inv_id, "viewed", viewed, "candidate")
    if status == "accepted" and responded:
        event(inv_id, "accepted", responded, "candidate")
        event(inv_id, "contacts_revealed", responded, None)
        audit(
            responded,
            rec["user_id"],
            "recruiter",
            "contacts_revealed",
            "invitation",
            inv_id,
            f"Раскрыты контакты: {cand['pseudonym']} ↔ {COMPANY_NAME[company]}",
            {"candidate_id": cid, "company_id": company},
        )
    if status == "declined" and responded:
        event(inv_id, "declined", responded, "candidate")
    return inv


def msk(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=MSK)


def build_demo_invitations() -> None:
    """У demo-соискателей — по два приглашения «ждёт ответа» от разных компаний и история."""
    # candidate@ (Backend · Middle): приглашение №2 от «Вектора» — ждёт ответа до 20.11
    inv = next(i for i in INVITATIONS if i["id"] == 2)
    assert inv["candidate_id"] == 1 and inv["status"] == "sent" and inv["company_id"] == 2
    inv["expires_at"] = iso(DEMO_INVITE_EXPIRES)
    inv["description"] = (
        "Ищем backend-разработчика в команду прогноза спроса: сервисы на Python и FastAPI, "
        "выгрузки из ClickHouse, API для витрин данных магазинов. Команда 5 человек, "
        "гибрид в Санкт-Петербурге или удалённо."
    )
    add_invitation(
        1,
        7,
        "sent",
        msk(10, 6, 9, 40),
        (200_000, 250_000),
        "telegram",
        "B2B-платформа учёта для логистики: нужен backend-разработчик на Python в команду "
        "интеграций с перевозчиками — приём статусов доставки, очереди, PostgreSQL. "
        "Удалённо, гибкий график.",
        task_text="Опишите, как бы вы принимали статусы доставки от 20 перевозчиков "
        "с разными API (до 10 предложений).",
        expires=DEMO_INVITE_EXPIRES,
    )
    # candidate.nofsp@ (Frontend · Junior): история + два ожидающих ответа
    cand = next(c for c in CANDIDATES if c["id"] == 26)
    base = cand["min_salary"] or 100_000

    def pay(lo: float, hi: float) -> tuple[int, int]:
        return round_to(base * lo), round_to(base * hi)

    add_invitation(
        26,
        6,
        "accepted",
        msk(9, 22, 11),
        pay(1.0, 1.25),
        "email",
        "Облачные системы «Тайга» приглашают на позицию Frontend · Junior: экраны учёта "
        "грузов на React. Расскажем о задачах на созвоне.",
        viewed=msk(9, 22, 15, 10),
        responded=msk(9, 23, 10, 5),
    )
    add_invitation(
        26,
        4,
        "declined",
        msk(9, 29, 14),
        pay(1.0, 1.2),
        "phone",
        "Лаборатория данных «Вектор»: внутренний портал аналитиков на Angular.",
        viewed=msk(9, 29, 20, 30),
        responded=msk(9, 30, 9, 15),
        reason="wrong_stack",
        comment="Ищу позицию на React, а здесь Angular",
    )
    add_invitation(
        26,
        3,
        "sent",
        msk(10, 5, 15, 20),
        pay(1.05, 1.4),
        "email",
        "Северный код: интерфейсы мобильного банка на React и TypeScript — формы платежей, "
        "история операций. Наставник на первые три месяца, гибрид в Москве или удалённо.",
        expires=DEMO_INVITE_EXPIRES,
    )
    add_invitation(
        26,
        5,
        "sent",
        msk(10, 6, 10, 15),
        pay(1.0, 1.3),
        "telegram",
        "Лаборатория данных «Вектор»: дашборды для сетей магазинов на React — графики, "
        "фильтры, выгрузки. Удалённо, команда из 4 фронтендеров.",
        task_text="Как бы вы показали на графике продажи 300 магазинов за год, чтобы он "
        "не тормозил? (до 10 предложений)",
        expires=DEMO_INVITE_EXPIRES,
    )


COVER_LETTERS = [
    "Здравствуйте! Интересна вакансия, готов обсудить детали.",
    "Добрый день! Стек совпадает с моим опытом, буду рад созвониться.",
    "Здравствуйте! Давно слежу за продуктом, хочу в команду. Удобно созвониться в будни после 17:00.",
    "Добрый день! Подхожу по грейду и стеку, тест на платформе пройден. Готов к тестовому заданию.",
]


def build_extra_applications() -> None:
    """Отклики кандидатов банка на опубликованные вакансии — в разных статусах."""
    plan = [
        # (вакансия, статусы откликов по порядку кандидатов категории)
        (1, ["viewed", "new", "viewed"]),
        (2, ["viewed", "rejected"]),
        (3, ["viewed", "invited"]),
        (4, ["new", "viewed"]),
        (7, ["new"]),
    ]
    k = 0
    for vid, statuses in plan:
        vac = next(v for v in VACANCIES if v["id"] == vid)
        pool = [
            c for c in CANDIDATES if c["id"] >= EXTRA_FIRST_ID and c["category"] == vac["category"]
        ]
        for cand, status in zip(pool, statuses, strict=False):
            k += 1
            created = days_ago(1 + k % 6, hour=9 + k % 9)
            app = {
                "id": len(APPLICATIONS) + 1,
                "vacancy_id": vid,
                "candidate_id": cand["id"],
                "vacancy_title": vac["title"],
                "company_id": vac["company_id"],
                "company_name": vac["company_name"],
                "cover_letter": COVER_LETTERS[k % len(COVER_LETTERS)],
                "status": status,
                "created_at": iso(created),
                "updated_at": iso(created + timedelta(hours=3) if status != "new" else created),
            }
            if status == "invited":
                rec = next(r for r in RECRUITERS if r["company_id"] == vac["company_id"])
                app["contact_method"] = {"type": "email", "value": rec["email"]}
                app["invite_message"] = (
                    "Здравствуйте! Понравился ваш профиль — давайте созвонимся на 30 минут, "
                    "напишите на почту удобное время."
                )
            APPLICATIONS.append(app)
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
        if not cand["category"] or cand["id"] > N_CANDIDATES:
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
                min(assigned + timedelta(days=rng.randint(1, 4)), NOW - timedelta(hours=2))
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
                    "graded_at": iso(min(submitted + timedelta(days=1), NOW - timedelta(hours=1)))
                    if score is not None and submitted
                    else None,
                }
            )
            task["submissions_count"] += 1


# Задачи недели на выбор: у каждой категории — по задаче от каждой компании, чтобы кандидат
# видел три задачи от разных работодателей. Тексты — по профилю компании, грейд-нейтральные.
# Без rng: добавление не сдвигает остальные фикстуры.
TASK_TEMPLATES: dict[tuple[str, int], tuple[str, str]] = {
    ("backend", 1): (
        "Очередь платежей без потерь",
        "Платёж пришёл в очередь, обработчик упал посередине. Как не потерять платёж "
        "и не провести его дважды?",
    ),
    ("backend", 2): (
        "Выгрузка большого отчёта",
        "Пользователь просит отчёт на 5 млн строк, запрос держит соединение минуту. "
        "Как отдать отчёт, не роняя API?",
    ),
    ("backend", 3): (
        "Ограничение частоты запросов",
        "Один клиент шлёт 1000 запросов в секунду и мешает остальным. Как ограничить его, "
        "не задев других?",
    ),
    ("frontend", 1): (
        "Двойная отправка оплаты",
        "Пользователь дважды нажимает «Оплатить». Как не отправить запрос дважды и показать "
        "понятный статус?",
    ),
    ("frontend", 2): (
        "Таблица на 10 000 строк",
        "Таблица с отчётом из 10 000 строк тормозит при прокрутке. Как сделать её плавной?",
    ),
    ("frontend", 3): (
        "Белый экран после выкладки",
        "После новой версии у части пользователей белый экран: старая вкладка грузит "
        "удалённые файлы. Как это предотвратить?",
    ),
    ("mobile", 1): (
        "Оплата без сети",
        "Пользователь нажал «Оплатить» в метро, и связь пропала. Что показать и как "
        "не потерять платёж?",
    ),
    ("mobile", 2): (
        "Тяжёлая лента в приложении",
        "Лента из 500 карточек с картинками дёргается при прокрутке. Что проверить "
        "и как ускорить?",
    ),
    ("mobile", 3): (
        "Рост падений после релиза",
        "После релиза падений приложения стало вдвое больше. Как быстро найти причину "
        "и что сделать до исправления?",
    ),
    ("data_ml", 1): (
        "Антифрод платежей",
        "Мошеннических платежей 0,1 %. Как обучить модель и чем мерить качество, если "
        "«всегда честный» уже даёт точность 99,9 %?",
    ),
    ("data_ml", 2): (
        "Модель стареет",
        "Качество прогноза падает каждый месяц. Как заметить это вовремя и что делать?",
    ),
    ("data_ml", 3): (
        "Прогноз нагрузки на кластер",
        "Нужно заранее знать, когда кластеру не хватит ресурсов. Какие данные и какую модель "
        "возьмёте?",
    ),
    ("qa", 1): (
        "Тест-план формы оплаты",
        "Что проверите в форме оплаты картой? Назовите главные сценарии и крайние случаи.",
    ),
    ("qa", 2): (
        "Проверка отчёта с цифрами",
        "Отчёт считает выручку по регионам. Как убедиться, что цифры верные, не пересчитывая "
        "всё вручную?",
    ),
    ("qa", 3): (
        "Внешний API тормозит",
        "Сервис зависит от внешнего API. Как проверить поведение, когда API отвечает медленно "
        "или с ошибкой?",
    ),
    ("devops", 1): (
        "Выкладка без простоя",
        "Сервис оплаты нельзя останавливать даже на минуту. Как выкатывать новую версию?",
    ),
    ("devops", 2): (
        "Кончается место под базу",
        "База растёт на 5 % в неделю, места осталось на месяц. Ваш план?",
    ),
    ("devops", 3): (
        "Ночные тревоги",
        "Ночью приходит 50 одинаковых тревог про один сбой. Как настроить мониторинг, "
        "чтобы будили по делу?",
    ),
}


def build_week_tasks() -> None:
    """Добрать задачи до «по одной от каждой компании» в каждой категории."""
    have = {(t["company_id"], t["category"]) for t in REGULAR_TASKS}
    recruiter_of = {c: min(r["id"] for r in RECRUITERS if r["company_id"] == c) for c in COMPANY_NAME}
    next_id = max(t["id"] for t in REGULAR_TASKS) + 1
    for cat in CATEGORIES:
        spec, grade = cat["specialization"], cat["grade"]
        for company in sorted(COMPANY_NAME):
            if (company, cat["id"]) in have:
                continue
            title, statement = TASK_TEMPLATES[(spec, company)]
            REGULAR_TASKS.append(
                {
                    "id": next_id,
                    "company_id": company,
                    "company_name": COMPANY_NAME[company],
                    "recruiter_id": recruiter_of[company],
                    "title": title,
                    "statement": statement,
                    "category": cat["id"],
                    "category_label": cat_label(spec, grade),
                    "deadline_days": 7,
                    "status": "active",
                    "submissions_count": 0,
                    "created_at": iso(days_ago(2 + next_id % 12)),
                }
            )
            next_id += 1


def build_company_tasks() -> None:
    """Ещё по задаче от «Северного кода» в категориях демо-соискателей: их прошлые задачи
    этой компании уже решены, а решённые повторно не предлагаются."""
    next_id = max(t["id"] for t in REGULAR_TASKS) + 1
    for spec, grade in (("backend", "middle"), ("frontend", "junior")):
        title, statement = TASK_TEMPLATES[(spec, 1)]
        REGULAR_TASKS.append(
            {
                "id": next_id,
                "company_id": 1,
                "company_name": COMPANY_NAME[1],
                "recruiter_id": 1,
                "title": title,
                "statement": statement,
                "category": cat_id(spec, grade),
                "category_label": cat_label(spec, grade),
                "deadline_days": 7,
                "status": "active",
                "submissions_count": 0,
                "created_at": iso(days_ago(8)),
            }
        )
        next_id += 1


# Задачи недели демо-соискателей: раздача понедельника 05.10, срок до 23.11.2026 —
# жюри смотрит стенд после сдачи (до 20.11), задачи не должны протухнуть раньше
# (обычный срок ответа — 7 дней).
DEMO_WEEK_START = datetime(2026, 10, 5, 3, 30, tzinfo=MSK)
DEMO_TASK_DUE = datetime(2026, 11, 23, 3, 0, tzinfo=MSK)


def submission(
    task: J,
    cand_id: int,
    status: str,
    assigned: datetime,
    due: datetime,
    *,
    kind: str | None = None,
    answer: str | None = None,
    submitted: datetime | None = None,
    score: int | None = None,
    comment: str | None = None,
    graded: datetime | None = None,
) -> J:
    sub = {
        "id": len(SUBMISSIONS) + 1,
        "task_id": task["id"],
        "candidate_id": cand_id,
        "task_title": task["title"],
        "statement": task["statement"],
        "company_name": task["company_name"],
        "status": status,
        "assigned_at": iso(assigned),
        "due_at": iso(due),
        "answer_kind": kind,
        "answer_text": answer,
        "submitted_at": iso(submitted) if submitted else None,
        "score": score,
        "grader_comment": comment,
        "graded_at": iso(graded) if graded else None,
    }
    SUBMISSIONS.append(sub)
    if status != "skipped":
        task["submissions_count"] += 1
    return sub


def week_task(company: int, category: str, title: str | None = None) -> J:
    return next(
        t
        for t in REGULAR_TASKS
        if t["company_id"] == company
        and t["category"] == category
        and (title is None or t["title"] == title)
    )


def retarget(sub: J, task: J) -> None:
    old = next(t for t in REGULAR_TASKS if t["id"] == sub["task_id"])
    old["submissions_count"] -= 1
    task["submissions_count"] += 1
    sub.update(
        task_id=task["id"],
        task_title=task["title"],
        statement=task["statement"],
        company_name=task["company_name"],
    )


def build_demo_tasks() -> None:
    """По три задачи недели на выбор (от трёх компаний) у обоих демо-соискателей."""
    week = timedelta(days=7) - timedelta(minutes=30)
    prev_week = DEMO_WEEK_START - timedelta(days=7)
    # candidate@: две оценённые задачи в истории, прошлонедельное предложение истекло
    subs = [s for s in SUBMISSIONS if s["candidate_id"] == 1]
    assert [s["status"] for s in subs] == ["graded", "graded", "assigned"], subs
    expired = subs[2]
    retarget(expired, week_task(3, "backend:middle"))
    expired.update(status="expired", assigned_at=iso(prev_week), due_at=iso(prev_week + week))
    for company, title in ((1, "Очередь платежей без потерь"), (2, None), (3, None)):
        submission(
            week_task(company, "backend:middle", title),
            1,
            "assigned",
            DEMO_WEEK_START,
            DEMO_TASK_DUE,
        )
    # candidate.nofsp@: ответ прошлой недели оценён, на этой неделе — три задачи на выбор
    subs = [s for s in SUBMISSIONS if s["candidate_id"] == 26]
    assert [s["status"] for s in subs] == ["submitted"], subs
    subs[0].update(
        status="graded",
        assigned_at=iso(prev_week),
        due_at=iso(prev_week + week),
        answer_kind="text",
        answer_text="Сначала посмотрю в React DevTools Profiler, что перерисовывается при вводе. "
        "Состояние каждого поля опущу в само поле или перейду на неуправляемые поля "
        "(react-hook-form), тяжёлые вычисления — в useMemo, валидацию — по blur.",
        submitted_at=iso(msk(10, 1, 19, 20)),
        score=2,
        grader_comment="Хороший разбор",
        graded_at=iso(msk(10, 2, 11, 0)),
    )
    for company, title in ((1, "Двойная отправка оплаты"), (2, None), (3, None)):
        submission(
            week_task(company, "frontend:junior", title),
            26,
            "assigned",
            DEMO_WEEK_START,
            DEMO_TASK_DUE,
        )


EXTRA_ANSWERS = {
    "text": "Сначала замерил бы, где теряется время, и только потом менял решение. "
    "Предложил бы два варианта и сравнил их по рискам.",
    "code": "def handle(event):\n    if seen(event.id):\n        return\n    process(event)\n"
    "    mark_seen(event.id)",
    "approach": "Разбил бы задачу на шаги: воспроизвести, найти узкое место, исправить, "
    "добавить проверку в мониторинг, чтобы не повторилось.",
}


def build_extra_submissions() -> None:
    """История задач недели у кандидатов банка: ответы прошлых недель (без активных)."""
    r = random.Random(SEED + 600)
    week = timedelta(days=7) - timedelta(minutes=30)
    for cand in CANDIDATES:
        if cand["id"] < EXTRA_FIRST_ID:
            continue
        tasks = sorted(
            (t for t in REGULAR_TASKS if t["category"] == cand["category"]), key=lambda t: t["id"]
        )
        n = r.choice([0, 0, 1, 1, 2])
        for k in range(n):
            task = tasks[(cand["id"] + k) % len(tasks)]
            assigned = DEMO_WEEK_START - timedelta(days=7 * (k + 1))
            status = r.choice(["graded", "graded", "submitted", "expired"])
            if status == "expired":
                submission(task, cand["id"], status, assigned, assigned + week)
                continue
            submitted = assigned + timedelta(days=r.randint(0, 5), hours=r.randint(6, 18))
            kind = r.choice(["text", "code", "approach"])
            score = r.randint(1, 3) if status == "graded" else None
            submission(
                task,
                cand["id"],
                status,
                assigned,
                assigned + week,
                kind=kind,
                answer=EXTRA_ANSWERS[kind],
                submitted=submitted,
                score=score,
                comment={
                    1: "Направление верное, мало деталей",
                    2: "Хороший разбор",
                    3: "Отлично, с учётом крайних случаев",
                }.get(score or 0),
                graded=min(submitted + timedelta(days=1), NOW - timedelta(hours=1))
                if score
                else None,
            )


# Ответы демо-соискателей на задачи недели — по теме задачи (раньше на любую задачу
# приходил один и тот же ответ про кэш или идемпотентность). Ключ — название задачи,
# дальше по виду ответа: text / code / approach. Без rng: остальные фикстуры не сдвигаются.
TASK_ANSWERS: dict[str, dict[str, str]] = {
    "Кэш для медленного API": {
        "text": "Сначала замерю, где теряются 2 секунды. Справочники меняются редко — положу их "
        "в Redis с TTL 5 минут и сброшу кэш по событию изменения справочника.",
        "code": '@cached(ttl=300, key=lambda code: f"dict:{code}")\n'
        "async def get_dictionary(code: str) -> Dictionary:\n"
        "    return await upstream.fetch(code)",
        "approach": "Кэш перед сервисом (Redis, TTL + сброс по событию), прогрев популярных "
        "справочников, при недоступности источника — отдать последнюю версию из кэша.",
    },
    "Идемпотентность платежей": {
        "text": "Клиент передаёт ключ идемпотентности. Сервер сохраняет результат по ключу "
        "в одной транзакции со списанием и на повтор отдаёт его, не списывая снова.",
        "code": "INSERT INTO payments (idempotency_key, amount) VALUES (:key, :amount)\n"
        "ON CONFLICT (idempotency_key) DO NOTHING\nRETURNING id;",
        "approach": "Ключ идемпотентности в заголовке, уникальный индекс в БД, повтор "
        "возвращает сохранённый результат.",
    },
    "Состояние формы в React": {
        "text": "Посмотрю в React DevTools Profiler, что перерисовывается при вводе: скорее "
        "всего вся форма из-за общего состояния. Опущу состояние в поля.",
        "code": "const { register, handleSubmit } = useForm<FormValues>({ mode: 'onBlur' })\n"
        "<input {...register('email')} />",
        "approach": "Профилирую ввод, перевожу поля на неуправляемые (react-hook-form), "
        "тяжёлые вычисления — в useMemo, валидацию — по blur.",
    },
    "Утечка в признаках": {
        "text": "Проверю признаки, которые известны только после даты прогноза (продажи "
        "за ту же неделю, итоговые статусы), и что валидация идёт по времени, а не случайно.",
        "code": "cv = TimeSeriesSplit(n_splits=5)\nleaks = [c for c in X if X[c].corr(y) > 0.95]",
        "approach": "Валидация по времени, разбор важности признаков, удаление признаков "
        "«из будущего», сравнение качества до и после.",
    },
    "Флаки-тесты": {
        "text": "Соберу статистику падений по тестам, перезапущу подозрительные в цикле "
        "и посмотрю на ожидания по времени, общие данные и порядок запуска.",
        "code": "pytest tests/ -p no:randomly --count=50 -x -k checkout",
        "approach": "Статистика падений, изоляция данных между тестами, явные ожидания "
        "вместо sleep, карантин флаки-тестов с задачей на исправление.",
    },
    "Откат релиза в Kubernetes": {
        "text": "Сразу откачу деплоймент на прошлую ревизию, проверю метрики 5xx, "
        "а причину буду искать уже на стенде по логам нового образа.",
        "code": "kubectl rollout undo deployment/payments -n prod\n"
        "kubectl rollout status deployment/payments -n prod",
        "approach": "rollout undo на прошлую ревизию, проверка readiness и метрик, "
        "затем разбор причины и canary-выкатка исправления.",
    },
    "Очередь платежей без потерь": {
        "text": "Подтверждаю сообщение в очереди только после записи результата. Повтор "
        "безопасен: обработчик проверяет id платежа и не проводит его второй раз.",
        "code": "def handle(msg):\n    if processed(msg.payment_id):\n        return msg.ack()\n"
        "    with db.transaction():\n        apply(msg)\n        mark_processed(msg.payment_id)\n"
        "    msg.ack()",
        "approach": "Подтверждение после обработки, идемпотентный обработчик по id платежа, "
        "очередь недоставленных сообщений и тревога на её рост.",
    },
    "Выгрузка большого отчёта": {
        "text": "Сделаю отчёт асинхронным: запрос ставит задачу, фоновый воркер пишет файл "
        "в хранилище, пользователь получает ссылку, когда файл готов.",
        "code": '@router.post("/reports")\nasync def create_report(req: ReportRequest):\n'
        "    job = await queue.enqueue(build_report, req)\n"
        '    return {"job_id": job.id, "status": "queued"}',
        "approach": "Фоновая задача, выгрузка курсором порциями, файл в S3 и ссылка "
        "со сроком жизни, статус задачи по id.",
    },
    "Ограничение частоты запросов": {
        "text": "Поставлю лимит на клиента по токен-бакету в Redis: лишние запросы получают "
        "429 с Retry-After, остальные клиенты не страдают.",
        "code": 'allowed = redis.eval(TOKEN_BUCKET_LUA, 1, f"rl:{client_id}", rate, burst, now)\n'
        'if not allowed:\n    raise HTTPException(429, headers={"Retry-After": "1"})',
        "approach": "Token bucket на клиента в Redis, 429 с Retry-After, отдельные лимиты "
        "для тяжёлых ручек, мониторинг отказов.",
    },
    "Двойная отправка оплаты": {
        "text": "Блокирую кнопку на время запроса и показываю статус «Оплата обрабатывается». "
        "В запрос передаю ключ идемпотентности, чтобы повтор не списал деньги.",
        "code": "const pay = useMutation({ mutationFn: () => api.pay(order.id, idempotencyKey) })\n"
        "<Button disabled={pay.isPending} onClick={() => pay.mutate()}>Оплатить</Button>",
        "approach": "Блокировка кнопки, ключ идемпотентности на заказ, понятные статусы "
        "«обрабатывается / оплачено / ошибка» и повтор только по кнопке.",
    },
    "Таблица на 10 000 строк": {
        "text": "Включу виртуализацию: в DOM только видимые строки. Строки мемоизирую, "
        "сортировку и фильтр считаю один раз, а не при каждом рендере.",
        "code": "const rows = useVirtualizer({ count: data.length, estimateSize: () => 36,\n"
        "  getScrollElement: () => ref.current })",
        "approach": "Виртуализация списка, memo для строки, фиксированная высота строк, "
        "тяжёлые вычисления в useMemo, замер в Profiler до и после.",
    },
    "Белый экран после выкладки": {
        "text": "Старые файлы не удаляю сразу: держу прошлую сборку на CDN несколько дней. "
        "Ошибку загрузки чанка ловлю и предлагаю обновить страницу.",
        "code": "window.addEventListener('vite:preloadError', () => {\n"
        "  showToast('Вышла новая версия', { action: () => location.reload() })\n})",
        "approach": "Файлы с хешем в имени и хранение прошлых версий, index.html без кэша, "
        "перехват ошибки загрузки чанка с предложением обновиться.",
    },
    "Оплата без сети": {
        "text": "Покажу «Нет сети, платёж не отправлен» и сохраню заказ локально. Когда сеть "
        "вернётся, отправлю платёж с тем же ключом, чтобы не провести его дважды.",
        "code": "if (!network.isConnected) {\n    pendingPayments.save(order.id, idempotencyKey)\n"
        "    showStatus(PaymentStatus.WaitingForNetwork)\n}",
        "approach": "Честный статус на экране, локальная очередь платежей, повтор при "
        "появлении сети с тем же ключом идемпотентности, проверка статуса на сервере.",
    },
    "Тяжёлая лента в приложении": {
        "text": "Проверю размер картинок и работу в главном потоке. Картинки уменьшу на сервере "
        "под экран, декодирование и загрузку вынесу из главного потока.",
        "code": "LazyColumn {\n    items(feed, key = { it.id }) { card -> FeedCard(card) }\n}",
        "approach": "Профилировщик кадров, картинки нужного размера и кэш, переиспользование "
        "ячеек, стабильные ключи элементов, загрузка порциями.",
    },
    "Рост падений после релиза": {
        "text": "Открою Crashlytics, сравню падения по версии и устройствам, найду самый "
        "частый стек. До исправления выключу новую функцию флагом.",
        "code": 'if (remoteConfig.getBoolean("new_checkout_enabled")) {\n'
        "    showNewCheckout()\n} else {\n    showOldCheckout()\n}",
        "approach": "Разбор падений по версии и стеку, отключение фичи флагом, остановка "
        "поэтапной раскатки, хотфикс и проверка на затронутых устройствах.",
    },
    "Антифрод платежей": {
        "text": "Точность тут бесполезна. Смотрю полноту и точность по мошенническому классу "
        "и PR-AUC, порог выбираю по цене пропуска и ложной блокировки.",
        "code": 'model = LGBMClassifier(class_weight="balanced")\n'
        "print(average_precision_score(y_test, model.predict_proba(X_test)[:, 1]))",
        "approach": "Валидация по времени, веса классов, метрики PR-AUC и полнота при "
        "заданной доле ложных срабатываний, порог — по стоимости ошибок.",
    },
    "Модель стареет": {
        "text": "Настрою мониторинг: дрейф входных признаков (PSI) и качество на свежих "
        "размеченных данных. При падении ниже порога — переобучение на новом окне.",
        "code": "psi = population_stability_index(train[col], last_month[col])\n"
        'if psi > 0.2:\n    alert(f"дрейф признака {col}: PSI={psi:.2f}")',
        "approach": "Мониторинг дрейфа и качества, регулярное переобучение по расписанию "
        "и по тревоге, сравнение новой модели со старой перед заменой.",
    },
    "Прогноз нагрузки на кластер": {
        "text": "Возьму историю загрузки CPU, памяти и диска с недельной сезонностью и "
        "релизами. Начну с простой модели с сезонностью, проверю на отложенных неделях.",
        "code": 'model = Prophet(weekly_seasonality=True)\nmodel.fit(df[["ds", "y"]])\n'
        "forecast = model.predict(model.make_future_dataframe(periods=30))",
        "approach": "Метрики кластера за год, сезонность и события, базовая модель и "
        "градиентный бустинг, тревога, когда прогноз пересекает порог ёмкости.",
    },
    "Тест-план формы оплаты": {
        "text": "Успешная оплата, отказ банка, неверные номер, срок и CVC, 3-D Secure, "
        "двойное нажатие, обрыв сети и возврат со страницы банка.",
        "code": '@pytest.mark.parametrize("card,expected", [\n'
        '    ("4111111111111111", "success"),\n    ("4000000000000002", "declined"),\n])',
        "approach": "Позитивные сценарии, отказы банка, валидация полей, 3-D Secure, "
        "повторное нажатие и сетевые сбои, проверка суммы в чеке.",
    },
    "Проверка отчёта с цифрами": {
        "text": "Сверю итог отчёта с суммой по исходным данным, проверю несколько регионов "
        "вручную и крайние случаи: возвраты, пустой регион, смену часового пояса.",
        "code": "SELECT region, SUM(amount) FROM orders\nWHERE paid_at >= :from AND paid_at < :to\n"
        "GROUP BY region;",
        "approach": "Контрольная сумма против источника, выборочная ручная сверка, крайние "
        "случаи и автотест, который сравнивает отчёт с эталонным набором данных.",
    },
    "Внешний API тормозит": {
        "text": "Подменю внешний API заглушкой с задержкой и ошибками и проверю таймауты, "
        "повторы и то, что видит пользователь, когда API не ответил.",
        "code": 'wiremock.stubFor(get("/rates").willReturn(aResponse()\n'
        "    .withFixedDelay(5000).withStatus(503)))",
        "approach": "Заглушка внешнего API с задержками и 5xx, проверка таймаутов, "
        "повторов и деградации, сообщение пользователю и логирование.",
    },
    "Выкладка без простоя": {
        "text": "Выкатываю по одному поду с проверкой готовности, старые убираю только когда "
        "новые готовы. Миграции базы — совместимые со старой версией.",
        "code": "strategy:\n  type: RollingUpdate\n  rollingUpdate:\n    maxUnavailable: 0\n"
        "    maxSurge: 1",
        "approach": "Rolling update или blue-green, readiness-проверки, обратно совместимые "
        "миграции, быстрый откат и наблюдение за ошибками во время выкатки.",
    },
    "Кончается место под базу": {
        "text": "Посчитаю, что растёт: данные, индексы или журналы. Старые данные — в архив, "
        "лишние индексы — удалить, диск расширю заранее с запасом.",
        "code": "SELECT relname, pg_size_pretty(pg_total_relation_size(relid))\n"
        "FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC;",
        "approach": "Разбор роста по таблицам, архив и партиционирование, чистка индексов, "
        "расширение диска и тревога при заполнении на 80 %.",
    },
    "Ночные тревоги": {
        "text": "Сгруппирую одинаковые тревоги в одну, будить буду только по симптомам "
        "для пользователей, остальное — в рабочий чат утром.",
        "code": "route:\n  group_by: [alertname, service]\n  group_wait: 1m\n  repeat_interval: 4h",
        "approach": "Группировка и подавление дублей, тревоги по SLO вместо причин, "
        "разделение срочного и несрочного, разбор каждой ночной тревоги.",
    },
}

# Общие ответы из build_tasks — их заменяем на ответ по теме задачи.
GENERIC_ANSWERS = {
    "Сначала замерил бы, где теряется время, затем добавил кэш.",
    "@lru_cache(maxsize=1024)\ndef get_dict(key): ...",
    "Ключ идемпотентности в заголовке, уникальный индекс в БД, повтор "
    "возвращает сохранённый результат.",
}


def fit_answers() -> None:
    """Ответ в каждой сданной задаче — по её теме (название задачи → TASK_ANSWERS).

    Свои ответы (например, у candidate.nofsp@) не трогаем — только общие заготовки."""
    generic = GENERIC_ANSWERS | set(EXTRA_ANSWERS.values())
    for sub in SUBMISSIONS:
        text, kind = sub.get("answer_text"), sub.get("answer_kind")
        if not text or not kind or text not in generic:
            continue
        sub["answer_text"] = TASK_ANSWERS[sub["task_title"]][kind]


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
    cand_of_user = {c["user_id"]: c for c in CANDIDATES}
    for u in USERS:
        # Текст согласия версии 2026-10-01: кто зарегистрировался раньше, принял новую версию
        # при входе 1–3 октября (дата согласия не раньше даты версии).
        created = datetime.fromisoformat(u["created_at"])
        accepted = max(created, CONSENT_DATE + timedelta(hours=(u["id"] * 7) % 60))
        CONSENTS.append(
            {
                "id": 0,
                "user_id": u["id"],
                "type": "processing",
                "version": CONSENT_VERSION,
                "granted": True,
                "granted_at": iso(accepted),
                "revoked_at": None,
            }
        )
        if u["role"] == "candidate":
            cand = cand_of_user[u["id"]]
            granted = cand["publication_consent"]
            CONSENTS.append(
                {
                    "id": 0,
                    "user_id": u["id"],
                    "type": "publication",
                    "version": CONSENT_VERSION,
                    "granted": granted,
                    "granted_at": iso(accepted) if granted or u["id"] == 37 else None,
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
        "cat_se_stop": 0.30,
        "cat_max_items": 20,
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
        "description": "Соискатель с ФСП ID: Backend · Middle, есть приглашения и задания",
    },
    {
        "id": 2,
        "role": "candidate",
        "email": "candidate.nofsp@example.com",
        "password": "demo1234",
        "user_id": 26,
        "is_default": False,
        "description": "Соискатель без истории ФСП: Frontend · Junior, есть приглашения и задания",
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
    build_extra_candidates()
    build_needs_and_vacancies()
    build_invitations()
    build_demo_invitations()
    build_extra_applications()
    build_tasks()
    build_week_tasks()
    build_company_tasks()
    build_demo_tasks()
    build_extra_submissions()
    fit_answers()
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

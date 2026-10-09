"""ФСП-скор и бейджи (T5.3). Чистые функции без БД и сети.

Формула — `docs/integration/fsp.md`, раздел 7:

    S = Σ по достижениям  L(уровень) × R(результат) × F(возраст)
    ФСП-скор = round(100 × (1 − e^(−S / 3)))

- L: региональный 1, всероссийский 2, международный 3;
- R: 1 место 1,0; 2 место 0,85; 3 место 0,7; диплом I 0,8; II 0,6; III 0,45;
  4–10 место 0,4; ниже 10-го 0,25; участие 0,1;
- F = 0,5^(возраст в годах / 2) — результат «стареет» вдвое за 2 года.

Сумма с насыщением: много слабых участий не обгоняют одну победу. Нет достижений —
скор None («нет данных»), а не 0: отсутствие истории ФСП не штрафуется (T5.4).

Та же формула продублирована в `scripts/seed/generate_fixtures.py` (генератор только на
стандартной библиотеке); тест `test_fsp_scoring.py` сверяет фикстуры с этим модулем.

Релевантность дисциплины специальности (ответ организаторов, E08): в подборе очки каждого
достижения умножаются на `DISCIPLINE_RELEVANCE[дисциплина][специализация потребности]` —
`fsp_score_for(...)`. Общий ФСП-скор профиля (`fsp_score`) не меняется.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Protocol

LEVEL_WEIGHT: dict[str, float] = {"regional": 1.0, "national": 2.0, "international": 3.0}
PLACE_WEIGHT: dict[int, float] = {1: 1.0, 2: 0.85, 3: 0.7}
PLACE_TOP10_WEIGHT = 0.4
PLACE_OTHER_WEIGHT = 0.25
DIPLOMA_WEIGHT: dict[int, float] = {1: 0.8, 2: 0.6, 3: 0.45}
PARTICIPATION_WEIGHT = 0.1
HALF_LIFE_YEARS = 2.0
SATURATION = 3.0

DIPLOMA_LABEL: dict[int, str] = {
    1: "Диплом I степени",
    2: "Диплом II степени",
    3: "Диплом III степени",
}
_DIPLOMA_DEGREE = {label: degree for degree, label in DIPLOMA_LABEL.items()}

LEVEL_GENITIVE = {
    "regional": "регионального",
    "national": "всероссийского",
    "international": "международного",
}
DISCIPLINE_GENITIVE = {
    "product": "продуктовому программированию",
    "algorithmic": "алгоритмическому программированию",
    "cybersecurity": "программированию систем ИБ",
    "uas": "программированию БАС",
    "robotics": "программированию робототехники",
}
SPECIALIZATION_LABELS = {
    "backend": "Backend",
    "frontend": "Frontend",
    "mobile": "Mobile",
    "data_ml": "Data Science / ML",
    "qa": "QA",
    "devops": "DevOps",
}

# Релевантность дисциплины ФСП специализации платформы, 0..1 (ответ организаторов, E08:
# «специалист по ИБ, участвовавший в соревнованиях по ИБ, релевантнее, чем участвовавший
# в соревнованиях по робототехнике»). Шкала:
# - 1,0 — профильно: дисциплина тренирует ровно то, что нужно в работе;
# - 0,7–0,9 — смежно: заметная часть навыков совпадает;
# - 0,3–0,6 — далеко, но полезно: командная работа, дедлайны, инженерная культура.
# Ни одна дисциплина не обнуляется: соревнования ФСП полезны любому разработчику.
# Продуктовое и алгоритмическое программирование полезно всем; ИБ сильнее для DevOps,
# QA и Backend; БАС и робототехника сильнее для Data Science / ML и Mobile.
DISCIPLINE_RELEVANCE: dict[str, dict[str, float]] = {
    "product": {
        "backend": 1.0,
        "frontend": 1.0,
        "mobile": 1.0,
        "data_ml": 0.7,
        "qa": 0.8,
        "devops": 0.7,
    },
    "algorithmic": {
        "backend": 1.0,
        "frontend": 0.7,
        "mobile": 0.7,
        "data_ml": 1.0,
        "qa": 0.7,
        "devops": 0.6,
    },
    "cybersecurity": {
        "backend": 0.8,
        "frontend": 0.4,
        "mobile": 0.4,
        "data_ml": 0.4,
        "qa": 0.9,
        "devops": 1.0,
    },
    "uas": {
        "backend": 0.5,
        "frontend": 0.3,
        "mobile": 0.7,
        "data_ml": 0.9,
        "qa": 0.5,
        "devops": 0.5,
    },
    "robotics": {
        "backend": 0.5,
        "frontend": 0.3,
        "mobile": 0.6,
        "data_ml": 0.9,
        "qa": 0.5,
        "devops": 0.5,
    },
}
# С какого коэффициента достижение помечается «профильно для …»
PROFILE_RELEVANCE = 0.9
CAPTAIN_PREFIX = "Капитан"
LEVEL_ORDER = ("international", "national", "regional")


class AchievementLike(Protocol):
    """Что нужно формуле от достижения: подходит ORM-модель FspAchievement и FspAchievementData."""

    @property
    def level(self) -> str: ...
    @property
    def place(self) -> int | None: ...
    @property
    def diploma(self) -> str | None: ...
    @property
    def date(self) -> date: ...
    @property
    def role(self) -> str | None: ...
    @property
    def discipline(self) -> str: ...


@dataclass(frozen=True)
class FspAchievementData:
    """Достижение без БД (для тестов и расчёта по словарю из фикстур/API)."""

    level: str
    date: date
    place: int | None = None
    diploma: str | None = None
    role: str | None = None
    discipline: str = "product"

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "FspAchievementData":
        raw_date = data["date"]
        return cls(
            level=data["level"],
            date=raw_date if isinstance(raw_date, date) else date.fromisoformat(raw_date),
            place=data.get("place"),
            diploma=data.get("diploma"),
            role=data.get("role"),
            discipline=data.get("discipline") or "product",
        )


def diploma_degree(diploma: str | None) -> int | None:
    """«Диплом II степени» → 2. Неизвестная подпись диплома считается III степенью."""
    if diploma is None:
        return None
    return _DIPLOMA_DEGREE.get(diploma, 3)


def result_weight(place: int | None, diploma: str | None) -> float:
    """R: вес результата. Нет ни места, ни диплома — это участие."""
    if place is not None:
        return PLACE_WEIGHT.get(place, PLACE_TOP10_WEIGHT if place <= 10 else PLACE_OTHER_WEIGHT)
    degree = diploma_degree(diploma)
    if degree is not None:
        return DIPLOMA_WEIGHT[degree]
    return PARTICIPATION_WEIGHT


def freshness(achieved: date, today: date) -> float:
    """F: 0,5^(возраст/2). Дата в будущем считается сегодняшней."""
    age_years = max(0, (today - achieved).days) / 365.25
    return float(0.5 ** (age_years / HALF_LIFE_YEARS))


def achievement_points(a: AchievementLike, today: date) -> float:
    return (
        LEVEL_WEIGHT.get(a.level, 1.0)
        * result_weight(a.place, a.diploma)
        * freshness(a.date, today)
    )


def raw_score(achievements: Sequence[AchievementLike], today: date | None = None) -> float:
    """S — сумма очков до насыщения."""
    day = today or _today()
    return sum(achievement_points(a, day) for a in achievements)


def fsp_score(achievements: Sequence[AchievementLike], today: date | None = None) -> float | None:
    """ФСП-скор 0–100 (целое число в float). Нет достижений — None («нет данных»).

    Эту функцию вызывает ранжирование (T6.3): вклад в счёт = (скор or 0) / 100, без штрафа
    за отсутствие истории.
    """
    if not achievements:
        return None
    s = raw_score(achievements, today)
    return float(round(100 * (1 - math.exp(-s / SATURATION))))


def is_prize(a: AchievementLike) -> bool:
    """Призовой результат: 1–3 место или диплом любой степени."""
    return a.diploma is not None or (a.place is not None and a.place <= 3)


def is_captain(a: AchievementLike) -> bool:
    return (a.role or "").startswith(CAPTAIN_PREFIX)


def _badge(badge_id: str, title: str, level: str | None = None) -> dict[str, Any]:
    return {"id": badge_id, "title": title, "level": level, "verified": True}


def fsp_badges(achievements: Sequence[AchievementLike]) -> list[dict[str, Any]]:
    """Бейджи «подтверждено ФСП» (формат схемы FspBadge), от сильных к слабым.

    - по каждому уровню не больше одного бейджа: «Победитель …» (1 место) или «Призёр …»;
    - «Капитан команды» — если хоть раз был капитаном;
    - «Участник N соревнований ФСП» (или «Участник соревнования ФСП» при одном).
    """
    badges: list[dict[str, Any]] = []
    for level in LEVEL_ORDER:
        on_level = [a for a in achievements if a.level == level]
        if any(a.place == 1 for a in on_level):
            title = f"Победитель {LEVEL_GENITIVE[level]} соревнования"
            badges.append(_badge(f"{level}_winner", title, level))
        elif any(is_prize(a) for a in on_level):
            badges.append(
                _badge(f"{level}_prize", f"Призёр {LEVEL_GENITIVE[level]} соревнования", level)
            )
    if any(is_captain(a) for a in achievements):
        badges.append(_badge("captain", "Капитан команды"))
    if len(achievements) >= 2:
        badges.append(_badge("participant_many", f"Участник {len(achievements)} соревнований ФСП"))
    elif len(achievements) == 1:
        badges.append(_badge("participant", "Участник соревнования ФСП"))
    return badges


def fsp_reason(achievements: Sequence[AchievementLike], today: date | None = None) -> str | None:
    """Одна строка для «почему в подборке»: лучший результат по очкам формулы.

    Пример: «Призёр всероссийского соревнования по продуктовому программированию, 2026».
    Без достижений — None (строку не показываем).
    """
    if not achievements:
        return None
    day = today or _today()
    best = max(achievements, key=lambda a: (achievement_points(a, day), a.date))
    return describe_achievement(best)


def describe_achievement(a: AchievementLike) -> str:
    """«Призёр всероссийского соревнования по продуктовому программированию, 2026»."""
    if a.place == 1:
        what = "Победитель"
    elif is_prize(a):
        what = "Призёр"
    else:
        what = "Участник"
    discipline = DISCIPLINE_GENITIVE.get(a.discipline, "спортивному программированию")
    level = LEVEL_GENITIVE.get(a.level, "")
    return f"{what} {level} соревнования по {discipline}, {a.date.year}".replace("  ", " ")


# ---------------------------------------------------------------- релевантность (E08)


def discipline_relevance(discipline: str, specialization: str | None) -> float:
    """Коэффициент 0..1. Специализация не задана или код неизвестен — 1 (как без таблицы)."""
    if not specialization:
        return 1.0
    return DISCIPLINE_RELEVANCE.get(discipline, {}).get(specialization, 1.0)


def is_profile_discipline(discipline: str, specialization: str | None) -> bool:
    """Профильная дисциплина для специализации (коэффициент ≥ PROFILE_RELEVANCE)."""
    if not specialization:
        return False
    return discipline_relevance(discipline, specialization) >= PROFILE_RELEVANCE


def fsp_score_for(
    achievements: Sequence[AchievementLike],
    specialization: str | None,
    today: date | None = None,
) -> float | None:
    """ФСП-скор 0–100 под специализацию потребности — его берёт ранжирование.

    Формула `fsp_score`, но очки каждого достижения умножены на `discipline_relevance`.
    Нет достижений — None: отсутствие истории ФСП по-прежнему не штрафуется.
    """
    if not achievements:
        return None
    day = today or _today()
    s = sum(
        achievement_points(a, day) * discipline_relevance(a.discipline, specialization)
        for a in achievements
    )
    return float(round(100 * (1 - math.exp(-s / SATURATION))))


def profile_note(specialization: str) -> str:
    return f"профильно для {SPECIALIZATION_LABELS.get(specialization, specialization)}"


def fsp_reason_for(
    achievements: Sequence[AchievementLike],
    specialization: str | None,
    today: date | None = None,
) -> str | None:
    """Строка «почему в подборке» под специализацию потребности.

    Лучшее достижение — по очкам × релевантность. Профильная дисциплина — с пометкой:
    «Призёр всероссийского соревнования по программированию систем ИБ, 2025 — профильно
    для DevOps». Без специализации — как `fsp_reason`.
    """
    if not achievements:
        return None
    if not specialization:
        return fsp_reason(achievements, today)
    day = today or _today()
    best = max(
        achievements,
        key=lambda a: (
            achievement_points(a, day) * discipline_relevance(a.discipline, specialization),
            a.date,
        ),
    )
    text = describe_achievement(best)
    if is_profile_discipline(best.discipline, specialization):
        text += f" — {profile_note(specialization)}"
    return text


def fsp_profile_note(
    achievements: Sequence[AchievementLike],
    specialization: str | None,
    today: date | None = None,
) -> str | None:
    """Пометка рядом с бейджами: лучшее достижение по профильной дисциплине специализации.

    Нет профильных достижений — None (пометки нет, штрафа тоже).
    """
    if not specialization:
        return None
    profile = [a for a in achievements if is_profile_discipline(a.discipline, specialization)]
    if not profile:
        return None
    day = today or _today()
    best = max(profile, key=lambda a: (achievement_points(a, day), a.date))
    return f"{describe_achievement(best)} — {profile_note(specialization)}"


@dataclass
class FspSummary:
    """Сводка ФСП по кандидату для профиля, выдачи и ранжирования."""

    candidate_id: int
    linked: bool = False
    fsp_id: str | None = None
    achievements_count: int = 0
    fsp_score: float | None = None
    badges: list[dict[str, Any]] = field(default_factory=list)
    reason: str | None = None
    # сами достижения: скор и пометки под специализацию потребности (`fsp_score_for`)
    achievements: list[FspAchievementData] = field(default_factory=list)

    @property
    def has_history(self) -> bool:
        return self.achievements_count > 0


def summarize(
    candidate_id: int,
    fsp_id: str | None,
    achievements: Sequence[AchievementLike],
    today: date | None = None,
) -> FspSummary:
    if fsp_id is None:
        return FspSummary(candidate_id=candidate_id)
    return FspSummary(
        candidate_id=candidate_id,
        linked=True,
        fsp_id=fsp_id,
        achievements_count=len(achievements),
        fsp_score=fsp_score(achievements, today),
        badges=fsp_badges(achievements),
        reason=fsp_reason(achievements, today),
        achievements=[as_data(a) for a in achievements],
    )


def as_data(a: AchievementLike) -> FspAchievementData:
    """Копия достижения без привязки к ORM-сессии."""
    return FspAchievementData(
        level=a.level,
        date=a.date,
        place=a.place,
        diploma=a.diploma,
        role=a.role,
        discipline=a.discipline,
    )


def _today() -> date:
    return datetime.now(UTC).date()

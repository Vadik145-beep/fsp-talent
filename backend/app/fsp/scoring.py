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
    if best.place == 1:
        what = "Победитель"
    elif is_prize(best):
        what = "Призёр"
    else:
        what = "Участник"
    discipline = DISCIPLINE_GENITIVE.get(best.discipline, "спортивному программированию")
    level = LEVEL_GENITIVE.get(best.level, "")
    return f"{what} {level} соревнования по {discipline}, {best.date.year}".replace("  ", " ")


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
    )


def _today() -> date:
    return datetime.now(UTC).date()

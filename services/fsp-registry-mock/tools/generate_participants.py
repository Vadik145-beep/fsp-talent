"""Генератор синтетических данных мока реестра ФСП.

Детерминированный: при одном и том же SEED даёт байт-в-байт одинаковый JSON.
Результат: services/fsp-registry-mock/data/participants.json (коммитится в репо).

Запуск из корня репозитория:
    python services/fsp-registry-mock/tools/generate_participants.py

ВСЕ ДАННЫЕ СИНТЕТИЧЕСКИЕ: ФИО, команды, соревнования, места и рейтинги выдуманы.
Названия соревнований составлены по общему образцу и не утверждают, что такие
мероприятия проводились на самом деле.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20261006
OUT = Path(__file__).resolve().parent.parent / "data" / "participants.json"
UPDATED_AT = "2026-10-01T03:00:00Z"  # фиксированная «дата выгрузки», чтобы файл не менялся
PROTOCOL_BASE = "https://registry.fsp.example/protocols"  # домен .example зарезервирован
PROFILE_BASE = "https://registry.fsp.example/participants"

DISCIPLINES = [
    {"code": "product", "title": "Продуктовое программирование"},
    {"code": "algorithmic", "title": "Алгоритмическое программирование"},
    {"code": "security", "title": "Программирование систем информационной безопасности"},
    {"code": "uav", "title": "Программирование беспилотных авиационных систем"},
    {"code": "robotics", "title": "Программирование робототехники"},
]
LEVELS = [
    {"code": "regional", "title": "Региональный"},
    {"code": "national", "title": "Всероссийский"},
    {"code": "international", "title": "Международный"},
]
DISC = {d["code"]: d for d in DISCIPLINES}
LEV = {lv["code"]: lv for lv in LEVELS}

# Рейтинг-очки реестра: база по уровню × множитель результата.
# Это «очки федерации» (как у реального рейтинга), а не наш ФСП-скор — он считается в бэкенде.
LEVEL_BASE = {"regional": 100, "national": 250, "international": 400}

# Каталог соревнований: (id, название, уровень, дисциплина, дата, формат участия,
# размер команды, участников/команд всего, регион проведения или None).
CATALOG = [
    (
        "COMP-2023-01",
        "Региональный чемпионат по продуктовому программированию",
        "regional",
        "product",
        "2023-04-15",
        "team",
        4,
        64,
        "Республика Татарстан",
    ),
    (
        "COMP-2023-02",
        "Открытые соревнования по алгоритмическому программированию «Весенний раунд»",
        "national",
        "algorithmic",
        "2023-05-20",
        "individual",
        1,
        1200,
        None,
    ),
    (
        "COMP-2023-03",
        "Всероссийские соревнования по программированию систем ИБ (Attack-Defense)",
        "national",
        "security",
        "2023-10-07",
        "team",
        5,
        90,
        None,
    ),
    (
        "COMP-2023-04",
        "Региональные соревнования по программированию БАС",
        "regional",
        "uav",
        "2023-09-16",
        "team",
        3,
        18,
        "Новосибирская область",
    ),
    (
        "COMP-2023-05",
        "Всероссийский хакатон по продуктовому программированию «Осенний спринт»",
        "national",
        "product",
        "2023-11-25",
        "team",
        5,
        210,
        None,
    ),
    (
        "COMP-2024-01",
        "Региональный чемпионат по алгоритмическому программированию (командный)",
        "regional",
        "algorithmic",
        "2024-02-10",
        "team",
        3,
        140,
        "Свердловская область",
    ),
    (
        "COMP-2024-02",
        "Всероссийские соревнования по программированию робототехники",
        "national",
        "robotics",
        "2024-04-13",
        "team",
        4,
        36,
        None,
    ),
    (
        "COMP-2024-03",
        "Международный онлайн-турнир по алгоритмическому программированию",
        "international",
        "algorithmic",
        "2024-05-25",
        "individual",
        1,
        3400,
        None,
    ),
    (
        "COMP-2024-04",
        "Региональные соревнования по программированию систем ИБ (CTF)",
        "regional",
        "security",
        "2024-06-08",
        "team",
        4,
        75,
        "г. Москва",
    ),
    (
        "COMP-2024-05",
        "Всероссийский чемпионат по продуктовому программированию, финал",
        "national",
        "product",
        "2024-09-28",
        "team",
        5,
        120,
        None,
    ),
    (
        "COMP-2024-06",
        "Всероссийские соревнования по программированию БАС",
        "national",
        "uav",
        "2024-10-19",
        "team",
        3,
        40,
        None,
    ),
    (
        "COMP-2024-07",
        "Кубок по алгоритмическому программированию «Зимний раунд»",
        "national",
        "algorithmic",
        "2024-12-07",
        "individual",
        1,
        1500,
        None,
    ),
    (
        "COMP-2025-01",
        "Региональный хакатон по продуктовому программированию",
        "regional",
        "product",
        "2025-03-01",
        "team",
        4,
        48,
        "Нижегородская область",
    ),
    (
        "COMP-2025-02",
        "Международные онлайн-соревнования по программированию систем ИБ (CTF)",
        "international",
        "security",
        "2025-04-19",
        "team",
        4,
        600,
        None,
    ),
    (
        "COMP-2025-03",
        "Всероссийские соревнования по алгоритмическому программированию (команды)",
        "national",
        "algorithmic",
        "2025-05-17",
        "team",
        3,
        300,
        None,
    ),
    (
        "COMP-2025-04",
        "Региональные соревнования по программированию робототехники",
        "regional",
        "robotics",
        "2025-06-14",
        "team",
        3,
        22,
        "г. Санкт-Петербург",
    ),
    (
        "COMP-2025-05",
        "Международный онлайн-хакатон по продуктовому программированию",
        "international",
        "product",
        "2025-09-13",
        "team",
        5,
        260,
        None,
    ),
    (
        "COMP-2025-06",
        "Всероссийские соревнования по программированию систем ИБ (Attack-Defense)",
        "national",
        "security",
        "2025-10-25",
        "team",
        5,
        110,
        None,
    ),
    (
        "COMP-2025-07",
        "Региональный чемпионат по алгоритмическому программированию",
        "regional",
        "algorithmic",
        "2025-11-22",
        "individual",
        1,
        260,
        "Республика Башкортостан",
    ),
    (
        "COMP-2026-01",
        "Всероссийский хакатон по продуктовому программированию «Весна-2026»",
        "national",
        "product",
        "2026-03-21",
        "team",
        5,
        180,
        None,
    ),
    (
        "COMP-2026-02",
        "Всероссийские соревнования по программированию БАС, финал",
        "national",
        "uav",
        "2026-04-25",
        "team",
        3,
        30,
        None,
    ),
    (
        "COMP-2026-03",
        "Региональные соревнования по программированию систем ИБ (CTF)",
        "regional",
        "security",
        "2026-05-16",
        "team",
        4,
        50,
        "Краснодарский край",
    ),
    (
        "COMP-2026-04",
        "Международный онлайн-турнир по алгоритмическому программированию «Лето»",
        "international",
        "algorithmic",
        "2026-07-11",
        "individual",
        1,
        2800,
        None,
    ),
    (
        "COMP-2026-05",
        "Всероссийский чемпионат по продуктовому программированию, финал",
        "national",
        "product",
        "2026-09-26",
        "team",
        5,
        140,
        None,
    ),
]

REGIONS = [
    "г. Москва",
    "г. Санкт-Петербург",
    "Республика Татарстан",
    "Новосибирская область",
    "Свердловская область",
    "Нижегородская область",
    "Краснодарский край",
    "Республика Башкортостан",
    "Самарская область",
    "Томская область",
    "Ростовская область",
    "Пермский край",
    "Воронежская область",
    "Калининградская область",
]

MALE_FIRST = [
    "Артём",
    "Иван",
    "Максим",
    "Дмитрий",
    "Никита",
    "Егор",
    "Михаил",
    "Кирилл",
    "Алексей",
    "Тимур",
    "Роман",
    "Павел",
    "Глеб",
    "Илья",
    "Арсений",
]
FEMALE_FIRST = [
    "Анна",
    "Мария",
    "Екатерина",
    "Дарья",
    "Полина",
    "Алина",
    "Софья",
    "Виктория",
    "Ксения",
    "Елизавета",
    "Вероника",
    "Ульяна",
]
MALE_MIDDLE = [
    "Андреевич",
    "Сергеевич",
    "Игоревич",
    "Олегович",
    "Викторович",
    "Павлович",
    "Алексеевич",
    "Романович",
    "Денисович",
    "Евгеньевич",
]
FEMALE_MIDDLE = [
    "Андреевна",
    "Сергеевна",
    "Игоревна",
    "Олеговна",
    "Викторовна",
    "Павловна",
    "Алексеевна",
    "Романовна",
    "Денисовна",
    "Евгеньевна",
]
# Фамилии: (мужская форма, женская форма)
LAST = [
    ("Соколов", "Соколова"),
    ("Лебедев", "Лебедева"),
    ("Морозов", "Морозова"),
    ("Волков", "Волкова"),
    ("Зайцев", "Зайцева"),
    ("Белов", "Белова"),
    ("Карпов", "Карпова"),
    ("Орлов", "Орлова"),
    ("Киселёв", "Киселёва"),
    ("Тихонов", "Тихонова"),
    ("Гусев", "Гусева"),
    ("Филиппов", "Филиппова"),
    ("Комаров", "Комарова"),
    ("Медведев", "Медведева"),
    ("Сафин", "Сафина"),
    ("Гарипов", "Гарипова"),
    ("Ершов", "Ершова"),
    ("Баранов", "Баранова"),
    ("Широков", "Широкова"),
    ("Никитин", "Никитина"),
    ("Абрамов", "Абрамова"),
    ("Латыпов", "Латыпова"),
    ("Голубев", "Голубева"),
    ("Крылов", "Крылова"),
]

TEAM_ADJ = [
    "Быстрые",
    "Тихие",
    "Квантовые",
    "Северные",
    "Рекурсивные",
    "Цифровые",
    "Ночные",
    "Асинхронные",
    "Красные",
    "Стальные",
    "Ленивые",
    "Бинарные",
]
TEAM_NOUN = [
    "лисы",
    "ежи",
    "биты",
    "совы",
    "пингвины",
    "дятлы",
    "куницы",
    "сурки",
    "кодеры",
    "грифоны",
    "тюлени",
    "кометы",
]

ROLES = {
    "product": [
        "бэкенд-разработчик",
        "фронтенд-разработчик",
        "фулстек-разработчик",
        "ML-инженер",
        "аналитик",
        "дизайнер интерфейсов",
        "мобильный разработчик",
    ],
    "algorithmic": ["участник команды"],
    "security": [
        "специалист по защите сервисов",
        "реверс-инженер",
        "специалист по веб-уязвимостям",
        "криптограф команды",
    ],
    "uav": [
        "программист полётного контроллера",
        "инженер компьютерного зрения",
        "оператор-испытатель",
    ],
    "robotics": ["программист робота", "инженер-электроник", "инженер компьютерного зрения"],
}

# Основная дисциплина участников FSP-000001…030 (по кругу, с перекосом в продуктовое
# и алгоритмическое — их больше всего среди IT-кандидатов).
PRIMARY_CYCLE = [
    "product",
    "algorithmic",
    "product",
    "security",
    "algorithmic",
    "product",
    "uav",
    "product",
    "algorithmic",
    "robotics",
]
# Сколько достижений у участника FSP-000001…030 (вручную, чтобы был разброс от 1 до 8).
COUNTS = [7, 5, 4, 6, 3, 2, 1, 8, 3, 2, 1, 4, 5, 2, 1, 3, 6, 2, 1, 1, 2, 4, 3, 1, 2, 5, 1, 2, 3, 1]
# «Сила» участника 0..1 — влияет на места. Первые пять — демо-пользователи Keycloak.
STRENGTH = [0.95, 0.7, 0.5, 0.8, 0.3]

# Дополнительный блок участников с историей для демо-банка кандидатов платформы:
# FSP-000101…FSP-000180. Номера 041…100 свободны (по ним мок отвечает 404).
# Свой генератор случайных чисел — первые 40 участников от этого блока не зависят.
EXTRA_IDS = range(101, 181)
EXTRA_PRIMARY = [
    "product",
    "algorithmic",
    "product",
    "security",
    "algorithmic",
    "robotics",
    "product",
    "uav",
    "algorithmic",
    "product",
    "security",
    "robotics",
    "product",
    "uav",
    "algorithmic",
    "security",
]
EXTRA_COUNTS = [1, 2, 3, 1, 4, 2, 5, 2, 3, 1, 6, 2, 3, 4, 1, 2, 3, 5, 2, 1]


def result_for(rng: random.Random, strength: float, level: str, total: int) -> dict:
    """Результат участника в соревновании: место, диплом или участие."""
    roll = rng.random() * 0.6 + strength * 0.5  # 0..1.1, выше = лучше
    if roll > 0.98:
        place = 1
    elif roll > 0.9:
        place = 2
    elif roll > 0.82:
        place = 3
    else:
        place = None
    if place is not None:
        return {"kind": "place", "place": place, "diploma_degree": None, "label": f"{place} место"}
    # На всероссийском и международном уровнях — дипломы степеней, на региональном — места.
    if level != "regional" and roll > 0.55:
        degree = 1 if roll > 0.75 else (2 if roll > 0.65 else 3)
        return {
            "kind": "diploma",
            "place": None,
            "diploma_degree": degree,
            "label": f"Диплом {'I' * degree} степени",
        }
    if roll > 0.45:
        place = 4 + int((0.82 - roll) / 0.37 * max(1, min(total, 60) - 4))
        return {
            "kind": "place",
            "place": place,
            "diploma_degree": None,
            "label": f"{place} место из {total}",
        }
    return {"kind": "participant", "place": None, "diploma_degree": None, "label": "Участник"}


def result_multiplier(res: dict) -> float:
    if res["kind"] == "place":
        p = res["place"]
        if p == 1:
            return 1.0
        if p == 2:
            return 0.85
        if p == 3:
            return 0.7
        return 0.45 if p <= 10 else 0.3
    if res["kind"] == "diploma":
        return {1: 0.8, 2: 0.6, 3: 0.45}[res["diploma_degree"]]
    return 0.15


def organizer(level: str, region: str | None) -> str:
    if level == "regional":
        return f"Региональное отделение ФСП ({region})"
    if level == "national":
        return "Федерация спортивного программирования России"
    return "ФСП России и партнёры (международный зачёт)"


def make_name(rng: random.Random) -> dict:
    female = rng.random() < 0.35
    last = rng.choice(LAST)[1 if female else 0]
    first = rng.choice(FEMALE_FIRST if female else MALE_FIRST)
    middle = rng.choice(FEMALE_MIDDLE if female else MALE_MIDDLE)
    return {
        "last_name": last,
        "first_name": first,
        "middle_name": middle,
        "full_name": f"{last} {first} {middle}",
    }


def make_achievements(
    rng: random.Random,
    n: int,
    competitions: list[dict],
    primary: str,
    count: int,
    strength: float,
) -> list[dict]:
    """Достижения участника: ~75 % — в основной дисциплине, остальные — в других."""
    own = [c for c in competitions if c["discipline"] == primary]
    other = [c for c in competitions if c["discipline"] != primary]
    chosen: list[dict] = []
    pool_own, pool_other = own[:], other[:]
    while len(chosen) < count and (pool_own or pool_other):
        pool = pool_own if (pool_own and (rng.random() < 0.75 or not pool_other)) else pool_other
        chosen.append(pool.pop(rng.randrange(len(pool))))
    chosen.sort(key=lambda c: c["date"])
    # Роль в команде у человека обычно постоянная, капитанит чаще сильный участник.
    captain_rate = 0.1 + 0.4 * strength
    roles = {d: rng.choice(r) for d, r in ROLES.items()}
    achievements = []
    for i, comp in enumerate(chosen, start=1):
        res = result_for(rng, strength, comp["level"], comp["participants_total"])
        points = round(LEVEL_BASE[comp["level"]] * result_multiplier(res))
        team = None
        if comp["participation"] == "team":
            team = {
                "name": f"{rng.choice(TEAM_ADJ)} {rng.choice(TEAM_NOUN)}",
                "size": comp["team_size"],
                "role": roles[comp["discipline"]],
                "is_captain": rng.random() < captain_rate,
            }
        achievements.append(
            {
                "id": f"ACH-{n:06d}-{i:02d}",
                "competition": {
                    k: comp[k]
                    for k in (
                        "id",
                        "title",
                        "organizer",
                        "region",
                        "participants_total",
                        "protocol_url",
                    )
                },
                "discipline": DISC[comp["discipline"]],
                "level": LEV[comp["level"]],
                "date": comp["date"],
                "result": res,
                "participation": comp["participation"],
                "team": team,
                "rating_points": points,
                "verified": True,
            }
        )
    return achievements


def participant(
    fsp_id: str, name: dict, region: str, registered: date, achievements: list[dict]
) -> dict:
    return {
        "fsp_id": fsp_id,
        **name,
        "region": region,
        "registered_at": registered.isoformat(),
        "profile_url": f"{PROFILE_BASE}/{fsp_id}",
        "achievements": achievements,
    }


def build() -> dict:
    rng = random.Random(SEED)
    competitions = []
    for cid, title, level, disc, d, fmt, size, total, region in CATALOG:
        competitions.append(
            {
                "id": cid,
                "title": title,
                "level": level,
                "discipline": disc,
                "date": d,
                "participation": fmt,
                "team_size": size,
                "participants_total": total,
                "region": region,
                "organizer": organizer(level, region),
                "protocol_url": f"{PROTOCOL_BASE}/{cid}.pdf",
            }
        )

    used_names: set[str] = set()
    participants = []
    for n in range(1, 41):
        fsp_id = f"FSP-{n:06d}"
        while True:
            name = make_name(rng)
            if name["full_name"] not in used_names:
                used_names.add(name["full_name"])
                break
        region = rng.choice(REGIONS)
        has_history = n <= 30
        achievements = []
        if has_history:
            primary = PRIMARY_CYCLE[(n - 1) % len(PRIMARY_CYCLE)]
            count = COUNTS[n - 1]
            strength = STRENGTH[n - 1] if n <= len(STRENGTH) else rng.random()
            achievements = make_achievements(rng, n, competitions, primary, count, strength)
            first = date.fromisoformat(achievements[0]["date"])
            registered = first - timedelta(days=rng.randint(20, 400))
        else:
            # Без истории: зарегистрировались недавно и ещё не участвовали.
            registered = date(2026, 1, 10) + timedelta(days=rng.randint(0, 250))
        participants.append(participant(fsp_id, name, region, registered, achievements))

    # Блок FSP-000101…180: все с историей. Имя и фамилия не повторяются ни с кем в реестре —
    # на платформе кандидат с ФСП ID получает ФИО из реестра.
    xrng = random.Random(SEED + 101)
    used_pairs = {(p["first_name"], p["last_name"]) for p in participants}
    for k, n in enumerate(EXTRA_IDS):
        fsp_id = f"FSP-{n:06d}"
        while True:
            name = make_name(xrng)
            pair = (name["first_name"], name["last_name"])
            if name["full_name"] not in used_names and pair not in used_pairs:
                used_names.add(name["full_name"])
                used_pairs.add(pair)
                break
        region = xrng.choice(REGIONS)
        primary = EXTRA_PRIMARY[k % len(EXTRA_PRIMARY)]
        count = EXTRA_COUNTS[k % len(EXTRA_COUNTS)]
        strength = round(xrng.uniform(0.15, 0.9), 2)
        achievements = make_achievements(xrng, n, competitions, primary, count, strength)
        first = date.fromisoformat(achievements[0]["date"])
        registered = first - timedelta(days=xrng.randint(20, 400))
        participants.append(participant(fsp_id, name, region, registered, achievements))
    return {
        "meta": {
            "synthetic": True,
            "note": "Синтетические данные для хакатона. Люди, команды, места и рейтинги "
            "выдуманы; названия соревнований составлены по общему образцу.",
            "seed": SEED,
            "updated_at": UPDATED_AT,
            "generator": "services/fsp-registry-mock/tools/generate_participants.py",
        },
        "disciplines": DISCIPLINES,
        "levels": LEVELS,
        "competitions": competitions,
        "participants": participants,
    }


def render() -> str:
    return json.dumps(build(), ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8", newline="\n")
    print(f"Записано: {OUT}")

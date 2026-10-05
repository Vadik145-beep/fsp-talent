"""Mobile / хранение данных: где хранить секреты и файлы, запрос Room (SQLite), миграции Room.

Ответы запроса Room сверяются в тесте с настоящим SQLite (tests/engine/test_bank_mobile_storage.py).
"""

from __future__ import annotations

import random
from typing import Any

from ...templates import ItemFormat, ItemTemplate, Variant, make_single_choice

# --------------------------------------------------------------------------- где хранить


def _storage_cases(platform: str, app: str) -> list[tuple[str, str, list[str]]]:
    if platform == "ios":
        return [
            (
                f"refresh-токен авторизации пользователя в приложении «{app}»",
                "Keychain",
                [
                    "UserDefaults",
                    "JSON-файл в папке Documents",
                    "Core Data",
                    "Info.plist приложения",
                ],
            ),
            (
                f"PIN-код для быстрого входа в приложение «{app}»",
                "Keychain",
                ["UserDefaults", "Core Data", "NSCache", "файл в папке tmp"],
            ),
            (
                f"обложки товаров, которые приложение «{app}» всегда может скачать заново",
                "Папка Library/Caches",
                ["Папка Documents", "UserDefaults", "Keychain"],
            ),
            (
                f"черновики документов, созданные пользователем в приложении «{app}», "
                "которые должны попадать в резервную копию iCloud",
                "Папка Documents",
                ["Папка Library/Caches", "Папка tmp", "UserDefaults"],
            ),
            (
                f"каталог из 50 000 товаров для офлайн-поиска с фильтрами в приложении «{app}»",
                "Core Data / SwiftData (SQLite)",
                ["UserDefaults", "Keychain", "один JSON-файл, который читается целиком"],
            ),
            (
                f"секретный ключ платного стороннего API, которым пользуется приложение «{app}»",
                "Не хранить в приложении: запросы к API идут через свой сервер",
                [
                    "Keychain, записав ключ при первом запуске из кода",
                    "Info.plist приложения",
                    "Строковая константа в коде, обфусцированная",
                ],
            ),
        ]
    return [
        (
            f"refresh-токен авторизации пользователя в приложении «{app}»",
            "EncryptedSharedPreferences или DataStore с ключом из Android Keystore",
            [
                "Обычные SharedPreferences",
                "Файл во внешнем хранилище (Downloads)",
                "Поле в BuildConfig",
                "Таблица Room без шифрования",
            ],
        ),
        (
            f"PIN-код для быстрого входа в приложение «{app}»",
            "Хэш с ключом из Android Keystore (или EncryptedSharedPreferences)",
            ["Обычные SharedPreferences", "Файл в cacheDir", "Ресурс strings.xml"],
        ),
        (
            f"обложки товаров, которые приложение «{app}» всегда может скачать заново",
            "Папка cacheDir (Context.getCacheDir())",
            ["SharedPreferences в Base64", "Таблица Room с BLOB", "Android Keystore"],
        ),
        (
            f"каталог из 50 000 товаров для офлайн-поиска с фильтрами в приложении «{app}»",
            "База Room (SQLite)",
            ["SharedPreferences", "Android Keystore", "один JSON-файл, который читается целиком"],
        ),
        (
            f"секретный ключ платного стороннего API, которым пользуется приложение «{app}»",
            "Не хранить в приложении: запросы к API идут через свой сервер",
            [
                "Поле в BuildConfig из local.properties",
                "Ресурс strings.xml",
                "EncryptedSharedPreferences, записав ключ при первом запуске из кода",
            ],
        ),
    ]


def _gen_storage(rng: random.Random) -> Variant:
    platform = rng.choice(("ios", "android"))
    app = rng.choice(("Банк", "Доставка", "Фитнес", "Заметки", "Маркет", "Такси", "Аптека"))
    what, correct, distractors = rng.choice(_storage_cases(platform, app))
    name = "iOS 17, Swift" if platform == "ios" else "Android 13, Kotlin"
    return make_single_choice(
        rng,
        f"Приложение под {name}. Где правильнее всего хранить {what}?",
        correct,
        distractors,
        extra={"platform": platform},
        explanation=f"Верно: {correct}.",
    )


SECURE_STORAGE = ItemTemplate(
    id="mobile.storage_choice",
    specialization="mobile",
    topic="data_storage",
    target_grade="intern",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_storage,
    a=1.0,
    b=-1.8,
    title="Где хранить токены, кэш и данные",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- запрос Room

_ENTITIES = (
    ("Note", "notes", "priority", "done", ("Buy", "Call", "Fix", "Plan", "Read", "Send", "Write")),
    ("Task", "tasks", "points", "archived", ("Auth", "Cart", "Feed", "Push", "Sync", "Maps")),
    ("Order", "orders", "amount", "paid", ("Alpha", "Beta", "Gamma", "Delta", "Omega", "Sigma")),
    ("Track", "tracks", "plays", "liked", ("Blue", "Rain", "Fire", "Wind", "Moon", "Star")),
)


Cond = tuple[Any, ...]


def _room_pred(c: Cond, r: dict[str, Any]) -> bool:
    """Условие WHERE для строки; сравнение с NULL — не истина (строка не попадает)."""
    col, op = c[0], c[1]
    v = r[col]
    if v is None:
        return False
    v = int(v)
    if op == "=":
        return bool(v == c[2])
    if op == ">=":
        return bool(v >= c[2])
    if op == ">":
        return bool(v > c[2])
    if op == "!=":
        return bool(v != c[2])
    return bool(c[2] <= v <= c[3])


def _cond_sql(c: Cond) -> str:
    if c[1] == "BETWEEN":
        return f"{c[0]} BETWEEN {c[2]} AND {c[3]}"
    return f"{c[0]} {c[1]} {c[2]}"


def _gen_room_query(rng: random.Random) -> Variant:
    cls, table, num, flag, titles = rng.choice(_ENTITIES)
    while True:
        n_rows = rng.randint(6, 8)
        ids = rng.sample(range(1, 40), n_rows)
        rows: list[dict[str, Any]] = []
        for i in ids:
            rating = rng.choice((None, None, *range(1, 6)))
            rows.append(
                {
                    "id": i,
                    "title": rng.choice(titles) + str(rng.randint(1, 9)),
                    num: rng.randint(1, 9),
                    flag: rng.random() < 0.4,
                    "rating": rating,
                }
            )
        # условие WHERE: (колонка, оператор, значение…)
        f_val = rng.choice((0, 1))
        conds: list[Cond] = [(flag, "=", f_val)]
        kind = rng.randrange(4)
        t = rng.randint(2, 7)
        if kind == 0:
            conds.append((num, ">=", t))
        elif kind == 1:
            conds.append(("rating", ">", t - 4 if t > 4 else 1))
        elif kind == 2:
            conds.append(("rating", "!=", rng.randint(1, 5)))
        else:
            lo, hi = sorted(rng.sample(range(1, 10), 2))
            conds.append((num, "BETWEEN", lo, hi))
        op = " AND " if rng.random() < 0.75 else " OR "
        if op == " AND ":
            sel = [r for r in rows if all(_room_pred(c, r) for c in conds)]
        else:
            sel = [r for r in rows if any(_room_pred(c, r) for c in conds)]
        desc = rng.random() < 0.6
        sel.sort(key=lambda r: (-r[num] if desc else r[num], r["id"]))
        limit = rng.randint(2, 4)
        offset = rng.choice((0, 0, 0, 1))
        res = sel[offset : offset + limit]
        if len(res) >= 2:
            break
    where = op.join(_cond_sql(c) for c in conds)
    order = f"{num} {'DESC' if desc else 'ASC'}, id ASC"
    tail = f"LIMIT {limit}" + (f" OFFSET {offset}" if offset else "")
    sql = f"SELECT id FROM {table} WHERE {where} ORDER BY {order} {tail}"
    entity = [
        f'@Entity(tableName = "{table}")',
        f"data class {cls}(",
        "    @PrimaryKey val id: Int,",
        "    val title: String,",
        f"    val {num}: Int,",
        f"    val {flag}: Boolean,",
        "    val rating: Int?,",
        ")",
        "",
        "@Dao",
        f"interface {cls}Dao {{",
        f'    @Query("{sql}")',
        "    suspend fun load(): List<Int>",
        "}",
        "",
        "// содержимое таблицы:",
    ]

    def lit(r: dict[str, Any]) -> str:
        rating = "null" if r["rating"] is None else str(r["rating"])
        flag_v = "true" if r[flag] else "false"
        return f'{cls}({r["id"]}, "{r["title"]}", {r[num]}, {flag_v}, {rating})'

    data = [f"// {lit(r)}" for r in rows]
    return Variant(
        prompt=(
            "Room хранит Boolean как INTEGER (0/1), null — как NULL. Что вернёт load() "
            "для этой таблицы? Перечислите id через пробел в порядке выдачи."
        ),
        key=" ".join(str(r["id"]) for r in res),
        code="\n".join([*entity, *data]),
        extra={"language": "kotlin", "sql": sql},
        explanation="Сравнение с NULL (rating > x, rating != x) даёт NULL — строка не попадает.",
    )


ROOM_QUERY = ItemTemplate(
    id="mobile.room_query_result",
    specialization="mobile",
    topic="data_storage",
    target_grade="junior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_room_query,
    a=1.2,
    b=-0.3,
    title="Что вернёт запрос Room DAO",
    time_limit_s=210,
)

# --------------------------------------------------------------------------- миграции Room

# (поле Kotlin, тип Kotlin, корректный SQL-тип с ограничениями, неверный вариант)
_NEW_FIELDS = (
    ("age", "Int", "INTEGER NOT NULL DEFAULT 0", "INTEGER NOT NULL"),
    ("rating", "Int", "INTEGER NOT NULL DEFAULT 0", "INTEGER NOT NULL"),
    ("isVip", "Boolean", "INTEGER NOT NULL DEFAULT 0", "INTEGER NOT NULL"),
    ("nickname", "String?", "TEXT", "TEXT NOT NULL DEFAULT ''"),
    ("avatarUrl", "String?", "TEXT", "TEXT NOT NULL DEFAULT ''"),
    ("city", "String", "TEXT NOT NULL DEFAULT ''", "TEXT NOT NULL"),
    ("lastSeen", "Long?", "INTEGER", "INTEGER NOT NULL DEFAULT 0"),
)
_OLD_FIELDS = (
    ("name", "String"),
    ("email", "String"),
    ("phone", "String?"),
    ("createdAt", "Long"),
    ("balance", "Int"),
)


def _gen_room_migration(rng: random.Random) -> Variant:
    table, cls = rng.choice((("users", "User"), ("customers", "Customer"), ("members", "Member")))
    old_v = rng.randint(2, 6)
    new_v = old_v + 1
    fname, ftype, good_sql, bad_sql = rng.choice(_NEW_FIELDS)
    old_fields = rng.sample(_OLD_FIELDS, rng.randint(1, 3))
    bug = rng.choice(("version", "not_null", "not_registered", "wrong_versions", "table"))
    with_comment = rng.random() < 0.5

    lines = [
        f'@Entity(tableName = "{table}")',
        f"data class {cls}(",
        "    @PrimaryKey val id: Long,",
    ]
    lines += [f"    val {n}: {t}," for n, t in old_fields]
    lines.append(f"    val {fname}: {ftype},")
    lines += [")", ""]
    mig = f"MIGRATION_{old_v}_{new_v}"
    from_v, to_v = (new_v, new_v + 1) if bug == "wrong_versions" else (old_v, new_v)
    lines.append(f"val {mig} = object : Migration({from_v}, {to_v}) {{")
    mig_line = len(lines)
    lines.append("    override fun migrate(db: SupportSQLiteDatabase) {")
    if with_comment:
        lines.append(f"        // новое поле {fname} появилось в версии {new_v}")
    sql_table = table[:-1] if bug == "table" else table
    sql_type = bad_sql if bug == "not_null" else good_sql
    lines.append(f'        db.execSQL("ALTER TABLE {sql_table} ADD COLUMN {fname} {sql_type}")')
    sql_line = len(lines)
    lines += ["    }", "}", ""]
    version = old_v if bug == "version" else new_v
    lines.append(f"@Database(entities = [{cls}::class], version = {version})")
    ver_line = len(lines)
    lines += [
        "abstract class AppDatabase : RoomDatabase() {",
        f"    abstract fun {cls.lower()}Dao(): {cls}Dao",
        "}",
        "",
        "fun buildDb(context: Context) = Room",
        '    .databaseBuilder(context, AppDatabase::class.java, "app.db")',
    ]
    prev = [f"MIGRATION_{v}_{v + 1}" for v in range(1, old_v)]
    regs = prev if bug == "not_registered" else [*prev, mig]
    lines.append(f"    .addMigrations({', '.join(regs)})")
    reg_line = len(lines)
    lines.append("    .build()")
    key = {
        "version": ver_line,
        "not_null": sql_line,
        "not_registered": reg_line,
        "wrong_versions": mig_line,
        "table": sql_line,
    }[bug]
    prev_text = f"Миграции {', '.join(prev)} объявлены в другом файле и корректны. " if prev else ""
    return Variant(
        prompt=(
            f"В магазине опубликована версия приложения с базой Room версии {old_v}. "
            f"В новой версии в сущность {cls} добавили поле {fname}, данные пользователей "
            f"нужно сохранить. {prev_text}После обновления приложение падает при первом "
            "обращении к базе. В какой строке ошибка? Укажите номер строки."
        ),
        key=key,
        code="\n".join(lines),
        extra={"language": "kotlin", "line_count": len(lines)},
        explanation={
            "version": "Схема изменилась, а version не увеличена — Room падает при проверке.",
            "not_null": "Тип колонки в миграции не совпадает с сущностью "
            "(NOT NULL без DEFAULT невозможен в SQLite или nullable-поле объявлено NOT NULL).",
            "not_registered": f"{mig} не передана в addMigrations — Room не находит путь миграции.",
            "wrong_versions": f"Migration объявлена для {from_v}→{to_v}, а нужна {old_v}→{new_v}.",
            "table": "В ALTER TABLE указана несуществующая таблица.",
        }[bug],
    )


ROOM_MIGRATION = ItemTemplate(
    id="mobile.room_migration_bug",
    specialization="mobile",
    topic="data_storage",
    target_grade="middle",
    format=ItemFormat.FIND_BUG_LINE,
    generator=_gen_room_migration,
    a=1.2,
    b=0.3,
    title="Ошибка в миграции Room",
    time_limit_s=210,
)

TEMPLATES = (SECURE_STORAGE, ROOM_QUERY, ROOM_MIGRATION)

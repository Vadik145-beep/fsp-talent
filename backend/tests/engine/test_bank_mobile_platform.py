"""Mobile: жизненный цикл, хранение, сеть, производительность, навигация, разрешения.

Ответы пересчитываются независимо — по тексту задачи (формулировка и код), а не по
внутренним структурам генератора: SQLite для запросов Room, Node.js для расчёта
задержек retry (если node установлен), собственные модели для остального.
"""

import re
import shutil
import sqlite3
import subprocess

import pytest

from app.testing.engine.bank.mobile import (
    lifecycle,
    navigation,
    network,
    performance,
    permissions,
    storage,
)
from app.testing.engine.templates import check

SEEDS = range(150)

# --------------------------------------------------------------------------- iOS lifecycle

# Порядок по документации UIKit (UIViewController, UISceneDelegate, UIApplicationDelegate).
_VC_ORDER = [
    "init()",
    "loadView()",
    "viewDidLoad()",
    "viewWillAppear(_:)",
    "viewDidAppear(_:)",
    "viewWillDisappear(_:)",
    "viewDidDisappear(_:)",
    "deinit",
]


def test_ios_lifecycle_orders():
    t = lifecycle.IOS_LIFECYCLE
    for seed in SEEDS:
        inst = t.generate(seed)
        order = [inst.public.options[i] for i in inst.key]
        prompt = inst.public.prompt
        if "Расставьте вызовы (AppDelegate)" in prompt and "с нуля" in prompt:
            assert order == [
                "application(_:willFinishLaunchingWithOptions:)",
                "application(_:didFinishLaunchingWithOptions:)",
                "applicationDidBecomeActive(_:)",
                "applicationWillResignActive(_:)",
                "applicationDidEnterBackground(_:)",
            ]
        elif "AppDelegate)" in prompt:
            assert order[-1] == "applicationWillResignActive(_:)"
            assert order.index("applicationWillEnterForeground(_:)") < order.index(
                "applicationDidBecomeActive(_:)"
            )
        elif "SceneDelegate" in prompt:
            assert order[-1] == "sceneDidBecomeActive(_:)"
            assert order[-2] == "sceneWillEnterForeground(_:)"
        elif "корневой" in prompt or "fullScreen" in prompt:
            # экран уходит и возвращается: сначала Disappear, потом Appear
            assert order == _VC_ORDER[5:7] + _VC_ORDER[3:5]
        else:
            # один контроллер от создания до закрытия — подпоследовательность канона
            assert order == [x for x in _VC_ORDER if x in order]


# --------------------------------------------------------------------------- launchMode


def run_launch_modes(prompt: str, manifest: str) -> list[str]:
    modes = dict(re.findall(r'android:name="\.(\w+)Activity" android:launchMode="(\w+)"', manifest))
    task: list[dict] = [{"name": "Main", "id": 0}]
    next_id = 1
    for step in re.findall(r"^\d+\. (.*)$", prompt, re.M):
        if "Назад" in step:
            task = task[:-1]
            continue
        name = re.search(r"startActivity для (\w+)Activity", step)[1]
        mode = modes[name]
        existing = [k for k, a in enumerate(task) if a["name"] == name]
        if mode == "singleTop" and task[-1]["name"] == name:
            continue  # onNewIntent у верхнего экземпляра
        if mode == "singleTask" and existing:
            task = task[: existing[0] + 1]  # всё над экземпляром уничтожается
            continue
        task.append({"name": name, "id": next_id})
        next_id += 1
    return [a["name"] for a in task]


def test_launch_mode_independent():
    t = lifecycle.LAUNCH_MODE
    for seed in SEEDS:
        inst = t.generate(seed)
        task = run_launch_modes(inst.public.prompt, inst.public.code)
        if m := re.search(r"Сколько экземпляров (\w+)Activity", inst.public.prompt):
            assert task.count(m[1]) == inst.key.value, (seed, inst.public.prompt)
        else:
            assert len(task) == inst.key.value, (seed, inst.public.prompt)


def test_launch_mode_manual_example():
    # Документация «Tasks and the back stack»: singleTop на вершине и singleTask с очисткой
    modes = {"Main": "standard", "A": "singleTop", "B": "singleTask"}
    acts = [("start", "A"), ("start", "A"), ("start", "B"), ("start", "A"), ("start", "B")]
    assert lifecycle.simulate_launch_modes(modes, acts) == ["Main", "A", "B"]


# ------------------------------------------------------------- поворот и смерть процесса

_EVENT_EFFECTS = {
    # событие: (onCreate, onDestroy, init ViewModel, onCleared, onSaveInstanceState)
    "поворачивает экран": (1, 1, 0, 0, 1),
    "меняет тему системы": (1, 1, 0, 0, 1),
    "нажимает home": (0, 0, 0, 0, 1),
    "убивает процесс": (0, 0, 0, 0, 0),
    "нажимает «назад»": (0, 1, 0, 1, 0),
    "снова открывает": (1, 0, 1, 0, 0),
}
_WHAT = {
    "DetailsActivity.onCreate()": 0,
    "DetailsActivity.onDestroy()": 1,
    "блок init во DetailsViewModel": 2,
    "DetailsViewModel.onCleared()": 3,
    "DetailsActivity.onSaveInstanceState()": 4,
}


def run_lifecycle_counts(prompt: str) -> int:
    what = next(v for k, v in _WHAT.items() if f"вызван {k}?" in prompt)
    total = [1, 0, 1, 0, 0]  # открытие DetailsActivity
    steps = re.findall(r"^\d+\. (.*)$", prompt, re.M)
    killed = False
    for step in steps:
        low = step.lower()
        if "возвращается" in low:
            if killed:  # процесс создан заново: новые Activity и ViewModel
                total[0] += 1
                total[2] += 1
            killed = False
            continue
        eff = next(v for k, v in _EVENT_EFFECTS.items() if k in low)
        killed = killed or "убивает процесс" in low
        total = [a + b for a, b in zip(total, eff, strict=True)]
    return total[what]


def test_lifecycle_counts_independent():
    t = lifecycle.LIFECYCLE_COUNTS
    for seed in SEEDS:
        inst = t.generate(seed)
        assert run_lifecycle_counts(inst.public.prompt) == inst.key.value, (
            seed,
            inst.public.prompt,
        )


def test_lifecycle_counts_manual_examples():
    # ViewModel переживает поворот; при смерти процесса onCleared не вызывается
    ev = ["rotate", "home", "kill", "return_after_kill", "back"]
    c = lifecycle.count_lifecycle(ev)
    assert c == {"create": 3, "destroy": 2, "vm_init": 2, "cleared": 1, "save": 2}


# --------------------------------------------------------------------------- хранение


def test_storage_choice_keywords():
    t = storage.SECURE_STORAGE
    for seed in SEEDS:
        inst = t.generate(seed)
        p = inst.public.prompt
        ans = inst.public.options[inst.key]
        if "токен" in p or "PIN" in p:
            assert "Keychain" in ans or "Keystore" in ans
            assert "UserDefaults" not in ans and "Обычные" not in ans
        elif "секретный ключ" in p:
            assert ans.startswith("Не хранить")
        elif "скачать заново" in p:
            assert "Caches" in ans or "cacheDir" in ans
        elif "черновики" in p:
            assert ans == "Папка Documents"
        else:
            assert "SQLite" in ans


def _room_parse(code: str):
    sql = re.search(r'@Query\("(.*)"\)', code)[1]
    table = re.search(r'tableName = "(\w+)"', code)[1]
    cols = re.findall(r"val (\w+): ", code)
    rows = []
    for m in re.finditer(r"^// \w+\((.*)\)$", code, re.M):
        parts = [p.strip() for p in m[1].split(",")]
        vals = []
        for p in parts:
            if p == "null":
                vals.append(None)
            elif p in ("true", "false"):
                vals.append(1 if p == "true" else 0)  # Room: Boolean → INTEGER
            elif p.startswith('"'):
                vals.append(p.strip('"'))
            else:
                vals.append(int(p))
        rows.append(vals)
    return sql, table, cols, rows


def test_room_query_matches_sqlite():
    t = storage.ROOM_QUERY
    for seed in SEEDS:
        inst = t.generate(seed)
        sql, table, cols, rows = _room_parse(inst.public.code)
        db = sqlite3.connect(":memory:")
        db.execute(
            f"CREATE TABLE {table} (id INTEGER PRIMARY KEY NOT NULL, title TEXT NOT NULL, "
            f"{cols[2]} INTEGER NOT NULL, {cols[3]} INTEGER NOT NULL, rating INTEGER)"
        )
        db.executemany(f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?)", rows)
        got = " ".join(str(r[0]) for r in db.execute(sql))
        assert check(inst, got), (seed, sql, got, inst.key)


_SQL_TYPE = {"Int": "INTEGER", "Long": "INTEGER", "Boolean": "INTEGER", "String": "TEXT"}


def find_migration_bug(prompt: str, code: str) -> int:
    """Проверки Room: версия, путь миграции, совпадение колонки с сущностью, таблица."""
    lines = code.split("\n")
    old_v = int(re.search(r"базой Room версии (\d+)", prompt)[1])
    table = re.search(r'tableName = "(\w+)"', code)[1]
    for n, ln in enumerate(lines, 1):
        if (m := re.search(r"version = (\d+)\)", ln)) and int(m[1]) != old_v + 1:
            return n
        if m := re.search(r"val (MIGRATION_\d+_\d+) = object : Migration\((\d+), (\d+)\)", ln):
            mig_name = m[1]
            if (int(m[2]), int(m[3])) != (old_v, old_v + 1):
                return n
        if m := re.search(r'ALTER TABLE (\w+) ADD COLUMN (\w+) ([^"]+)"', ln):
            if m[1] != table:
                return n
            field_type = re.search(rf"val {m[2]}: (\w+\??)", code)[1]
            nullable = field_type.endswith("?")
            sql = m[3]
            if not sql.startswith(_SQL_TYPE[field_type.rstrip("?")]):
                return n
            if nullable == ("NOT NULL" in sql):
                return n  # nullability колонки не совпадает с полем сущности
            if "NOT NULL" in sql and "DEFAULT" not in sql:
                return n  # SQLite не добавит NOT NULL-колонку без DEFAULT
        regs = re.search(r"\.addMigrations\((.*)\)", ln)
        if regs and mig_name not in [x.strip() for x in regs[1].split(",")]:
            return n
    raise AssertionError("ошибка не найдена")


def test_room_migration_independent():
    t = storage.ROOM_MIGRATION
    for seed in SEEDS:
        inst = t.generate(seed)
        assert find_migration_bug(inst.public.prompt, inst.public.code) == inst.key, (
            seed,
            inst.public.code,
        )


# --------------------------------------------------------------------------- сеть


def _retry_params(code: str) -> tuple[int, int, int, float]:
    def get(name):
        return re.search(rf"{name}: \w+ = ([\d.]+)", code)[1]

    return int(get("times")), int(get("initialDelay")), int(get("maxDelay")), float(get("factor"))


def _retry_answer_from_delays(prompt: str, delays: list[int]) -> int:
    if m := re.search(r"после (\d+)-й неудачной", prompt):
        return delays[int(m[1]) - 1]
    return sum(delays)


@pytest.mark.skipif(shutil.which("node") is None, reason="node не установлен")
def test_retry_backoff_matches_node():
    t = network.RETRY_BACKOFF
    for seed in range(40):
        inst = t.generate(seed)
        times, initial, max_delay, factor = _retry_params(inst.public.code)
        js = (
            f"let cur = {initial}; const out = [];"
            f"for (let k = 0; k < {times} - 1; k++) {{ out.push(cur);"
            f" cur = Math.min(Math.trunc(cur * {factor}), {max_delay}); }}"
            "console.log(out.join(' '));"
        )
        res = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
        delays = [int(x) for x in res.stdout.split()]
        assert _retry_answer_from_delays(inst.public.prompt, delays) == inst.key.value


def test_retry_backoff_manual_example():
    # 300 → 450 → 675 → 1012 (675 × 1.5 = 1012.5, toLong() отбрасывает дробь) → потолок 1000
    assert network.backoff_delays(5, 300, 1000, 1.5) == [300, 450, 675, 1000]


def run_http_cache(prompt: str) -> int:
    times = [int(x) for x in re.search(r"в моменты ([\d, ]+) \(", prompt)[1].split(",")]
    m = re.search(r"max-age=(\d+)", prompt)
    max_age = int(m[1]) if m else None
    ch = re.search(r"через (\d+) с после", prompt)
    change = int(ch[1]) if ch else None
    cache = None  # (время ответа, версия)
    net = full = not_mod = 0
    for t in times:
        server_version = int(change is not None and t >= change)
        if cache is not None and max_age is not None and t - cache[0] < max_age:
            continue  # свежий ответ из кэша, в сеть не ходим
        net += 1
        if cache is not None and cache[1] == server_version:
            not_mod += 1
        else:
            full += 1
        cache = (t, server_version)
    if "ответов 304" in prompt:
        return not_mod
    if "ответ 200" in prompt:
        return full
    return net


def test_http_cache_independent():
    t = network.HTTP_CACHE
    for seed in SEEDS:
        inst = t.generate(seed)
        assert run_http_cache(inst.public.prompt) == inst.key.value, (seed, inst.public.prompt)


def test_http_cache_manual_example():
    # RFC 9111: свежий ответ отдаётся из кэша; устаревший ревалидируется (304 освежает кэш)
    st = network.simulate_http_cache([0, 30, 70, 100, 140], max_age=60, change_at=None)
    assert st == {"network": 3, "full": 1, "not_modified": 2, "cache": 2}


# --------------------------------------------------------------------------- производительность


def test_bitmap_independent():
    t = performance.BITMAP_MEMORY
    bpp = {"ARGB_8888": 4, "RGB_565": 2, "RGBA_F16": 8}
    for seed in SEEDS:
        inst = t.generate(seed)
        p = inst.public.prompt
        w, h = map(int, re.search(r"(\d+)×(\d+) пикселей", p).groups())
        s = int(m[1]) if (m := re.search(r"inSampleSize = (\d+)", p)) else 1
        cnt = int(m[1]) if (m := re.search(r"держатся (\d+) таких", p)) else 1
        cfg = re.search(r"Bitmap\.Config\.(\w+)", p)[1]
        mib = (w // s) * (h // s) * bpp[cfg] * cnt / 2**20
        assert check(inst, f"{mib:.1f}"), (seed, p, mib)
        if mib > 3:  # путаница МБ и МиБ не принимается
            assert not check(inst, f"{mib * 1.048576:.1f}")


def _diff_items(block: str) -> list[tuple[int, str, int]]:
    return [(int(a), b, int(c)) for a, b, c in re.findall(r'\w+\((\d+), "(\w+)", (\d+)\)', block)]


def _lcs_pairs(a: list, b: list) -> list[tuple[int, int]]:
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = dp[i + 1][j + 1] + 1 if a[i] == b[j] else max(dp[i + 1][j], dp[i][j + 1])
    pairs, i, j = [], 0, 0
    while i < n and j < m:
        if a[i] == b[j]:
            pairs.append((i, j))
            i, j = i + 1, j + 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return pairs


def test_diffutil_independent():
    t = performance.DIFFUTIL
    for seed in SEEDS:
        inst = t.generate(seed)
        code = inst.public.code
        old = _diff_items(code.split("val oldList")[1].split("val newList")[0])
        new = _diff_items(code.split("val newList")[1])
        by_name = "old.name == new.name" in code
        by_price = "old.price == new.price" in code
        k = 1 if by_name else 0
        pairs = _lcs_pairs([p[k] for p in old], [p[k] for p in new])
        changed = sum(
            1 for i, j in pairs if (old[i][2] != new[j][2] if by_price else old[i] != new[j])
        )
        counts = {
            "вставленные": len(new) - len(pairs),
            "удалённые": len(old) - len(pairs),
            "изменённые": changed,
        }
        what = next(k for k in counts if f"как {k}" in inst.public.prompt)
        assert counts[what] == inst.key.value, (seed, code)


_LEAK_LINES = (
    "AnalyticsTracker.init(this)",
    "GlobalScope.launch",
    "observeForever",
    "LocationRepository.addListener",
    "handler.postDelayed",
)


def test_memory_leak_independent():
    t = performance.MEMORY_LEAK
    for seed in SEEDS:
        inst = t.generate(seed)
        code = inst.public.code
        lines = code.split("\n")
        leaking = []
        for n, ln in enumerate(lines, 1):
            s = ln.strip()
            unremoved = (
                ("observeForever", "removeObserver"),
                ("LocationRepository.addListener", "removeListener"),
                ("handler.postDelayed", "removeCallbacks"),
            )
            strong = s == "AnalyticsTracker.init(this)" or s.startswith("GlobalScope.launch")
            if strong or any(add in s and rm not in code for add, rm in unremoved):
                leaking.append(n)
        assert leaking == [inst.key], (seed, code)


def run_lazy_keys(prompt: str, code: str) -> str:
    items = re.findall(r"«([^»]+)»", prompt.split("; все строки")[0])
    checked = re.search(r"чекбокс у задачи «([^»]+)»", prompt)[1]
    idx = items.index(checked)
    new = list(items)
    if m := re.search(r"удаляют задачу «([^»]+)»", prompt):
        new.remove(m[1])
    else:
        m = re.search(r"на позицию (\d+) \(с нуля\) вставляют задачу «([^»]+)»", prompt)
        new.insert(int(m[1]), m[2])
    keyed = "key = { it }" in code
    if keyed:  # состояние у ключа элемента
        return checked if checked in new else "Ни одна задача не отмечена"
    # без key — состояние у позиции: слот idx показывает тот элемент, что теперь на idx
    return new[idx] if idx < len(new) else "Ни одна задача не отмечена"


def test_lazy_keys_independent():
    t = performance.LAZY_KEYS
    for seed in SEEDS:
        inst = t.generate(seed)
        exp = run_lazy_keys(inst.public.prompt, inst.public.code)
        assert inst.public.options[inst.key] == exp, (seed, inst.public.prompt)


# --------------------------------------------------------------------------- навигация


def run_uinav(code: str) -> str:
    titles = dict(re.findall(r'let (\w+) = screen\("(\w+)"\)', code))
    stack: list[str] = []
    for ln in code.split("\n"):
        if m := re.fullmatch(r"let nav = UINavigationController\(rootViewController: (\w+)\)", ln):
            stack = [m[1]]
        elif m := re.fullmatch(r"nav\.pushViewController\((\w+), animated: false\)", ln):
            assert m[1] not in stack  # один экземпляр дважды пушить нельзя
            stack.append(m[1])
        elif ln == "nav.popViewController(animated: false)":
            if len(stack) > 1:  # корневой экран не снимается
                stack.pop()
        elif ln == "nav.popToRootViewController(animated: false)":
            stack = stack[:1]
        elif m := re.fullmatch(r"nav\.popToViewController\((\w+), animated: false\)", ln):
            stack = stack[: stack.index(m[1]) + 1]
        elif m := re.fullmatch(r"nav\.setViewControllers\(\[(.*)\], animated: false\)", ln):
            stack = [x.strip() for x in m[1].split(",")]
        elif m := re.fullmatch(r"nav\.viewControllers\.remove\(at: (\d+)\)", ln):
            stack.pop(int(m[1]))
    return " ".join(titles[x] for x in stack)


def test_uinav_independent():
    t = navigation.UINAV_STACK
    for seed in SEEDS:
        inst = t.generate(seed)
        assert check(inst, run_uinav(inst.public.code)), (seed, inst.public.code)


def run_nav_compose(code: str) -> str:
    stack = ["home"]

    def pop_to(route: str, inclusive: bool) -> None:
        nonlocal stack
        i = max(k for k, r in enumerate(stack) if r == route)  # ближайший сверху
        stack = stack[: i if inclusive else i + 1]

    for ln in code.split("\n")[1:]:
        if m := re.fullmatch(
            r'navController\.popBackStack\("(\w+)", inclusive = (true|false)\)', ln
        ):
            pop_to(m[1], m[2] == "true")
        elif ln == "navController.popBackStack()":
            stack.pop()
        elif m := re.fullmatch(r'navController\.navigate\("(\w+)"\)( \{ (.*) \})?', ln):
            opts = m[3] or ""
            if p := re.search(r'popUpTo\("(\w+)"\)', opts):
                pop_to(p[1], "inclusive = true" in opts)
            if "launchSingleTop = true" in opts and stack and stack[-1] == m[1]:
                continue
            stack.append(m[1])
        else:
            raise AssertionError(ln)
    return " → ".join(stack)


def test_nav_compose_independent():
    t = navigation.NAV_COMPOSE
    for seed in SEEDS:
        inst = t.generate(seed)
        assert inst.public.options[inst.key] == run_nav_compose(inst.public.code), (
            seed,
            inst.public.code,
        )


def test_nav_compose_manual_example():
    # Документация Navigation: popUpTo("login") { inclusive = true } убирает login из стека
    code = "\n".join(
        [
            "// NavHost",
            'navController.navigate("login")',
            'navController.navigate("profile") { popUpTo("login") { inclusive = true } }',
            'navController.navigate("profile") { launchSingleTop = true }',
        ]
    )
    assert run_nav_compose(code) == "home → profile"


# --------------------------------------------------------------------------- разрешения и релиз

# Dangerous-разрешения по справочнику Manifest.permission (protectionLevel="dangerous").
_DANGEROUS_REFERENCE = {
    "CAMERA",
    "RECORD_AUDIO",
    "ACCESS_FINE_LOCATION",
    "ACCESS_COARSE_LOCATION",
    "READ_CONTACTS",
    "POST_NOTIFICATIONS",
    "READ_MEDIA_IMAGES",
    "READ_CALENDAR",
    "SEND_SMS",
    "CALL_PHONE",
    "BODY_SENSORS",
    "READ_PHONE_STATE",
    "BLUETOOTH_CONNECT",
}


def test_dangerous_permissions_reference():
    t = permissions.DANGEROUS_PERMISSIONS
    for seed in SEEDS:
        inst = t.generate(seed)
        exp = {
            i
            for i, o in enumerate(inst.public.options)
            if o.removeprefix("android.permission.") in _DANGEROUS_REFERENCE
        }
        assert exp == set(inst.key)


def test_runtime_permission_flow():
    t = permissions.RUNTIME_PERMISSIONS
    for seed in SEEDS:
        inst = t.generate(seed)
        p = inst.public.prompt
        ans = inst.public.options[inst.key]
        if "включил разрешение" in p or "нажал «Разрешить»" in p:
            assert ans.startswith("Диалог не покажется") and "true" in ans
        elif "удалил приложение" in p or "один раз" in p or "ни разу" in p:
            assert ans == "Покажется системный диалог запроса разрешения"
        else:  # два отказа на Android 11+ — диалог больше не показывается
            assert "дважды" in p
            assert ans.startswith("Диалог не покажется") and "false" in ans


def test_version_fields():
    t = permissions.VERSION_FIELDS
    for seed in SEEDS:
        inst = t.generate(seed)
        p = inst.public.prompt
        if "has already been used" in p:
            exp = "versionCode"
        elif "начиная с API" in p:
            exp = "minSdk"
        elif "каждый год" in p:
            exp = "targetSdk"
        elif "Google Play версию" in p:
            exp = "versionName"
        elif "номере сборки" in p or ("сборка" in p and "App Store Connect" in p):
            exp = "CFBundleVersion"
        else:
            exp = "CFBundleShortVersionString"
        assert check(inst, exp), (seed, p)
        assert not check(inst, "version")

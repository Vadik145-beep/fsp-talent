"""Mobile / производительность: память под Bitmap, DiffUtil, утечки Activity, ключи LazyColumn."""

from __future__ import annotations

import random

from ...templates import ItemFormat, ItemTemplate, NumericKey, Variant, make_single_choice

# --------------------------------------------------------------------------- память Bitmap

_CONFIGS = (("ARGB_8888", 4), ("ARGB_8888", 4), ("RGB_565", 2), ("RGBA_F16", 8))
_SIZES = (
    (4000, 3000),
    (4032, 3024),
    (3840, 2160),
    (2560, 1440),
    (1920, 1080),
    (1600, 1200),
    (3000, 2000),
    (2048, 1536),
    (1280, 960),
    (6000, 4000),
)


def _gen_bitmap(rng: random.Random) -> Variant:
    w, h = rng.choice(_SIZES)
    if rng.random() < 0.5:
        w, h = h, w
    config, bpp = rng.choice(_CONFIGS)
    sample = rng.choice((1, 1, 2, 4))
    count = rng.choice((1, 1, 2, 3, 5))
    dw, dh = w // sample, h // sample
    total = dw * dh * bpp * count
    mib = total / (1024 * 1024)
    sample_text = (
        f" с BitmapFactory.Options.inSampleSize = {sample}" if sample > 1 else " без уменьшения"
    )
    count_text = (
        f"В памяти одновременно держатся {count} таких Bitmap. Сколько памяти они занимают"
        if count > 1
        else "Сколько памяти займёт этот Bitmap"
    )
    return Variant(
        prompt=(
            f"Фото {w}×{h} пикселей декодируется из файла (BitmapFactory.decodeFile, "
            f"без масштабирования по плотности экрана){sample_text} в конфигурации "
            f"Bitmap.Config.{config}. {count_text}? Ответ в МиБ (1 МиБ = 1 048 576 байт), "
            "округлите до десятых."
        ),
        key=NumericKey(round(mib, 4), tolerance=0.051),
        extra={"platform": "android", "bytes": total},
        explanation=f"{dw}×{dh}×{bpp} байт × {count} = {total} байт ≈ {mib:.2f} МиБ.",
    )


BITMAP_MEMORY = ItemTemplate(
    id="mobile.bitmap_memory",
    specialization="mobile",
    topic="performance",
    target_grade="intern",
    format=ItemFormat.NUMERIC,
    generator=_gen_bitmap,
    a=1.2,
    b=-1.3,
    title="Сколько памяти занимает Bitmap",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- DiffUtil

_PRODUCTS = ("Milk", "Bread", "Cheese", "Apple", "Juice", "Tea", "Coffee", "Eggs", "Rice", "Salt")


def diff_counts(
    old: list[tuple[int, str, int]], new: list[tuple[int, str, int]], same_by: str, content_by: str
) -> dict[str, int]:
    """Счётчики DiffUtil для списков, где общие элементы идут в одном порядке."""

    def ident(p: tuple[int, str, int]) -> object:
        return p[0] if same_by == "id" else p[1]

    def content(p: tuple[int, str, int]) -> object:
        return p if content_by == "all" else p[2]

    old_keys = {ident(p): p for p in old}
    new_keys = {ident(p): p for p in new}
    common = old_keys.keys() & new_keys.keys()
    return {
        "inserted": len(new_keys.keys() - old_keys.keys()),
        "removed": len(old_keys.keys() - new_keys.keys()),
        "changed": sum(1 for k in common if content(old_keys[k]) != content(new_keys[k])),
    }


def _gen_diffutil(rng: random.Random) -> Variant:
    cls = rng.choice(("Product", "CartItem", "Offer"))
    while True:
        same_by = rng.choice(("id", "id", "name"))
        content_by = rng.choice(("all", "all", "price"))
        names = rng.sample(_PRODUCTS, 8)
        n_old = rng.randint(4, 6)
        old = [(i + 1, names[i], rng.choice(range(50, 300, 10))) for i in range(n_old)]
        spare = names[n_old:]
        new: list[tuple[int, str, int]] = []
        next_id = n_old + 1
        for p in old:
            r = rng.random()
            if r < 0.2:
                continue  # удалён
            if r < 0.35:
                new.append((p[0], p[1], p[2] + rng.choice((10, 20, 30))))  # новая цена
            elif r < 0.45 and spare:
                new.append((p[0], spare.pop(), p[2]))  # переименован, id тот же
            else:
                new.append(p)
            if rng.random() < 0.2 and spare:
                new.append((next_id, spare.pop(), rng.choice(range(50, 300, 10))))
                next_id += 1
        if rng.random() < 0.4 and spare:
            new.insert(0, (next_id, spare.pop(), rng.choice(range(50, 300, 10))))
        # идентичность должна быть уникальной, а общие элементы — в прежнем порядке
        idx = 0 if same_by == "id" else 1
        if len({p[idx] for p in new}) != len(new):
            continue
        counts = diff_counts(old, new, same_by, content_by)
        what = rng.choice(("inserted", "removed", "changed"))
        alt = diff_counts(old, new, "id" if same_by == "name" else "name", "all")
        if counts[what] > 0 and (counts != alt or rng.random() < 0.3):
            break
    same_expr = "old.id == new.id" if same_by == "id" else "old.name == new.name"
    content_expr = "old == new" if content_by == "all" else "old.price == new.price"

    def lst(items: list[tuple[int, str, int]]) -> str:
        return ",\n".join(f'    {cls}({i}, "{n}", {p})' for i, n, p in items)

    code = "\n".join(
        [
            f"data class {cls}(val id: Int, val name: String, val price: Int)",
            "",
            f"object {cls}Diff : DiffUtil.ItemCallback<{cls}>() {{",
            f"    override fun areItemsTheSame(old: {cls}, new: {cls}) = {same_expr}",
            f"    override fun areContentsTheSame(old: {cls}, new: {cls}) = {content_expr}",
            "}",
            "",
            "val oldList = listOf(",
            lst(old),
            ")",
            "val newList = listOf(",
            lst(new),
            ")",
            "// adapter.submitList(oldList), дождались отрисовки,",
            "// затем adapter.submitList(newList)",
        ]
    )
    question = {
        "inserted": "Сколько элементов ListAdapter отметит как вставленные (notifyItemInserted)?",
        "removed": "Сколько элементов ListAdapter отметит как удалённые (notifyItemRemoved)?",
        "changed": "Сколько элементов ListAdapter отметит как изменённые (notifyItemChanged) "
        "и перепривяжет через onBindViewHolder?",
    }[what]
    return Variant(
        prompt=(
            f"RecyclerView с ListAdapter и DiffUtil.ItemCallback (код ниже). {question} "
            "Считайте элементы, а не вызовы: соседние элементы могут прийти одним "
            "range-вызовом."
        ),
        key=NumericKey(counts[what]),
        code=code,
        extra={"language": "kotlin", "counts": counts},
        explanation=f"Итог: {counts}. Элементы сопоставляются по areItemsTheSame, "
        "изменёнными считаются сопоставленные с areContentsTheSame = false.",
    )


DIFFUTIL = ItemTemplate(
    id="mobile.diffutil_updates",
    specialization="mobile",
    topic="performance",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_diffutil,
    a=1.2,
    b=0.2,
    title="DiffUtil: вставки, удаления, изменения",
    time_limit_s=210,
)

# --------------------------------------------------------------------------- утечка Activity

# категория: (безопасный вариант, вариант с утечкой); строки — в onCreate; cleanup — отдельно
_LEAK = {
    "tracker": (
        ["AnalyticsTracker.init(applicationContext)"],
        ["AnalyticsTracker.init(this)"],
        [],
    ),
    "scope": (
        ["lifecycleScope.launch {", "    while (true) { delay(1000); tick() }", "}"],
        ["GlobalScope.launch(Dispatchers.Main) {", "    while (true) { delay(1000); tick() }", "}"],
        [],
    ),
    "listener": (
        ["LocationRepository.addListener(locationListener)"],
        ["LocationRepository.addListener(locationListener)"],
        ["LocationRepository.removeListener(locationListener)"],
    ),
    "handler": (
        ["handler.postDelayed({ showPromo() }, 10 * 60 * 1000L)"],
        ["handler.postDelayed({ showPromo() }, 10 * 60 * 1000L)"],
        ["handler.removeCallbacksAndMessages(null)"],
    ),
    "observer": (
        ["UserRepository.user.observe(this) { render(it) }"],
        ["UserRepository.user.observeForever { render(it) }"],
        [],
    ),
}


def _gen_leak(rng: random.Random) -> Variant:
    act = rng.choice(("MainActivity", "PlayerActivity", "MapActivity", "OrderActivity"))
    cats = list(_LEAK)
    bug = rng.choice(cats)
    others = rng.sample([c for c in cats if c != bug], 3)
    blocks: list[tuple[str, list[str], bool]] = []
    cleanup: list[str] = []
    for c in [bug, *others]:
        safe, leaky, clean = _LEAK[c]
        is_bug = c == bug
        blocks.append((c, leaky if is_bug else safe, is_bug))
        if not is_bug:
            cleanup += clean
    rng.shuffle(blocks)
    lines = [
        f"class {act} : AppCompatActivity() {{",
        "    private val handler = Handler(Looper.getMainLooper())",
        "    private val locationListener = LocationListener { loc -> showLocation(loc) }",
        "",
        "    override fun onCreate(savedInstanceState: Bundle?) {",
        "        super.onCreate(savedInstanceState)",
        "        setContentView(R.layout.activity_main)",
    ]
    bug_line = 0
    for _, stmts, is_bug in blocks:
        if is_bug:
            bug_line = len(lines) + 1
        lines += ["        " + s for s in stmts]
    lines += ["    }", ""]
    if cleanup:
        lines += ["    override fun onDestroy() {"]
        lines += ["        " + s for s in cleanup]
        lines += ["        super.onDestroy()", "    }", ""]
    lines += [
        "    private fun tick() { /* обновить таймер на экране */ }",
        "    private fun showPromo() { /* показать баннер */ }",
        "    private fun showLocation(loc: Location) { /* ... */ }",
        "    private fun render(user: User?) { /* ... */ }",
        "}",
    ]
    return Variant(
        prompt=(
            f"LeakCanary сообщает, что {act} не освобождается после onDestroy (пользователь "
            "закрыл экран, процесс жив). AnalyticsTracker, LocationRepository и "
            "UserRepository — синглтоны (object), которые хранят переданные объекты, "
            "пока их не уберут. В какой строке "
            "создаётся ссылка, удерживающая активити? Укажите номер строки."
        ),
        key=bug_line,
        code="\n".join(lines),
        extra={"language": "kotlin", "line_count": len(lines)},
        explanation=f"Утечка: {lines[bug_line - 1].strip()}",
    )


MEMORY_LEAK = ItemTemplate(
    id="mobile.android_memory_leak",
    specialization="mobile",
    topic="performance",
    target_grade="senior",
    format=ItemFormat.FIND_BUG_LINE,
    generator=_gen_leak,
    a=1.3,
    b=1.1,
    title="Где утекает Activity",
    time_limit_s=210,
)

# --------------------------------------------------------------------------- ключи LazyColumn

_TASKS = (
    "Купить молоко",
    "Позвонить маме",
    "Оплатить свет",
    "Сдать отчёт",
    "Записаться к врачу",
    "Забрать посылку",
    "Полить цветы",
    "Продлить полис",
)


def lazy_checked(
    items: list[str], checked: int, change: tuple[str, int], keyed: bool
) -> str | None:
    """Какой элемент окажется отмеченным после изменения списка (None — ни один)."""
    kind, pos = change
    target = items[checked]
    new = list(items)
    if kind == "remove":
        del new[pos]
    else:
        new.insert(pos, "НОВЫЙ")
    if keyed:
        return target if target in new else None
    return new[checked] if checked < len(new) else None


def _gen_lazy_keys(rng: random.Random) -> Variant:
    while True:
        items = rng.sample(_TASKS, rng.randint(4, 6))
        new_item = rng.choice(("Вынести мусор", "Починить кран", "Купить хлеб"))
        checked = rng.randrange(len(items))
        kind = rng.choice(("remove", "remove", "insert"))
        pos = rng.randrange(len(items)) if kind == "remove" else rng.randrange(len(items) + 1)
        keyed = rng.random() < 0.4
        res = lazy_checked(items, checked, (kind, pos), keyed)
        if res == "НОВЫЙ":
            res = new_item
        other = lazy_checked(items, checked, (kind, pos), not keyed)
        if other == "НОВЫЙ":
            other = new_item
        if res != other or rng.random() < 0.25:
            break
    none_text = "Ни одна задача не отмечена"
    correct = res if res is not None else none_text
    new_list = list(items)
    if kind == "remove":
        change_text = f"из списка удаляют задачу «{items[pos]}»"
        del new_list[pos]
    else:
        change_text = f"в список на позицию {pos} (с нуля) вставляют задачу «{new_item}»"
        new_list.insert(pos, new_item)
    distractors = [t for t in new_list if t != correct]
    if correct != none_text:
        distractors.append(none_text)
    items_call = "items(tasks, key = { it }) { title ->" if keyed else "items(tasks) { title ->"
    code = "\n".join(
        [
            "@Composable",
            "fun TaskList(tasks: List<String>) {",
            "    LazyColumn {",
            f"        {items_call}",
            "            var checked by remember { mutableStateOf(false) }",
            "            Row {",
            "                Checkbox(checked = checked, onCheckedChange = { checked = it })",
            "                Text(title)",
            "            }",
            "        }",
            "    }",
            "}",
        ]
    )
    shown = ", ".join(f"«{t}»" for t in items)
    return make_single_choice(
        rng,
        f"Список задач (Jetpack Compose) сейчас: {shown}; все строки помещаются на экране. "
        f"Пользователь отмечает чекбокс у задачи «{items[checked]}». Затем {change_text}, "
        "и TaskList рекомпонуется с новым списком. У какой задачи на экране будет "
        "отмеченный чекбокс?",
        correct,
        distractors,
        code=code,
        extra={"language": "kotlin"},
        explanation="Без key состояние remember привязано к позиции в LazyColumn, "
        "с key — к ключу элемента.",
    )


LAZY_KEYS = ItemTemplate(
    id="mobile.compose_lazy_keys",
    specialization="mobile",
    topic="performance",
    target_grade="senior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_lazy_keys,
    a=1.4,
    b=1.5,
    title="Состояние элементов LazyColumn и key",
    time_limit_s=180,
)

TEMPLATES = (BITMAP_MEMORY, DIFFUTIL, MEMORY_LEAK, LAZY_KEYS)

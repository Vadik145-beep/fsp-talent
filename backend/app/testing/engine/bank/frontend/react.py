"""Frontend / React 18: выбор хука, батчинг setState, ключи списков, React.memo,
порядок эффектов и cleanup.

Код задач — готовые компоненты (JSX, `export default function App`). Тест, если рядом
установлены react@18, react-dom@18, jsdom и sucrase, рендерит их по-настоящему и сверяет ключ.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ...templates import ItemFormat, ItemTemplate, NumericKey, Variant, make_ordering

_REACT_NOTE = "React 18, StrictMode выключен."

# --------------------------------------------------------------------------- выбор хука

_COMPONENTS = ("SearchBox", "ProductCard", "ChatWindow", "Profile", "Gallery", "Checkout")


def _hook_scenarios(comp: str, rng: random.Random) -> list[tuple[str, list[str], tuple[str, ...]]]:
    """(описание, строки кода с пропуском ____, допустимые ответы)."""
    item = rng.choice(("items", "products", "messages", "users", "orders"))
    query = rng.choice(("query", "filter", "search", "term"))
    ms = rng.choice((300, 500, 1000, 2000))
    return [
        (
            f"В {comp} нужно хранить id таймера между рендерами; изменение этого значения "
            "не должно вызывать перерисовку.",
            ["const timerRef = ____(null);", f"timerRef.current = setTimeout(save, {ms});"],
            ("useRef",),
        ),
        (
            f"В {comp} нужно получить доступ к DOM-элементу поля ввода, чтобы вызвать focus().",
            ["const inputRef = ____(null);", "// ...", "<input ref={inputRef} />"],
            ("useRef",),
        ),
        (
            f"В {comp} нужно загрузить {item} с сервера после первого рендера.",
            [
                "____(() => {",
                f"  fetch('/api/{item}').then((r) => r.json()).then(set{item.title()});",
                "}, []);",
            ],
            ("useEffect",),
        ),
        (
            f"В {comp} отфильтрованный список {item} нужно пересчитывать только при "
            f"изменении {item} или {query}, а не на каждом рендере.",
            [
                "const visible = ____(",
                f"  () => {item}.filter((x) => x.name.includes({query})),",
                f"  [{item}, {query}],",
                ");",
            ],
            ("useMemo",),
        ),
        (
            f"{comp} передаёт обработчик в дочерний компонент, обёрнутый в React.memo; "
            "ссылка на функцию не должна меняться между рендерами.",
            [
                "const handleSelect = ____(",
                "  (id) => setSelectedId(id),",
                "  [],",
                ");",
                "<List onSelect={handleSelect} />",
            ],
            ("useCallback",),
        ),
        (
            f"{comp} должен прочитать текущую тему из ThemeContext, созданного через "
            "createContext.",
            ["const theme = ____(ThemeContext);"],
            ("useContext",),
        ),
        (
            f"В {comp} нужно измерить высоту блока и поправить позицию подсказки до того, как "
            "браузер отрисует кадр, чтобы не было мигания.",
            [
                "____(() => {",
                "  const { height } = boxRef.current.getBoundingClientRect();",
                "  setTop(height + 8);",
                "}, []);",
            ],
            ("useLayoutEffect",),
        ),
        (
            f"В {comp} нужно получить стабильный уникальный id для связки <label htmlFor> и "
            "<input id>, одинаковый при серверном и клиентском рендере.",
            ["const id = ____();", "<label htmlFor={id}>Email</label>", "<input id={id} />"],
            ("useId",),
        ),
        (
            f"Состояние формы в {comp} сложное, переходы удобно описать функцией "
            "(state, action) => newState.",
            ["const [state, dispatch] = ____(formReducer, initialState);"],
            ("useReducer",),
        ),
    ]


def _gen_hook_choice(rng: random.Random) -> Variant:
    comp = rng.choice(_COMPONENTS)
    text, code_lines, answers = rng.choice(_hook_scenarios(comp, rng))
    keys = tuple(dict.fromkeys([*answers, *(f"React.{a}" for a in answers)]))
    return Variant(
        prompt=(
            f"{text} Какой встроенный хук React нужно подставить вместо ____? "
            "Ответ — имя хука, например useState."
        ),
        key=keys,
        code="\n".join(code_lines),
        extra={"language": "jsx"},
        explanation=f"Ответ: {answers[0]}.",
    )


REACT_HOOK_CHOICE = ItemTemplate(
    id="frontend.react_hook_choice",
    specialization="frontend",
    topic="react",
    target_grade="intern",
    format=ItemFormat.SHORT_TEXT,
    generator=_gen_hook_choice,
    a=1.1,
    b=-1.3,
    title="Какой хук React нужен",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- батчинг setState

_STATE_NAMES = (("count", "setCount"), ("score", "setScore"), ("total", "setTotal"))


def _gen_batching(rng: random.Random) -> Variant:
    var, setter = rng.choice(_STATE_NAMES)
    start = rng.randint(0, 10)
    while True:
        n_ops = rng.randint(3, 4)
        ops: list[tuple[bool, str, int]] = []  # (функциональный?, операция, k)
        for _ in range(n_ops):
            op = "+" if rng.random() < 0.8 else "*"
            k = rng.randint(1, 5) if op == "+" else 2
            ops.append((rng.random() < 0.5, op, k))
        if any(f for f, _, _ in ops) and not all(f for f, _, _ in ops):
            break
    clicks = rng.choice((1, 1, 2))
    value = start
    for _ in range(clicks):
        snap = value
        for functional, op, k in ops:
            base = value if functional else snap
            value = base + k if op == "+" else base * k
    body = []
    for functional, op, k in ops:
        if functional:
            body.append(f"    {setter}((prev) => prev {op} {k});")
        else:
            body.append(f"    {setter}({var} {op} {k});")
    code = "\n".join(
        [
            "import { useState } from 'react';",
            "",
            "export default function App() {",
            f"  const [{var}, {setter}] = useState({start});",
            "",
            "  function handleClick() {",
            *body,
            "  }",
            "",
            f"  return <button onClick={{handleClick}}>{{{var}}}</button>;",
            "}",
        ]
    )
    times = "один раз" if clicks == 1 else "два раза (второй — после перерисовки)"
    return Variant(
        prompt=f"{_REACT_NOTE} Пользователь нажал на кнопку {times}. Какое число будет на кнопке?",
        key=NumericKey(value),
        code=code,
        extra={"language": "jsx"},
        explanation=(
            f"{var} внутри обработчика — снимок с последнего рендера; функциональное обновление "
            f"получает актуальное значение из очереди. Ответ {value}."
        ),
    )


REACT_BATCHING = ItemTemplate(
    id="frontend.react_state_batching",
    specialization="frontend",
    topic="react",
    target_grade="junior",
    format=ItemFormat.NUMERIC,
    generator=_gen_batching,
    a=1.5,
    b=-0.1,
    title="Несколько setState подряд и функциональное обновление",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- ключи списков

_NAMES = ("Ann", "Bob", "Cid", "Dan", "Eva", "Fay", "Gus", "Ida", "Kim", "Lev")
_TYPED = ("red", "blue", "tea", "milk", "cat", "dog", "sun", "sky", "oak", "elm")


def _gen_list_keys(rng: random.Random) -> Variant:
    n = rng.randint(3, 4)
    while True:
        names = rng.sample(_NAMES, n)
        if names != sorted(names):
            break
    ids = rng.sample(range(1, 50), n)
    typed = rng.sample(_TYPED, n)
    items = list(zip(ids, names, typed, strict=True))
    action = rng.choice(("first", "by_id", "by_id", "reverse", "sort"))
    if action == "first":
        expr = "items.slice(1)"
        new = items[1:]
    elif action == "by_id":
        victim = items[rng.randrange(n - 1)]
        expr = f"items.filter((it) => it.id !== {victim[0]})"
        new = [it for it in items if it != victim]
    elif action == "reverse":
        expr = "[...items].reverse()"
        new = items[::-1]
    else:
        expr = "[...items].sort((a, b) => a.name.localeCompare(b.name))"
        new = sorted(items, key=lambda it: it[1])
    key_kind = rng.choice(("index", "index", "index", "id", "name"))
    key_expr = {"index": "index", "id": "item.id", "name": "item.name"}[key_kind]
    if key_kind == "index":
        shown = [f"{it[1]}={items[j][2]}" for j, it in enumerate(new)]
    else:
        shown = [f"{it[1]}={it[2]}" for it in new]
    init = ",\n".join(f"  {{ id: {i}, name: '{nm}' }}" for i, nm, _ in items)
    code = "\n".join(
        [
            "import { useState } from 'react';",
            "",
            f"const INITIAL = [\n{init},\n];",
            "",
            "export default function App() {",
            "  const [items, setItems] = useState(INITIAL);",
            "  return (",
            "    <div>",
            f"      <button onClick={{() => setItems({expr})}}>Изменить</button>",
            "      {items.map((item, index) => (",
            f"        <p key={{{key_expr}}}>",
            "          {item.name}: <input />",
            "        </p>",
            "      ))}",
            "    </div>",
            "  );",
            "}",
        ]
    )
    typed_desc = ", ".join(f"{nm} — «{t}»" for _, nm, t in items)
    return Variant(
        prompt=(
            f"{_REACT_NOTE} Пользователь ввёл текст в поля по порядку: {typed_desc}. Затем "
            "нажал «Изменить». Что будет показано в строках сверху вниз? Ответ — пары "
            "Имя=текст_в_поле через пробел, например Ann=red Bob=blue."
        ),
        key=" ".join(shown),
        code=code,
        extra={"language": "jsx"},
        explanation=(
            "С key={index} React сопоставляет строки по позиции: DOM-поля ввода (и введённый "
            "текст) остаются на местах, меняются только подписи. Со стабильным ключом поле "
            "переезжает вместе с элементом."
        ),
    )


REACT_LIST_KEYS = ItemTemplate(
    id="frontend.react_list_keys",
    specialization="frontend",
    topic="react",
    target_grade="middle",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_list_keys,
    a=1.5,
    b=0.7,
    title="Ключи списков и состояние DOM",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- React.memo


@dataclass(frozen=True)
class _Prop:
    jsx: str  # атрибут в JSX
    hook: str | None  # строка хука в App
    kind: str  # stable | every | once | unstable


def _memo_props(rng: random.Random, threshold: int) -> list[_Prop]:
    color = rng.choice(("red", "teal", "navy", "gray"))
    title = rng.choice(("Корзина", "Профиль", "Заказы", "Итого"))
    return [
        _Prop(f'title="{title}"', None, "stable"),
        _Prop("value={count}", None, "every"),
        _Prop("even={count % 2 === 0}", None, "every"),
        _Prop(f"big={{count >= {threshold}}}", None, "once"),
        _Prop(f"style={{{{ color: '{color}' }}}}", None, "unstable"),
        _Prop("onPick={() => setCount(0)}", None, "unstable"),
        _Prop(
            "onPick={handlePick}",
            "const handlePick = useCallback(() => setCount(0), []);",
            "stable",
        ),
        _Prop(
            "onPick={handlePick}",
            "const handlePick = useCallback(() => console.log(count), [count]);",
            "every",
        ),
        _Prop(
            "style={style}",
            f"const style = useMemo(() => ({{ color: '{color}' }}), []);",
            "stable",
        ),
        _Prop("items={[1, 2, 3]}", None, "unstable"),
    ]


def _gen_memo(rng: random.Random) -> Variant:
    clicks = rng.randint(2, 5)
    threshold = rng.randint(1, clicks + 1)
    while True:
        pool = _memo_props(rng, threshold)
        chosen = rng.sample(pool, rng.randint(1, 3))
        attrs = [p.jsx.split("=")[0] for p in chosen]
        if len(set(attrs)) == len(attrs):
            break
    memo = rng.random() < 0.8
    if not memo or any(p.kind in ("every", "unstable") for p in chosen):
        renders = 1 + clicks
    elif any(p.kind == "once" for p in chosen):
        renders = 1 + (1 if threshold <= clicks else 0)
    else:
        renders = 1
    hooks = [p.hook for p in chosen if p.hook]
    imports = ["useState"]
    if memo:
        imports.insert(0, "memo")
    if any("useCallback" in h for h in hooks):
        imports.append("useCallback")
    if any("useMemo" in h for h in hooks):
        imports.append("useMemo")
    params = ", ".join(sorted(set(attrs)))
    child = (
        [f"const Child = memo(function Child({{ {params} }}) {{"]
        if memo
        else [f"function Child({{ {params} }}) {{"]
    )
    child += [
        "  console.log('render Child');",
        "  return <div>child</div>;",
        "});" if memo else "}",
    ]
    code = "\n".join(
        [
            f"import {{ {', '.join(imports)} }} from 'react';",
            "",
            *child,
            "",
            "export default function App() {",
            "  const [count, setCount] = useState(0);",
            *(f"  {h}" for h in hooks),
            "  return (",
            "    <>",
            "      <button onClick={() => setCount(count + 1)}>+1</button>",
            f"      <Child {' '.join(p.jsx for p in chosen)} />",
            "    </>",
            "  );",
            "}",
        ]
    )
    return Variant(
        prompt=(
            f"{_REACT_NOTE} Пользователь нажал «+1» {clicks} {'раза' if clicks < 5 else 'раз'} "
            "подряд. Сколько раз всего "
            "в консоли появится 'render Child', включая первый рендер?"
        ),
        key=NumericKey(renders),
        code=code,
        extra={"language": "jsx"},
        explanation=(
            "memo пропускает рендер, только если все пропсы равны по Object.is; новый объект, "
            "массив или стрелочная функция на каждом рендере ломают мемоизацию. "
            f"Ответ {renders}."
        ),
    )


REACT_MEMO = ItemTemplate(
    id="frontend.react_memo_renders",
    specialization="frontend",
    topic="react",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_memo,
    a=1.4,
    b=0.9,
    title="Сколько раз отрендерится компонент в React.memo",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- порядок эффектов


@dataclass(frozen=True)
class _Comp:
    name: str
    log_render: bool
    layout: str | None  # None | "count" | "once" — зависимости [count] или []
    effect: str | None


def _effect_logs(comps: list[_Comp], scenario: str) -> list[str]:
    """comps[0] — App (родитель), остальные — его дети по порядку. Модель React 18."""
    pre = comps  # прямой порядок: родитель, затем дети
    post = [*comps[1:], comps[0]]  # обратный: дети, затем родитель
    out = [f"render {c.name}" for c in pre if c.log_render]
    if scenario == "mount":
        out += [f"layout {c.name}" for c in post if c.layout]
        out += [f"effect {c.name}" for c in post if c.effect]
        return out
    out += [f"cleanup layout {c.name}" for c in post if c.layout == "count"]
    out += [f"layout {c.name}" for c in post if c.layout == "count"]
    out += [f"cleanup effect {c.name}" for c in post if c.effect == "count"]
    out += [f"effect {c.name}" for c in post if c.effect == "count"]
    return out


def _comp_body(c: _Comp, ret: str, indent: str = "  ") -> list[str]:
    lines = []
    if c.log_render:
        lines.append(f"{indent}console.log('render {c.name}');")
    for hook, deps, label in (
        ("useLayoutEffect", c.layout, "layout"),
        ("useEffect", c.effect, "effect"),
    ):
        if deps is None:
            continue
        dep_list = "[count]" if deps == "count" else "[]"
        lines += [
            f"{indent}{hook}(() => {{",
            f"{indent}  console.log('{label} {c.name}');",
            f"{indent}  return () => console.log('cleanup {label} {c.name}');",
            f"{indent}}}, {dep_list});",
        ]
    lines.append(f"{indent}return {ret};")
    return lines


def _gen_effect_order(rng: random.Random) -> Variant:
    child_names = rng.sample(("Header", "List", "Footer", "Sidebar", "Avatar", "Badge"), 2)
    while True:
        scenario = rng.choice(("mount", "update", "update"))
        n_children = rng.choice((1, 2))
        comps: list[_Comp] = []
        for name in ["App", *child_names[:n_children]]:
            comps.append(
                _Comp(
                    name=name,
                    log_render=rng.random() < 0.5,
                    layout=rng.choice((None, "count", "once")),
                    effect=rng.choice(("count", "count", "once", None)),
                )
            )
        logs = _effect_logs(comps, scenario)
        if 4 <= len(logs) <= 7 and any(x.startswith(("layout", "cleanup layout")) for x in logs):
            break
    imports = sorted(
        {"useState"}
        | {"useEffect" for c in comps if c.effect}
        | {"useLayoutEffect" for c in comps if c.layout}
    )
    lines = [f"import {{ {', '.join(imports)} }} from 'react';", ""]
    for c in comps[1:]:
        lines.append(f"function {c.name}({{ count }}) {{")
        lines += _comp_body(c, "<p>{count}</p>")
        lines += ["}", ""]
    app = comps[0]
    kids = " ".join(f"<{c.name} count={{count}} />" for c in comps[1:])
    lines.append("export default function App() {")
    lines.append("  const [count, setCount] = useState(0);")
    lines += _comp_body(
        app,
        f"(\n    <div>\n      <button onClick={{() => setCount(count + 1)}}>+1</button>\n"
        f"      {kids}\n    </div>\n  )",
    )
    lines.append("}")
    when = (
        "при первом монтировании App"
        if scenario == "mount"
        else "после одного клика по «+1» (первое монтирование уже прошло, консоль очищена)"
    )
    return make_ordering(
        rng,
        f"{_REACT_NOTE} Расставьте сообщения, которые появятся в консоли {when}, в порядке "
        "появления.",
        logs,
        code="\n".join(lines),
        extra={"language": "jsx"},
        explanation=(
            "Рендер идёт сверху вниз; эффекты — снизу вверх (сначала дети). Все cleanup "
            "useLayoutEffect, затем все useLayoutEffect; потом все cleanup useEffect, затем "
            "все useEffect. Эффекты с [] при обновлении не перезапускаются."
        ),
    )


REACT_EFFECT_ORDER = ItemTemplate(
    id="frontend.react_effect_order",
    specialization="frontend",
    topic="react",
    target_grade="senior",
    format=ItemFormat.ORDERING,
    generator=_gen_effect_order,
    a=1.6,
    b=1.6,
    title="Порядок рендера, эффектов и cleanup",
    time_limit_s=270,
)

TEMPLATES = (REACT_HOOK_CHOICE, REACT_BATCHING, REACT_LIST_KEYS, REACT_MEMO, REACT_EFFECT_ORDER)

"""Mobile / навигация: стек UINavigationController, back stack Navigation Compose (popUpTo)."""

from __future__ import annotations

import random

from ...templates import ItemFormat, ItemTemplate, Variant, make_single_choice

# --------------------------------------------------------------------------- UINavigationController

_SCREENS = ("Home", "Catalog", "Product", "Cart", "Checkout", "Profile", "Orders", "Search")

NavOp = tuple[str, str]  # ("push", X) | ("pop", "") | ("root", "") | ("popto", X) | ("set", "A,B")


def simulate_uinav(root: str, ops: list[NavOp]) -> list[str]:
    stack = [root]
    for op, arg in ops:
        if op == "push":
            stack.append(arg)
        elif op == "pop":
            if len(stack) > 1:
                stack.pop()
        elif op == "root":
            del stack[1:]
        elif op == "popto":
            del stack[stack.index(arg) + 1 :]
        elif op == "set":
            stack = arg.split(",")
        else:  # remove — удалить экран по индексу через viewControllers.remove(at:)
            del stack[int(arg)]
    return stack


def _gen_uinav(rng: random.Random) -> Variant:
    while True:
        names = rng.sample(_SCREENS, 6)
        root = names[0]
        pool = names[1:]
        stack = [root]
        ops: list[NavOp] = []
        lines: list[str] = []
        for _ in range(rng.randint(5, 7)):
            free = [x for x in pool if x not in stack]
            r = rng.random()
            if (r < 0.45 or len(stack) == 1) and free:
                x = rng.choice(free)
                ops.append(("push", x))
                lines.append(f"nav.pushViewController({x.lower()}, animated: false)")
            elif r < 0.6:
                ops.append(("pop", ""))
                lines.append("nav.popViewController(animated: false)")
            elif r < 0.7:
                ops.append(("root", ""))
                lines.append("nav.popToRootViewController(animated: false)")
            elif r < 0.85 and len(stack) > 2:
                x = rng.choice(stack[:-1])
                ops.append(("popto", x))
                lines.append(f"nav.popToViewController({x.lower()}, animated: false)")
            elif r < 0.93:
                k = rng.randint(1, 3)
                new = rng.sample(names, k)
                ops.append(("set", ",".join(new)))
                arr = ", ".join(x.lower() for x in new)
                lines.append(f"nav.setViewControllers([{arr}], animated: false)")
            elif len(stack) > 2:
                i = rng.randrange(1, len(stack) - 1)
                ops.append(("remove", str(i)))
                lines.append(f"nav.viewControllers.remove(at: {i})")
            else:
                continue
            stack = simulate_uinav(root, ops)
        if len(ops) >= 4 and any(op in ("pop", "popto", "root", "remove") for op, _ in ops):
            break
    decl = [f'let {x.lower()} = screen("{x}")' for x in names]
    code = "\n".join(
        [
            "func screen(_ title: String) -> UIViewController {",
            "    let vc = UIViewController()",
            "    vc.title = title",
            "    return vc",
            "}",
            "",
            *decl,
            f"let nav = UINavigationController(rootViewController: {root.lower()})",
            *lines,
            'print(nav.viewControllers.compactMap { $0.title }.joined(separator: " "))',
        ]
    )
    return Variant(
        prompt=(
            "Что напечатает код (iOS 17, UIKit)? Перечислите заголовки экранов через пробел "
            "в порядке, в котором их печатает print."
        ),
        key=" ".join(stack),
        code=code,
        extra={"language": "swift"},
        explanation="viewControllers — стек снизу вверх; popViewController не снимает корневой "
        "экран; popToViewController оставляет указанный экран на вершине.",
    )


UINAV_STACK = ItemTemplate(
    id="mobile.ios_navigation_stack",
    specialization="mobile",
    topic="navigation",
    target_grade="junior",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_uinav,
    a=1.2,
    b=-0.6,
    title="Стек UINavigationController",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- Navigation Compose

_ROUTES = ("home", "catalog", "product", "cart", "checkout", "login", "profile", "orders")

# ("nav", X, popUpTo|None, inclusive, singleTop) | ("back", "", None, False, False)
# | ("backto", Y, None, inclusive, False)
NavCmd = tuple[str, str, str | None, bool, bool]


def simulate_nav(start: str, cmds: list[NavCmd], model: str = "correct") -> list[str]:
    """Back stack (снизу вверх). model — модель с типичной ошибкой для дистракторов."""
    stack = [start]
    for kind, x, up_to, inclusive, single_top in cmds:
        if model == "flip_inclusive":
            inclusive = not inclusive
        if kind == "back":
            stack.pop()
        elif kind == "backto":
            i = len(stack) - 1 - stack[::-1].index(x)
            del stack[i if inclusive else i + 1 :]
        else:
            if up_to is not None and model != "ignore_popupto":
                i = len(stack) - 1 - stack[::-1].index(up_to)
                del stack[i if inclusive else i + 1 :]
            if single_top and model != "ignore_single_top" and stack and stack[-1] == x:
                continue
            stack.append(x)
    return stack


def _render_cmd(c: NavCmd) -> str:
    kind, x, up_to, inclusive, single_top = c
    if kind == "back":
        return "navController.popBackStack()"
    if kind == "backto":
        return f'navController.popBackStack("{x}", inclusive = {str(inclusive).lower()})'
    if up_to is None and not single_top:
        return f'navController.navigate("{x}")'
    if single_top:
        return f'navController.navigate("{x}") {{ launchSingleTop = true }}'
    if inclusive:
        return f'navController.navigate("{x}") {{ popUpTo("{up_to}") {{ inclusive = true }} }}'
    return f'navController.navigate("{x}") {{ popUpTo("{up_to}") }}'


def _gen_nav_compose(rng: random.Random) -> Variant:
    while True:
        routes = rng.sample(_ROUTES[1:], 5)
        start = "home"
        cmds: list[NavCmd] = []
        stack = [start]
        for _ in range(rng.randint(4, 6)):
            r = rng.random()
            if r < 0.3 or len(stack) < 2:
                cmds.append(("nav", rng.choice(routes), None, False, False))
            elif r < 0.6:
                cmds.append(
                    ("nav", rng.choice(routes), rng.choice(stack), rng.random() < 0.5, False)
                )
            elif r < 0.75:
                cmds.append(("nav", rng.choice([stack[-1], *routes]), None, False, True))
            elif r < 0.85 and len(stack) > 2:
                cmds.append(("back", "", None, False, False))
            elif len(stack) > 2:
                y = rng.choice(stack[1:])
                cmds.append(("backto", y, None, rng.random() < 0.5, False))
            else:
                cmds.append(("nav", rng.choice(routes), None, False, False))
            stack = simulate_nav(start, cmds)
            if not stack:
                break
        if not stack:
            continue
        wrong: set[str] = set()
        for model in ("flip_inclusive", "ignore_popupto", "ignore_single_top"):
            try:
                alt = simulate_nav(start, cmds, model)
            except (ValueError, IndexError):
                continue
            if alt and alt != stack:
                wrong.add(" → ".join(alt))
        if len(wrong) >= 2:
            break
    correct = " → ".join(stack)
    extra_wrong: list[str] = []
    if len(stack) > 1:
        extra_wrong.append(" → ".join(stack[:-1]))
    extra_wrong.append(" → ".join([*stack, stack[-1]]))
    if stack[0] != start:
        extra_wrong.append(" → ".join([start, *stack]))
    distractors = [w for w in [*sorted(wrong), *extra_wrong] if w != correct]
    code = "\n".join(
        [
            '// NavHost(navController, startDestination = "home") { ... все маршруты ... }',
            *[_render_cmd(c) for c in cmds],
        ]
    )
    return make_single_choice(
        rng,
        "Navigation Compose 2.7. Приложение только что открылось на стартовом экране "
        "«home». Затем по очереди выполняются вызовы ниже. Что окажется в back stack "
        "(снизу вверх, без самого графа)?",
        correct,
        distractors,
        code=code,
        extra={"language": "kotlin"},
        explanation="popUpTo снимает экраны над указанным (inclusive = true — и его самого) "
        "до перехода; launchSingleTop не добавляет копию, если экран уже на вершине.",
    )


NAV_COMPOSE = ItemTemplate(
    id="mobile.nav_popupto_backstack",
    specialization="mobile",
    topic="navigation",
    target_grade="middle",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_nav_compose,
    a=1.3,
    b=0.4,
    title="Back stack Navigation: popUpTo и launchSingleTop",
    time_limit_s=210,
)

TEMPLATES = (UINAV_STACK, NAV_COMPOSE)

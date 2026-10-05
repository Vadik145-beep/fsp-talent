"""Mobile / жизненный цикл: UIViewController и сцены iOS, launchMode Android, что переживает
поворот и смерть процесса (ViewModel, onSaveInstanceState).

Порядок колбэков Activity/Fragment уже есть в примерах (mobile.android_lifecycle) —
здесь его не дублируем.
"""

from __future__ import annotations

import random

from ...templates import ItemFormat, ItemTemplate, NumericKey, Variant, make_ordering

# --------------------------------------------------------------------------- iOS: колбэки

_VCS = (
    "FeedViewController",
    "ProfileViewController",
    "CartViewController",
    "SettingsViewController",
    "DetailsViewController",
    "ChatViewController",
)


def _ios_scenarios(a: str, b: str) -> list[tuple[str, str, list[str]]]:
    """(описание, чьи колбэки, порядок)."""
    return [
        (
            f"{a} лежит в UINavigationController. На него пушат новый экземпляр {b} "
            f"(pushViewController), затем пользователь нажимает «Назад», и {b} освобождается.",
            f"{b}",
            [
                "viewDidLoad()",
                "viewWillAppear(_:)",
                "viewDidAppear(_:)",
                "viewWillDisappear(_:)",
                "viewDidDisappear(_:)",
                "deinit",
            ],
        ),
        (
            f"{a} — корневой экран UINavigationController и уже на экране. На него пушат {b}, "
            "затем пользователь возвращается назад.",
            f"{a}",
            [
                "viewWillDisappear(_:)",
                "viewDidDisappear(_:)",
                "viewWillAppear(_:)",
                "viewDidAppear(_:)",
            ],
        ),
        (
            f"{a} на экране. Он показывает {b} модально с modalPresentationStyle = .fullScreen, "
            f"затем {b} закрывается через dismiss(animated:).",
            f"{a}",
            [
                "viewWillDisappear(_:)",
                "viewDidDisappear(_:)",
                "viewWillAppear(_:)",
                "viewDidAppear(_:)",
            ],
        ),
        (
            f"{b} создаётся в коде через init() (без storyboard) и пушится в стек навигации.",
            f"{b}",
            ["init()", "loadView()", "viewDidLoad()", "viewWillAppear(_:)", "viewDidAppear(_:)"],
        ),
        (
            f"{a} показывает {b} модально (стиль по умолчанию, iOS 15), затем пользователь "
            f"смахивает {b} вниз, и он закрывается.",
            f"{b}",
            [
                "viewDidLoad()",
                "viewWillAppear(_:)",
                "viewDidAppear(_:)",
                "viewWillDisappear(_:)",
                "viewDidDisappear(_:)",
            ],
        ),
        (
            "Приложение использует сцены (UIScene, iOS 13+). Пользователь запускает его "
            "с нуля (холодный старт).",
            "AppDelegate и SceneDelegate",
            [
                "application(_:didFinishLaunchingWithOptions:)",
                "scene(_:willConnectTo:options:)",
                "sceneWillEnterForeground(_:)",
                "sceneDidBecomeActive(_:)",
            ],
        ),
        (
            "Приложение использует сцены (UIScene, iOS 13+) и активно. Пользователь уходит "
            "на домашний экран, а через минуту снова открывает приложение.",
            "SceneDelegate",
            [
                "sceneWillResignActive(_:)",
                "sceneDidEnterBackground(_:)",
                "sceneWillEnterForeground(_:)",
                "sceneDidBecomeActive(_:)",
            ],
        ),
        (
            "Приложение без сцен (только AppDelegate). Пользователь запускает его с нуля, "
            "затем уходит на домашний экран.",
            "AppDelegate",
            [
                "application(_:willFinishLaunchingWithOptions:)",
                "application(_:didFinishLaunchingWithOptions:)",
                "applicationDidBecomeActive(_:)",
                "applicationWillResignActive(_:)",
                "applicationDidEnterBackground(_:)",
            ],
        ),
        (
            "Приложение без сцен (только AppDelegate) свёрнуто в фон. Пользователь возвращается "
            "в него, а затем ему поступает входящий звонок поверх приложения.",
            "AppDelegate",
            [
                "applicationWillEnterForeground(_:)",
                "applicationDidBecomeActive(_:)",
                "applicationWillResignActive(_:)",
            ],
        ),
    ]


def _gen_ios_lifecycle(rng: random.Random) -> Variant:
    a, b = rng.sample(_VCS, 2)
    text, whose, steps = rng.choice(_ios_scenarios(a, b))
    return make_ordering(
        rng,
        f"{text}\nРасставьте вызовы ({whose}) в порядке, в котором их делает UIKit.",
        steps,
        extra={"platform": "ios"},
        explanation="Порядок по документации UIKit: " + " → ".join(steps),
    )


IOS_LIFECYCLE = ItemTemplate(
    id="mobile.ios_lifecycle_order",
    specialization="mobile",
    topic="app_lifecycle",
    target_grade="junior",
    format=ItemFormat.ORDERING,
    generator=_gen_ios_lifecycle,
    a=1.1,
    b=-0.8,
    title="Жизненный цикл UIViewController и сцены iOS",
    time_limit_s=150,
)

# --------------------------------------------------------------------------- launchMode

_ACTS = ("Main", "List", "Details", "Cart", "Profile", "Settings")
_MODES = ("standard", "singleTop", "singleTask")


def simulate_launch_modes(modes: dict[str, str], actions: list[tuple[str, str]]) -> list[str]:
    """Стек одной задачи (снизу вверх). actions: ("start", X) | ("back", "")."""
    stack = ["Main"]
    for act, target in actions:
        if act == "back":
            stack.pop()
            continue
        mode = modes[target]
        if mode == "singleTop" and stack[-1] == target:
            continue
        if mode == "singleTask" and target in stack:
            del stack[stack.index(target) + 1 :]
            continue
        stack.append(target)
    return stack


def _gen_launch_mode(rng: random.Random) -> Variant:
    while True:
        acts = rng.sample(_ACTS[1:], 3)
        modes = {"Main": "standard"}
        for x in acts:
            modes[x] = rng.choice(_MODES)
        if len(set(modes[x] for x in acts)) < 2:
            continue
        actions: list[tuple[str, str]] = []
        stack_len = 1
        for _ in range(rng.randint(5, 8)):
            if stack_len > 2 and rng.random() < 0.2:
                actions.append(("back", ""))
            else:
                actions.append(
                    ("start", rng.choice([*acts, "Main"] if rng.random() < 0.15 else acts))
                )
            stack_len = len(simulate_launch_modes(modes, actions))
        stack = simulate_launch_modes(modes, actions)
        naive = 1 + sum(1 if a == "start" else -1 for a, _ in actions)
        ask = rng.choice(("total", "total", "one"))
        if ask == "one":
            who = rng.choice(acts)
            value = stack.count(who)
            naive_value = sum(1 for a, t in actions if a == "start" and t == who)
        else:
            who = ""
            value = len(stack)
            naive_value = naive
        if value != naive_value and len(actions) >= 5:
            break
    manifest = [
        f'<activity android:name=".{x}Activity" android:launchMode="{modes[x]}" />'
        for x in ["Main", *acts]
    ]
    steps = []
    for i, (act, target) in enumerate(actions, 1):
        if act == "back":
            steps.append(f"{i}. Пользователь нажимает «Назад».")
        else:
            steps.append(
                f"{i}. Активити на вершине стека вызывает startActivity для {target}Activity."
            )
    question = (
        "Сколько всего экземпляров активити будет в стеке задачи после последнего шага?"
        if ask == "total"
        else f"Сколько экземпляров {who}Activity будет в стеке задачи после последнего шага?"
    )
    return Variant(
        prompt=(
            "Приложение (Android 13) запущено с иконки: в задаче одна MainActivity. "
            "Все активити в одной задаче (taskAffinity по умолчанию), флаги Intent не "
            "используются.\n" + "\n".join(steps) + "\n" + question
        ),
        key=NumericKey(value),
        code="\n".join(manifest),
        extra={"language": "xml", "stack": list(stack)},
        explanation="Итоговый стек (снизу вверх): " + " → ".join(f"{x}Activity" for x in stack),
    )


LAUNCH_MODE = ItemTemplate(
    id="mobile.android_launch_mode_stack",
    specialization="mobile",
    topic="app_lifecycle",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_launch_mode,
    a=1.3,
    b=0.5,
    title="launchMode и back stack задачи",
    time_limit_s=210,
)

# ------------------------------------------------------------- поворот и смерть процесса

_EVENTS = {
    "rotate": "пользователь поворачивает экран",
    "theme": "пользователь меняет тему системы, пока экран открыт (уведомление в шторке)",
    "home": "пользователь нажимает Home",
    "return": "пользователь возвращается в приложение через список недавних",
    "kill": "система убивает процесс приложения в фоне из-за нехватки памяти",
    "return_after_kill": "пользователь возвращается в приложение через список недавних",
    "back": "пользователь нажимает «Назад» (DetailsActivity закрывается)",
    "reopen": "пользователь снова открывает DetailsActivity из MainActivity",
}

_COUNTERS = {
    "create": "DetailsActivity.onCreate()",
    "destroy": "DetailsActivity.onDestroy()",
    "vm_init": "блок init во DetailsViewModel",
    "cleared": "DetailsViewModel.onCleared()",
    "save": "DetailsActivity.onSaveInstanceState()",
}


def count_lifecycle(events: list[str]) -> dict[str, int]:
    """Счётчики после открытия DetailsActivity и последовательности событий (Android 13)."""
    c = {"create": 1, "destroy": 0, "vm_init": 1, "cleared": 0, "save": 0}
    for e in events:
        if e in ("rotate", "theme"):
            c["save"] += 1
            c["destroy"] += 1
            c["create"] += 1
        elif e == "home":
            c["save"] += 1  # с Android 9 вызывается после onStop
        elif e == "return_after_kill":
            c["create"] += 1
            c["vm_init"] += 1
        elif e == "back":
            c["destroy"] += 1
            c["cleared"] += 1
        elif e == "reopen":
            c["create"] += 1
            c["vm_init"] += 1
    return c


def _random_events(rng: random.Random) -> list[str]:
    events: list[str] = []
    state = "fg"  # fg | bg | killed | closed
    for _ in range(rng.randint(4, 7)):
        if state == "fg":
            e = rng.choice(("rotate", "rotate", "theme", "home", "home", "back"))
        elif state == "bg":
            e = rng.choice(("return", "return", "kill"))
        elif state == "killed":
            e = "return_after_kill"
        else:
            e = "reopen"
        events.append(e)
        state = {
            "home": "bg",
            "kill": "killed",
            "back": "closed",
        }.get(e, "fg")
    while state != "fg":
        e = {"bg": "return", "killed": "return_after_kill", "closed": "reopen"}[state]
        events.append(e)
        state = "fg"
    return events


def _gen_lifecycle_counts(rng: random.Random) -> Variant:
    while True:
        events = _random_events(rng)
        counts = count_lifecycle(events)
        what = rng.choice(list(_COUNTERS))
        # интересно, только если ответ отличается от «по одному на каждое событие»
        if counts[what] not in (0, len(events)) or what in ("vm_init", "cleared"):
            break
    steps = "\n".join(
        f"{i}. {_EVENTS[e][0].upper()}{_EVENTS[e][1:]}." for i, e in enumerate(events, 1)
    )
    return Variant(
        prompt=(
            "Android 13, targetSdk 33. MainActivity открывает DetailsActivity; у DetailsActivity "
            "есть DetailsViewModel (by viewModels()), configChanges в манифесте не заданы. "
            "Считаем вызовы, начиная с открытия DetailsActivity (его тоже считаем). "
            f"Дальше по порядку:\n{steps}\n"
            f"Сколько раз всего будет вызван {_COUNTERS[what]}?"
        ),
        key=NumericKey(counts[what]),
        extra={"platform": "android", "events": list(events)},
        explanation=(
            "ViewModel переживает смену конфигурации, но не закрытие экрана и не смерть "
            "процесса; onCleared при убийстве процесса не вызывается; onSaveInstanceState "
            f"вызывается при повороте и уходе в фон. Счётчики: {counts}"
        ),
    )


LIFECYCLE_COUNTS = ItemTemplate(
    id="mobile.android_config_change_counts",
    specialization="mobile",
    topic="app_lifecycle",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_lifecycle_counts,
    a=1.3,
    b=0.8,
    title="Поворот экрана, ViewModel и смерть процесса",
    time_limit_s=210,
)

TEMPLATES = (IOS_LIFECYCLE, LAUNCH_MODE, LIFECYCLE_COUNTS)

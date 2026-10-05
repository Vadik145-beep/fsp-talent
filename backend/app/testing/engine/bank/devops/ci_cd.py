"""DevOps — CI/CD: порядок стадий пайплайна, semver, стратегии выкладки."""

from __future__ import annotations

import random

from ...templates import ItemFormat, ItemTemplate, Variant, make_ordering, make_single_choice

# --------------------------------------------------------------------------- стадии пайплайна

_STACK_CMDS = (
    ("npm ci", "npm run lint && npm test"),
    ("pip install -r requirements.txt", "ruff check . && pytest"),
    ("go mod download", "go vet ./... && go test ./..."),
    ("mvn -q dependency:go-offline", "mvn -q verify"),
)


def _gen_pipeline(rng: random.Random) -> Variant:
    install, test = rng.choice(_STACK_CMDS)
    app = rng.choice(("orders-api", "web-shop", "billing", "notifier"))
    reg = rng.choice(("registry.gitlab.com/team", "ghcr.io/team", "cr.yandex/crp1"))
    tool = rng.choice(("helm upgrade --install", "kubectl apply -k", "argocd app sync"))
    steps = [
        "Получить код коммита (checkout)",
        f"Установить зависимости: {install}",
        f"Линтер и модульные тесты: {test}",
        f"Собрать Docker-образ {app} с тегом коммита",
        f"Отправить образ в реестр {reg}",
        f"Выкатить образ на staging: {tool}",
        "Прогнать сквозные (e2e) тесты на staging",
        "После ручного подтверждения выкатить тот же образ в прод",
    ]
    if rng.random() < 0.4:
        steps = steps[:6] + steps[7:]  # без e2e
    return make_ordering(
        rng,
        f"Расставьте стадии CI/CD-пайплайна сервиса {app} в правильном порядке.",
        steps,
        explanation=" → ".join(steps),
    )


PIPELINE = ItemTemplate(
    id="devops.pipeline_order",
    specialization="devops",
    topic="ci_cd",
    target_grade="intern",
    format=ItemFormat.ORDERING,
    generator=_gen_pipeline,
    a=1.0,
    b=-1.5,
    title="Порядок стадий CI/CD",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- semver


def bump(version: tuple[int, int, int], kind: str) -> tuple[int, int, int]:
    major, minor, patch = version
    if kind == "major":
        return major + 1, 0, 0
    if kind == "minor":
        return major, minor + 1, 0
    return major, minor, patch + 1


def _gen_semver(rng: random.Random) -> Variant:
    v = (rng.randint(1, 9), rng.randint(0, 25), rng.randint(0, 30))
    lib = rng.choice(("payments-sdk", "auth-client", "pdf-render", "geo-utils"))
    changes = {
        "patch": [
            "исправлена ошибка округления в расчёте суммы",
            "исправлена утечка памяти при повторном подключении",
            "обновлён текст сообщения об ошибке",
        ],
        "minor": [
            "добавлен новый необязательный параметр timeout, старые вызовы работают как раньше",
            "добавлен новый метод export_csv()",
        ],
        "major": [
            "удалён устаревший метод get_all(), вместо него list()",
            "параметр amount теперь обязательный и принимает копейки вместо рублей",
        ],
    }
    kinds = rng.sample(["patch", "minor", "major"], rng.randint(1, 2))
    rank = {"patch": 0, "minor": 1, "major": 2}
    top = max(kinds, key=lambda k: rank[k])
    items = [rng.choice(changes[k]) for k in kinds]
    new = bump(v, top)
    old_s, new_s = ".".join(map(str, v)), ".".join(map(str, new))
    return Variant(
        prompt=(
            f"Библиотека {lib} версии {old_s} следует Semantic Versioning. В новый релиз вошло: "
            + "; ".join(items)
            + ". Какой номер версии у релиза? Ответ в формате X.Y.Z."
        ),
        key=(new_s, "v" + new_s),
        extra={"answer_type": "text", "max_length": 16},
        explanation=f"Самое крупное изменение — {top}: {new_s}",
    )


SEMVER = ItemTemplate(
    id="devops.semver_bump",
    specialization="devops",
    topic="ci_cd",
    target_grade="intern",
    format=ItemFormat.SHORT_TEXT,
    generator=_gen_semver,
    a=1.1,
    b=-1.2,
    title="Следующая версия по SemVer",
    time_limit_s=90,
)

# --------------------------------------------------------------------------- стратегии выкладки

_STRATEGIES = {
    "recreate": "Recreate: остановить все старые экземпляры, затем запустить новые",
    "rolling": "Rolling update: постепенно заменять экземпляры по несколько штук",
    "blue_green": "Blue-green: поднять полную копию новой версии и переключить весь трафик",
    "canary": "Canary: отправить новой версии малую долю трафика и следить за метриками",
    "feature_flag": "Feature flag: выкатить код выключенным и включать функцию по флагу",
}


def _gen_strategy(rng: random.Random) -> Variant:
    pct = rng.choice((1, 2, 5, 10))
    sec = rng.choice((5, 10, 30))
    team = rng.choice(("маркетинга", "продаж", "поддержки"))
    scenarios = [
        (
            f"Новая версия меняет схему БД несовместимо со старой, две версии не могут работать "
            f"одновременно, а простой в {rng.randint(2, 15)} минут ночью допустим.",
            "recreate",
        ),
        (
            f"Нужно проверить новую версию на {pct}% реальных пользователей и автоматически "
            "откатиться, если вырастет доля ошибок.",
            "canary",
        ),
        (
            f"Нужно переключиться на новую версию целиком за {sec} с и так же быстро вернуться "
            "назад; ресурсов хватает на два полных окружения.",
            "blue_green",
        ),
        (
            "Обычный релиз stateless-сервиса из 12 реплик без простоя и без лишних ресурсов на "
            "второе окружение.",
            "rolling",
        ),
        (
            f"Код новой функции уже в проде, но включить её нужно в день запуска по команде отдела "
            f"{team}, без нового деплоя.",
            "feature_flag",
        ),
    ]
    text, correct = rng.choice(scenarios)
    return make_single_choice(
        rng,
        f"{text}\nКакую стратегию выкладки выбрать?",
        _STRATEGIES[correct],
        [v for k, v in _STRATEGIES.items() if k != correct],
        explanation=f"Верно: {_STRATEGIES[correct]}",
    )


STRATEGIES = ItemTemplate(
    id="devops.deploy_strategies",
    specialization="devops",
    topic="ci_cd",
    target_grade="junior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_strategy,
    a=1.1,
    b=-0.6,
    title="Стратегия выкладки под задачу",
    time_limit_s=120,
)

TEMPLATES = [PIPELINE, SEMVER, STRATEGIES]

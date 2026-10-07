"""Словарь тем для «тестов из вакансий» (T4.8).

Тема — то, что разумно проверить по тексту вакансии: ключевые слова, к какой теме справочника
(`data/seed/topics.json`) она относится, какие темы банка задач (`bank_registry()`) её
покрывают и заготовка черновика, если шаблонов в банке нет.

Темы банка (`ItemTemplate.topic`, короткие: `sql`, `kubernetes`) и темы справочника
(`backend.databases`) — разные уровни; `BANK_TO_CATALOG` связывает их (нужно для поля
`items.topic`, у которого внешний ключ на справочник).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# (специализация, тема банка) → тема справочника
BANK_TO_CATALOG: dict[tuple[str, str], str] = {
    ("backend", "algorithms"): "backend.algorithms",
    ("backend", "caching_queues"): "backend.architecture",
    ("backend", "concurrency"): "backend.concurrency",
    ("backend", "distributed_systems"): "backend.architecture",
    ("backend", "http_api"): "backend.http_api",
    ("backend", "python"): "backend.algorithms",
    ("backend", "security"): "backend.security",
    ("backend", "sql"): "backend.databases",
    ("frontend", "accessibility"): "frontend.css_layout",
    ("frontend", "browser_network"): "frontend.browser",
    ("frontend", "css"): "frontend.css_layout",
    ("frontend", "dom_events"): "frontend.browser",
    ("frontend", "javascript"): "frontend.js_core",
    ("frontend", "javascript_async"): "frontend.js_core",
    ("frontend", "react"): "frontend.react",
    ("frontend", "typescript"): "frontend.typescript",
    ("frontend", "web_security"): "frontend.browser",
    ("mobile", "android_lifecycle"): "mobile.lifecycle",
    ("mobile", "app_lifecycle"): "mobile.lifecycle",
    ("mobile", "concurrency"): "mobile.language",
    ("mobile", "data_storage"): "mobile.networking",
    ("mobile", "kotlin"): "mobile.language",
    ("mobile", "navigation"): "mobile.ui",
    ("mobile", "networking_offline"): "mobile.networking",
    ("mobile", "performance"): "mobile.ui",
    ("mobile", "publishing_permissions"): "mobile.release",
    ("mobile", "swift"): "mobile.language",
    ("data_ml", "classic_ml"): "data_ml.ml_basics",
    ("data_ml", "deep_learning"): "data_ml.deep_learning",
    ("data_ml", "metrics"): "data_ml.metrics",
    ("data_ml", "mlops"): "data_ml.ml_basics",
    ("data_ml", "model_validation"): "data_ml.metrics",
    ("data_ml", "pandas_numpy"): "data_ml.sql_data",
    ("data_ml", "preprocessing"): "data_ml.sql_data",
    ("data_ml", "statistics"): "data_ml.statistics",
    ("qa", "api_testing"): "qa.api_testing",
    ("qa", "automation"): "qa.automation",
    ("qa", "bug_reports"): "qa.process",
    ("qa", "performance"): "qa.performance",
    ("qa", "security"): "qa.api_testing",
    ("qa", "sql"): "qa.api_testing",
    ("qa", "test_design"): "qa.test_design",
    ("qa", "test_management"): "qa.process",
    ("devops", "bash"): "devops.linux",
    ("devops", "ci_cd"): "devops.ci_cd",
    ("devops", "containers"): "devops.containers",
    ("devops", "iac"): "devops.iac",
    ("devops", "incidents"): "devops.monitoring",
    ("devops", "kubernetes"): "devops.containers",
    ("devops", "linux"): "devops.linux",
    ("devops", "monitoring"): "devops.monitoring",
    ("devops", "networking"): "devops.linux",
}


def catalog_topic_of(spec: str, bank_topic: str) -> str:
    """Тема справочника для шаблона банка; незнакомая пара → первая тема специализации."""
    fallback = {
        "backend": "backend.architecture",
        "frontend": "frontend.js_core",
        "mobile": "mobile.language",
        "data_ml": "data_ml.ml_basics",
        "qa": "qa.process",
        "devops": "devops.linux",
    }
    return BANK_TO_CATALOG.get((spec, bank_topic), fallback.get(spec, "backend.architecture"))


@dataclass(frozen=True)
class DraftSeed:
    """Заготовка черновика шаблона (режим без LLM)."""

    title: str
    format: str  # ItemFormat контракта
    prompt: str


@dataclass(frozen=True)
class VacancyTopic:
    id: str
    label: str
    specs: tuple[str, ...]  # для каких специализаций тема уместна (первая — «своя»)
    keywords: tuple[str, ...]  # регулярные выражения, регистр не важен
    bank: tuple[tuple[str, str], ...] = ()  # (специализация, тема банка)
    catalog: dict[str, str] = field(default_factory=dict)  # специализация → тема справочника
    draft: DraftSeed | None = None

    def catalog_topic(self, spec: str) -> str:
        if spec in self.catalog:
            return self.catalog[spec]
        if self.bank:
            return catalog_topic_of(*self.bank[0])
        return next(iter(self.catalog.values()))


_W = r"(?<![a-zа-яё])"  # начало слова
_E = r"(?![a-zа-яё])"  # конец слова


def _t(
    id_: str,
    label: str,
    specs: tuple[str, ...],
    keywords: tuple[str, ...],
    bank: tuple[tuple[str, str], ...] = (),
    catalog: dict[str, str] | None = None,
    draft: DraftSeed | None = None,
) -> VacancyTopic:
    return VacancyTopic(id_, label, specs, keywords, bank, catalog or {}, draft)


GIT_CATALOG = {
    "backend": "backend.architecture",
    "frontend": "frontend.testing",
    "mobile": "mobile.release",
    "data_ml": "data_ml.ml_basics",
    "qa": "qa.process",
    "devops": "devops.ci_cd",
}

TOPICS: tuple[VacancyTopic, ...] = (
    # ------------------------------------------------------------ backend
    _t(
        "backend.go",
        "Язык Go",
        ("backend", "devops"),
        (rf"{_W}go{_E}", rf"{_W}golang", r"горутин"),
        catalog={"backend": "backend.concurrency", "devops": "devops.linux"},
        draft=DraftSeed(
            "Что выведет программа с горутинами и WaitGroup",
            "code_output",
            "Дана программа на Go: в цикле запускаются 3 горутины, каждая увеличивает общий "
            "счётчик под sync.Mutex, main ждёт их через sync.WaitGroup и печатает счётчик. "
            "Что будет выведено и что изменится, если убрать Mutex?",
        ),
    ),
    _t(
        "backend.java",
        "Java и Spring",
        ("backend",),
        (rf"{_W}java{_E}", rf"{_W}spring", rf"{_W}jvm{_E}"),
        catalog={"backend": "backend.architecture"},
        draft=DraftSeed(
            "Область видимости бина в Spring",
            "single_choice",
            "В Spring-приложении сервис объявлен с @Service без указания scope и хранит "
            "счётчик запросов в поле. Что произойдёт при параллельных запросах от разных "
            "пользователей?",
        ),
    ),
    _t(
        "backend.python",
        "Язык Python",
        ("backend", "data_ml", "qa"),
        (rf"{_W}python", rf"{_W}django", rf"{_W}fastapi", rf"{_W}flask"),
        bank=(("backend", "python"),),
    ),
    _t(
        "backend.http_api",
        "HTTP и REST API",
        ("backend", "frontend", "mobile", "qa"),
        (rf"{_W}rest{_E}", rf"{_W}http", rf"{_W}api{_E}", r"эндпоинт", r"openapi|swagger"),
        bank=(("backend", "http_api"),),
    ),
    _t(
        "backend.grpc",
        "gRPC и контракты API",
        ("backend",),
        (rf"{_W}grpc", r"protobuf", r"контракт\w*"),
        catalog={"backend": "backend.http_api"},
        draft=DraftSeed(
            "Обратная совместимость protobuf-схемы",
            "single_choice",
            "В сообщение gRPC-сервиса нужно добавить поле и убрать устаревшее. Какое изменение "
            ".proto-схемы сохранит совместимость со старыми клиентами: переиспользовать номер "
            "удалённого поля, пометить его reserved и добавить новое с новым номером, "
            "поменять тип существующего поля или переименовать сообщение?",
        ),
    ),
    _t(
        "backend.databases",
        "Базы данных и SQL",
        ("backend",),
        (
            r"postgres\w*",
            rf"{_W}mysql",
            rf"{_W}sql{_E}",
            r"транзакц\w*",
            r"изоляц\w*",
            r"индекс\w*",
            r"план\w* запрос\w*",
        ),
        bank=(("backend", "sql"),),
    ),
    _t(
        "backend.concurrency",
        "Конкурентность и асинхронность",
        ("backend",),
        (
            r"конкурентн\w*",
            r"горутин\w*",
            rf"{_W}канал\w*",
            rf"{_W}context{_E}",
            r"гонк\w* данных",
            r"асинхрон\w*",
            r"многопоточ\w*",
        ),
        bank=(("backend", "concurrency"),),
    ),
    _t(
        "backend.message_queues",
        "Очереди и брокеры сообщений",
        ("backend", "data_ml"),
        (
            rf"{_W}kafka",
            rf"{_W}rabbitmq",
            r"брокер\w*",
            r"очеред\w*",
            r"не потеря\w*",
            r"задво\w*",
            r"идемпотент\w*",
        ),
        bank=(("backend", "caching_queues"), ("backend", "distributed_systems")),
    ),
    _t(
        "backend.caching",
        "Кэширование",
        ("backend",),
        (rf"{_W}redis", r"кэш\w*", r"кеш\w*", r"memcached"),
        bank=(("backend", "caching_queues"),),
    ),
    _t(
        "backend.distributed",
        "Распределённые системы",
        ("backend",),
        (r"микросервис\w*", r"распредел[её]нн\w*", rf"{_W}saga", r"outbox", r"отказоустойчив\w*"),
        bank=(("backend", "distributed_systems"),),
    ),
    _t(
        "backend.algorithms",
        "Алгоритмы и структуры данных",
        ("backend",),
        (r"алгоритм\w*", r"структур\w* данных", r"сложност\w* алгоритм"),
        bank=(("backend", "algorithms"),),
    ),
    _t(
        "backend.security",
        "Безопасность веб-приложений",
        ("backend",),
        (rf"{_W}oauth", rf"{_W}jwt", r"безопасн\w*", r"owasp", r"инъекц\w*", r"аутентификац\w*"),
        bank=(("backend", "security"),),
    ),
    # ------------------------------------------------------------ frontend
    _t(
        "frontend.react",
        "React и хуки",
        ("frontend",),
        (rf"{_W}react(?! native)", r"хук\w*", r"компонент\w*"),
        bank=(("frontend", "react"),),
    ),
    _t(
        "frontend.typescript",
        "TypeScript",
        ("frontend",),
        (r"typescript",),
        bank=(("frontend", "typescript"),),
    ),
    _t(
        "frontend.js_core",
        "JavaScript и event loop",
        ("frontend",),
        (r"javascript", r"замыкан\w*", r"промис\w*|promise", r"event loop"),
        bank=(("frontend", "javascript"), ("frontend", "javascript_async")),
    ),
    _t(
        "frontend.css_layout",
        "HTML, CSS и адаптивная вёрстка",
        ("frontend",),
        (rf"{_W}html", rf"{_W}css", r"в[её]рстк\w*", r"адаптивн\w*", r"flexbox"),
        bank=(("frontend", "css"),),
    ),
    _t(
        "frontend.browser",
        "Браузер: рендеринг и производительность",
        ("frontend",),
        (r"браузер\w*", r"рендеринг\w*", r"скорост\w* загрузки", r"производительност\w*"),
        bank=(("frontend", "browser_network"), ("frontend", "dom_events")),
    ),
    _t(
        "frontend.state",
        "Управление состоянием (Redux)",
        ("frontend",),
        (rf"{_W}redux", rf"{_W}mobx", r"стейт-менеджер\w*", r"состояни\w*"),
        catalog={"frontend": "frontend.react"},
        draft=DraftSeed(
            "Иммутабельное обновление в Redux Toolkit",
            "single_choice",
            "В слайсе Redux Toolkit редьюсер addItem делает state.items.push(item). Почему это "
            "работает в createSlice, но сломает обычный редьюсер без Immer, и какой вариант "
            "корректен вне createSlice?",
        ),
    ),
    _t(
        "frontend.testing",
        "Тестирование фронтенда",
        ("frontend",),
        (rf"{_W}jest", r"testing library", r"unit-тест\w*", rf"{_W}e2e", r"cypress"),
        catalog={"frontend": "frontend.testing"},
        draft=DraftSeed(
            "Поиск элемента в React Testing Library",
            "single_choice",
            "Кнопка «Купить» появляется после асинхронной загрузки товара. Какой запрос React "
            "Testing Library правильно дождётся её: getByText, queryByText, findByRole или "
            "getAllByTestId — и почему?",
        ),
    ),
    _t(
        "frontend.accessibility",
        "Доступность интерфейса",
        ("frontend",),
        (r"доступност\w* интерфейс\w*", rf"{_W}a11y", rf"{_W}aria"),
        bank=(("frontend", "accessibility"),),
    ),
    # ------------------------------------------------------------ mobile
    _t(
        "mobile.kotlin",
        "Kotlin: основы и null-safety",
        ("mobile", "backend"),
        (rf"{_W}kotlin(?! coroutines)", r"null-safety", r"лямбд\w*", r"коллекци\w*"),
        bank=(("mobile", "kotlin"),),
    ),
    _t(
        "mobile.swift",
        "Swift",
        ("mobile",),
        (rf"{_W}swift(?!ui)",),
        bank=(("mobile", "swift"),),
    ),
    _t(
        "mobile.lifecycle",
        "Жизненный цикл Activity/Fragment",
        ("mobile",),
        (r"жизненн\w* цикл\w*", rf"{_W}activity", rf"{_W}fragment", r"lifecycle"),
        bank=(("mobile", "android_lifecycle"), ("mobile", "app_lifecycle")),
    ),
    _t(
        "mobile.compose",
        "Вёрстка экранов (Jetpack Compose / SwiftUI)",
        ("mobile",),
        (r"jetpack compose", rf"{_W}compose", r"swiftui", r"экран\w*", r"макет\w*"),
        catalog={"mobile": "mobile.ui"},
        draft=DraftSeed(
            "Рекомпозиция в Jetpack Compose",
            "single_choice",
            "В @Composable-функции счётчик объявлен как var count = 0, по нажатию кнопки "
            "count++, но текст на экране не меняется. Почему, и как правильно хранить "
            "состояние (remember + mutableStateOf, rememberSaveable)?",
        ),
    ),
    _t(
        "mobile.networking",
        "Работа с сетью и REST API",
        ("mobile",),
        (r"rest api", r"retrofit", r"okhttp", r"офлайн\w*"),
        bank=(("mobile", "networking_offline"),),
    ),
    _t(
        "mobile.storage",
        "Хранение данных на устройстве",
        ("mobile",),
        (rf"{_W}room{_E}", r"sqlite", r"core data", r"хранени\w* данных"),
        bank=(("mobile", "data_storage"),),
    ),
    _t(
        "mobile.concurrency",
        "Корутины и многопоточность",
        ("mobile",),
        (r"coroutines", r"корутин\w*", rf"{_W}flow{_E}", r"многопоточ\w*"),
        bank=(("mobile", "concurrency"),),
    ),
    _t(
        "mobile.release",
        "Сборка и публикация",
        ("mobile",),
        (r"google play", r"app store", r"rustore", r"публикац\w*"),
        bank=(("mobile", "publishing_permissions"),),
    ),
    # ------------------------------------------------------------ data / ml
    _t(
        "data_ml.statistics",
        "Статистика и A/B-тесты",
        ("data_ml",),
        (r"статистик\w*", r"a/b", r"гипотез\w*", r"p-value", r"доверительн\w*"),
        bank=(("data_ml", "statistics"),),
    ),
    _t(
        "data_ml.classic_ml",
        "Классическое ML (scikit-learn)",
        ("data_ml",),
        (r"scikit-learn|sklearn", r"классическ\w* ml", r"бустинг\w*", r"регресси\w*"),
        bank=(("data_ml", "classic_ml"), ("data_ml", "model_validation")),
    ),
    _t(
        "data_ml.validation",
        "Валидация моделей и переобучение",
        ("data_ml",),
        (r"валидац\w*", r"переобучен\w*", r"обучающ\w* выборк\w*"),
        bank=(("data_ml", "model_validation"),),
    ),
    _t(
        "data_ml.deep_learning",
        "Нейросети (PyTorch)",
        ("data_ml",),
        (r"pytorch", r"tensorflow", r"нейросет\w*", r"эмбеддинг\w*", r"глубок\w* обучени\w*"),
        bank=(("data_ml", "deep_learning"),),
    ),
    _t(
        "data_ml.sql",
        "SQL: оконные функции и JOIN",
        ("data_ml", "qa"),
        (rf"{_W}sql{_E}", r"оконн\w* функц\w*", rf"{_W}join"),
        bank=(("backend", "sql"), ("qa", "sql")),
        catalog={"data_ml": "data_ml.sql_data", "qa": "qa.api_testing"},
    ),
    _t(
        "data_ml.pandas",
        "Обработка данных (pandas)",
        ("data_ml",),
        (r"pandas", r"numpy", r"признак\w*"),
        bank=(("data_ml", "pandas_numpy"), ("data_ml", "preprocessing")),
    ),
    _t(
        "data_ml.metrics",
        "Метрики качества и ранжирования",
        ("data_ml",),
        (r"метрик\w*", r"precision", r"recall", rf"{_W}roc", rf"{_W}ndcg", rf"{_W}auc{_E}"),
        bank=(("data_ml", "metrics"),),
    ),
    _t(
        "data_ml.recsys",
        "Рекомендательные системы",
        ("data_ml",),
        (r"рекомендац\w*", r"рекомендательн\w*", r"коллаборативн\w*", r"ранжировани\w*"),
        catalog={"data_ml": "data_ml.ml_basics"},
        draft=DraftSeed(
            "Метрика precision@k для выдачи рекомендаций",
            "numeric",
            "Модель показала пользователю 5 книг, из них понравились 2-я и 4-я; всего у "
            "пользователя 3 релевантные книги. Посчитайте precision@5 и recall@5 и объясните, "
            "почему для ленты рекомендаций важнее nDCG.",
        ),
    ),
    _t(
        "data_ml.mlops",
        "Вывод моделей в прод (MLOps)",
        ("data_ml",),
        (r"mlflow", r"airflow", r"в прод\w*", r"деплой модел\w*", r"дрейф\w*"),
        bank=(("data_ml", "mlops"),),
    ),
    # ------------------------------------------------------------ qa
    _t(
        "qa.test_design",
        "Тест-дизайн",
        ("qa",),
        (r"тест-дизайн\w*", r"тест-кейс\w*", r"граничн\w*", r"эквивалентн\w*", r"чек-лист\w*"),
        bank=(("qa", "test_design"),),
    ),
    _t(
        "qa.automation",
        "Автоматизация тестирования",
        ("qa",),
        (r"автотест\w*", r"автоматизац\w*", r"selenium", r"playwright", r"pytest", r"page object"),
        bank=(("qa", "automation"),),
    ),
    _t(
        "qa.api_testing",
        "Тестирование API",
        ("qa",),
        (r"postman", rf"{_W}api{_E}", rf"{_W}rest{_E}", r"swagger"),
        bank=(("qa", "api_testing"),),
    ),
    _t(
        "qa.process",
        "Баг-репорты и процессы",
        ("qa",),
        (r"баг\w*", rf"{_W}jira", r"testrail", r"дефект\w*"),
        bank=(("qa", "bug_reports"), ("qa", "test_management")),
    ),
    _t(
        "qa.performance",
        "Нагрузочное тестирование",
        ("qa",),
        (r"нагрузочн\w*", r"jmeter", rf"{_W}k6{_E}"),
        bank=(("qa", "performance"),),
    ),
    # ------------------------------------------------------------ devops (и смежные)
    _t(
        "devops.linux",
        "Linux: сети, процессы, диагностика",
        ("devops",),
        (r"linux", r"systemd", r"процесс\w*", rf"{_W}сет(?:и|ь|ей|евы\w*){_E}", r"диагностик\w*"),
        bank=(("devops", "linux"), ("devops", "networking"), ("devops", "bash")),
    ),
    _t(
        "devops.containers",
        "Docker и контейнеризация",
        ("devops", "backend", "data_ml"),
        (r"docker", r"контейнер\w*", r"образ\w* контейнер\w*"),
        bank=(("devops", "containers"),),
    ),
    _t(
        "devops.kubernetes",
        "Kubernetes: объекты и отладка",
        ("devops", "backend"),
        (r"kubernetes", rf"{_W}k8s", rf"{_W}helm", rf"{_W}под{_E}\s+упал"),
        bank=(("devops", "kubernetes"),),
        catalog={"devops": "devops.containers", "backend": "devops.containers"},
    ),
    _t(
        "devops.ci_cd",
        "CI/CD",
        ("devops",),
        (r"ci/cd", r"gitlab ci", r"jenkins", r"github actions", r"пайплайн\w*", rf"{_W}деплой\w*"),
        bank=(("devops", "ci_cd"),),
    ),
    _t(
        "devops.monitoring",
        "Мониторинг и инциденты",
        ("devops", "backend"),
        (
            r"мониторинг\w*",
            r"алерт\w*",
            r"prometheus",
            r"grafana",
            r"наблюдаемост\w*",
            r"инцидент\w*",
            r"дежурств\w*",
        ),
        bank=(("devops", "monitoring"), ("devops", "incidents")),
    ),
    _t(
        "devops.iac",
        "Инфраструктура как код (Terraform)",
        ("devops",),
        (r"terraform", r"ansible", rf"{_W}iac{_E}", r"инфраструктур\w* как код"),
        bank=(("devops", "iac"),),
    ),
    # ------------------------------------------------------------ общее
    _t(
        "common.git",
        "Git: ветки и merge request",
        ("mobile", "frontend", "backend", "qa", "data_ml", "devops"),
        (rf"{_W}git(?!lab|hub)(?![a-zа-яё])", r"merge request", r"pull request", r"ветк\w*"),
        catalog=GIT_CATALOG,
        draft=DraftSeed(
            "Слияние ветки с конфликтом",
            "ordering",
            "Ваша ветка feature/payment отстала от main, а в merge request конфликт в одном "
            "файле. Расположите шаги в правильном порядке: git fetch, git rebase origin/main, "
            "исправить конфликт, git add, git rebase --continue, git push --force-with-lease.",
        ),
    ),
)

TOPIC_BY_ID = {t.id: t for t in TOPICS}

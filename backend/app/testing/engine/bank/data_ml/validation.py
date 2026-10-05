"""Data Science / ML — валидация: k-fold, выбор схемы разбиения, утечка данных."""

from __future__ import annotations

import random

from ...templates import ItemFormat, ItemTemplate, NumericKey, Variant, make_single_choice

# --------------------------------------------------------------------------- размеры фолдов


def _gen_kfold(rng: random.Random) -> Variant:
    k = rng.choice((3, 4, 5, 5, 10))
    n = k * rng.randint(20, 400)
    question = rng.choice(("val", "train", "fits", "repeated", "holdout"))
    if question == "val":
        value = n // k
        ask = (
            f"Датасет из {n} строк делят KFold(n_splits={k}). Сколько строк попадает "
            "в валидационную часть каждого фолда?"
        )
    elif question == "train":
        value = n - n // k
        ask = (
            f"Датасет из {n} строк делят KFold(n_splits={k}). На скольких строках обучается "
            "модель в каждом фолде?"
        )
    elif question == "fits":
        value = k
        ask = (
            f"Кросс-валидация KFold(n_splits={k}) на датасете из {n} строк. Сколько раз будет "
            "обучена модель, чтобы получить оценку качества?"
        )
    elif question == "repeated":
        r = rng.choice((2, 3, 5))
        value = k * r
        ask = (
            f"RepeatedKFold(n_splits={k}, n_repeats={r}) на датасете из {n} строк. "
            "Сколько раз будет обучена модель?"
        )
    else:
        test_share = rng.choice((0.1, 0.2, 0.25))
        n = rng.randint(30, 900) * 20
        value = round(n * test_share)
        ask = (
            f"train_test_split(X, y, test_size={test_share}) на датасете из {n} строк. "
            "Сколько строк окажется в тестовой выборке?"
        )
    return Variant(
        prompt=ask,
        key=NumericKey(value, 0),
        extra={"answer_type": "integer"},
        explanation=f"Ответ: {value}.",
    )


KFOLD_SIZES = ItemTemplate(
    id="data_ml.kfold_sizes",
    specialization="data_ml",
    topic="model_validation",
    target_grade="intern",
    format=ItemFormat.NUMERIC,
    generator=_gen_kfold,
    a=1.0,
    b=-1.5,
    title="Размеры частей при кросс-валидации",
    time_limit_s=90,
)

# --------------------------------------------------------------------------- схема разбиения

_S = {
    "group": "GroupKFold: все записи одного {who} — только в одной части",
    "time": "TimeSeriesSplit: обучение на прошлом, проверка на более позднем периоде",
    "strat": "StratifiedKFold: доля классов в каждом фолде как во всём датасете",
    "holdout": "Одно случайное разбиение train/test (hold-out)",
    "loo": "Leave-One-Out или повторённая k-fold кросс-валидация",
    "kfold_shuffle": "KFold(shuffle=True) по строкам без учёта групп и времени",
}


_WHO = (
    ("пациента", "пациентов", "пациентам", "визитов"),
    ("клиента", "клиентов", "клиентам", "покупок"),
    ("пользователя", "пользователей", "пользователям", "сессий"),
    ("магазина", "магазинов", "магазинам", "дней продаж"),
)


def _gen_split(rng: random.Random) -> Variant:
    who, who_pl, who_dat, events = rng.choice(_WHO)
    scenarios = [
        (
            f"Датасет: {rng.randint(3, 40) * 1000} {events} от {rng.randint(300, 2000)} "
            f"{who_pl}, у каждого много записей. Модель будут применять к новым {who_dat}, "
            "которых не было в обучении.",
            "group",
            ["kfold_shuffle", "time", "loo"],
        ),
        (
            f"Прогноз продаж на следующую неделю по истории за {rng.randint(2, 6)} года. "
            "Нужна оценка качества, честная для будущего применения.",
            "time",
            ["kfold_shuffle", "strat", "loo"],
        ),
        (
            f"Классификация отказов: {rng.randint(2000, 9000)} объектов, положительный класс — "
            f"{rng.choice((2, 3, 4, 5))}%, наблюдения независимы, время не важно.",
            "strat",
            ["time", "group", "holdout"],
        ),
        (
            f"Независимые объекты, {rng.randint(3, 9)} млн строк, классы сбалансированы, "
            "одно обучение модели занимает несколько часов.",
            "holdout",
            ["loo", "time", "group"],
        ),
        (
            f"Всего {rng.randint(25, 60)} размеченных образцов (дорогие лабораторные анализы), "
            "объекты независимы, нужна как можно более устойчивая оценка.",
            "loo",
            ["holdout", "time", "group"],
        ),
    ]
    text, correct, wrong = rng.choice(scenarios)
    fmt = {k: v.format(who=who) for k, v in _S.items()}
    return make_single_choice(
        rng,
        f"{text}\nКакую схему валидации выбрать?",
        fmt[correct],
        [fmt[w] for w in wrong],
        explanation=f"Верно: {fmt[correct]}",
    )


SPLIT_STRATEGY = ItemTemplate(
    id="data_ml.split_strategy",
    specialization="data_ml",
    topic="model_validation",
    target_grade="junior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_split,
    a=1.3,
    b=-0.4,
    title="Выбор схемы валидации",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- найди утечку


def _leak_program(rng: random.Random) -> tuple[str, list[str], int]:
    """(симптом, строки кода, индекс строки с утечкой)."""
    xs, y = rng.choice((("X", "y"), ("features", "target"), ("X_all", "y_all")))
    model = rng.choice(
        (
            "LogisticRegression(max_iter=1000)",
            "RandomForestClassifier(n_estimators=300)",
            "GradientBoostingClassifier()",
        )
    )
    seed = rng.choice((0, 7, 42, 2024))
    split = (
        f"X_train, X_test, y_train, y_test = train_test_split({xs}, {y}, "
        f"test_size=0.2, random_state={seed})"
    )
    kind = rng.randrange(6)
    if kind == 0:
        scaler = rng.choice(("StandardScaler()", "MinMaxScaler()", "RobustScaler()"))
        lines = [
            f"{xs}, {y} = load_dataset()",
            f"scaler = {scaler}",
            f"{xs} = scaler.fit_transform({xs})",
            split,
            f"model = {model}",
            "model.fit(X_train, y_train)",
            "print(roc_auc_score(y_test, model.predict_proba(X_test)[:, 1]))",
        ]
        return "Масштабирование признаков", lines, 2
    if kind == 1:
        kbest = rng.choice((10, 20, 50))
        lines = [
            f"{xs}, {y} = load_dataset()",
            f"selector = SelectKBest(f_classif, k={kbest})",
            f"{xs}_sel = selector.fit_transform({xs}, {y})",
            f"model = {model}",
            f"scores = cross_val_score(model, {xs}_sel, {y}, cv=5, scoring='roc_auc')",
            "print(scores.mean())",
        ]
        return "Отбор признаков", lines, 2
    if kind == 2:
        col = rng.choice(("city", "shop_id", "category", "region"))
        lines = [
            "df = pd.read_parquet('train.parquet')",
            f"df['{col}_te'] = df.groupby('{col}')['target'].transform('mean')",
            f"{xs} = df.drop(columns=['target', '{col}'])",
            f"{y} = df['target']",
            split,
            f"model = {model}",
            "model.fit(X_train, y_train)",
            "print(roc_auc_score(y_test, model.predict_proba(X_test)[:, 1]))",
        ]
        return "Кодирование категорий средним таргета", lines, 1
    if kind == 3:
        lines = [
            f"{xs}, {y} = load_dataset()",
            f"{xs}_res, {y}_res = SMOTE(random_state={seed}).fit_resample({xs}, {y})",
            f"X_train, X_test, y_train, y_test = train_test_split({xs}_res, {y}_res, "
            f"test_size=0.2, random_state={seed})",
            f"model = {model}",
            "model.fit(X_train, y_train)",
            "print(f1_score(y_test, model.predict(X_test)))",
        ]
        return "Балансировка классов", lines, 1
    if kind == 4:
        lag = rng.choice((1, 7, 14))
        lines = [
            "df = pd.read_csv('daily_sales.csv', parse_dates=['date']).sort_values('date')",
            f"df['lag_{lag}'] = df['sales'].shift({lag})",
            "df = df.dropna()",
            f"{xs}, {y} = df[['lag_{lag}', 'dow', 'promo']], df['sales']",
            f"X_train, X_test, y_train, y_test = train_test_split({xs}, {y}, "
            f"test_size=0.2, shuffle=True, random_state={seed})",
            "model = GradientBoostingRegressor()",
            "model.fit(X_train, y_train)",
            "print(mean_absolute_error(y_test, model.predict(X_test)))",
        ]
        return "Прогноз продаж на будущие дни", lines, 4
    lines = [
        f"{xs}, {y} = load_dataset()",
        f"{xs} = {xs}.fillna({xs}.median())",
        split,
        f"model = {model}",
        "model.fit(X_train, y_train)",
        "print(roc_auc_score(y_test, model.predict_proba(X_test)[:, 1]))",
    ]
    return "Заполнение пропусков", lines, 1


_LEAK_FILLERS = (
    "warnings.filterwarnings('ignore')",
    "# эксперимент: baseline",
    "np.random.seed(0)",
    "pd.set_option('display.max_columns', 50)",
)


def _gen_leakage(rng: random.Random) -> Variant:
    topic, lines, bug = _leak_program(rng)
    k = rng.choice((0, 1, 1, 2))
    fillers = rng.sample(_LEAK_FILLERS, k)
    lines = fillers + lines
    bug += k
    metric = rng.choice(("0.97", "0.95", "0.99", "0.93"))
    return Variant(
        prompt=(
            f"На отложенной выборке модель показала {metric}, а на новых данных — заметно хуже. "
            "В коде есть утечка данных: информация из проверочной части (или из будущего) "
            "попадает в обучение. В какой строке утечка? Укажите номер строки."
        ),
        key=bug + 1,
        code="\n".join(lines),
        extra={"language": "python", "line_count": len(lines)},
        explanation=f"{topic}: строка {bug + 1} — {lines[bug]}",
    )


LEAKAGE_LINE = ItemTemplate(
    id="data_ml.leakage_line",
    specialization="data_ml",
    topic="model_validation",
    target_grade="middle",
    format=ItemFormat.FIND_BUG_LINE,
    generator=_gen_leakage,
    a=1.5,
    b=0.4,
    title="Найди строку с утечкой данных",
    time_limit_s=180,
)

TEMPLATES = [KFOLD_SIZES, SPLIT_STRATEGY, LEAKAGE_LINE]

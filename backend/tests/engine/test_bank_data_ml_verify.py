"""Сверка ключей шаблонов data_ml с настоящими библиотеками: numpy, pandas, sklearn, scipy.

Код задач выполняется, метрики пересчитываются библиотечными функциями. Если библиотеки
нет в окружении (в CI ставятся только зависимости бэкенда), тест пропускается.
"""

import ast
import contextlib
import io
import math
import re

import numpy as np
import pytest

from app.testing.engine.bank.data_ml import TEMPLATES
from app.testing.engine.templates import ItemFormat, check

REG = {t.id: t for t in TEMPLATES}
SEEDS = range(60)


def _run(code: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(code, {})
    return buf.getvalue()


def _rows(table: str) -> list[list[str]]:
    lines = table.split("\n")
    return [[c.strip() for c in line.split("|")] for line in lines[2:]]


def _assert_numeric(inst, value: float) -> None:
    assert abs(inst.key.value - value) < 1e-9, (inst.public.prompt, inst.key, value)


# --------------------------------------------------------------------------- выполнение кода


@pytest.mark.parametrize(
    "tid",
    ["data_ml.numpy_axis", "data_ml.numpy_view_copy", "data_ml.activation_values"],
)
def test_numpy_code_output_matches_execution(tid):
    for seed in SEEDS:
        inst = REG[tid].generate(seed)
        out = _run(inst.public.code)
        assert check(inst, out), (seed, inst.public.code, out, inst.key)


def test_broadcasting_matches_numpy():
    t = REG["data_ml.numpy_broadcasting"]
    errors = 0
    for seed in range(150):
        inst = t.generate(seed)
        try:
            out = _run(inst.public.code)
        except ValueError:
            out = "error"
            errors += 1
        assert check(inst, out), (seed, inst.public.code, out, inst.key)
    assert 10 < errors < 75  # ошибки встречаются, но не доминируют


@pytest.mark.parametrize(
    "tid", ["data_ml.pandas_nan", "data_ml.pandas_groupby", "data_ml.one_hot_shape"]
)
def test_pandas_code_output_matches_execution(tid):
    pytest.importorskip("pandas")
    for seed in SEEDS:
        inst = REG[tid].generate(seed)
        out = _run(inst.public.code)
        assert check(inst, out), (seed, inst.public.code, out, inst.key)


# --------------------------------------------------------------------------- метрики sklearn


def test_accuracy_paradox_sklearn():
    metrics = pytest.importorskip("sklearn.metrics")
    t = REG["data_ml.accuracy_paradox"]
    for seed in SEEDS:
        inst = t.generate(seed)
        p = inst.public.prompt
        n = int(re.search(r"выборке (\d+)", p).group(1))
        m = re.search(r"из них (\d+)", p)
        if m:
            k = int(m.group(1))
        else:
            k = round(n * float(re.search(r"— (\d+(?:\.\d+)?)%", p).group(1)) / 100)
        y_true = np.array([1] * k + [0] * (n - k))
        y_pred = np.zeros(n, dtype=int)
        acc = metrics.accuracy_score(y_true, y_pred)
        if "accuracy" in p:
            _assert_numeric(inst, acc * 100)
        elif "error rate" in p:
            _assert_numeric(inst, (1 - acc) * 100)
        else:
            _assert_numeric(inst, int((y_true != y_pred).sum()))


def test_regression_metrics_sklearn():
    m = pytest.importorskip("sklearn.metrics")
    t = REG["data_ml.regression_metrics"]
    for seed in range(100):
        inst = t.generate(seed)
        rows = _rows(inst.public.code)
        y = np.array([float(r[1]) for r in rows])
        p = np.array([float(r[2]) for r in rows])
        prompt = inst.public.prompt
        if "MAPE" in prompt:
            value = m.mean_absolute_percentage_error(y, p) * 100
        elif "RMSE" in prompt:
            value = math.sqrt(m.mean_squared_error(y, p))
        elif "MSE" in prompt:
            value = m.mean_squared_error(y, p)
        elif "MAE" in prompt:
            value = m.mean_absolute_error(y, p)
        else:
            value = m.r2_score(y, p)
        _assert_numeric(inst, value)


def test_roc_auc_sklearn():
    m = pytest.importorskip("sklearn.metrics")
    t = REG["data_ml.roc_auc_pairs"]
    for seed in range(100):
        inst = t.generate(seed)
        rows = _rows(inst.public.code)
        y = [int(r[1]) for r in rows]
        s = [float(r[2]) for r in rows]
        _assert_numeric(inst, m.roc_auc_score(y, s))


def test_kfold_sizes_sklearn():
    ms = pytest.importorskip("sklearn.model_selection")
    t = REG["data_ml.kfold_sizes"]
    for seed in range(100):
        inst = t.generate(seed)
        p = inst.public.prompt
        n = int(re.search(r"(\d+) строк", p).group(1))
        x = np.arange(n)
        if "train_test_split" in p:
            share = float(re.search(r"test_size=(\d+(?:\.\d+)?)", p).group(1))
            _, test = ms.train_test_split(x, test_size=share, random_state=0)
            value = len(test)
        elif "RepeatedKFold" in p:
            k, r = map(int, re.search(r"n_splits=(\d+), n_repeats=(\d+)", p).groups())
            value = ms.RepeatedKFold(n_splits=k, n_repeats=r).get_n_splits(x)
        else:
            k = int(re.search(r"n_splits=(\d+)", p).group(1))
            train, val = next(ms.KFold(n_splits=k).split(x))
            if "валидационную" in p:
                value = len(val)
            elif "обучается" in p:
                value = len(train)
            else:
                value = ms.KFold(n_splits=k).get_n_splits(x)
        _assert_numeric(inst, value)


def test_knn_sklearn():
    nb = pytest.importorskip("sklearn.neighbors")
    t = REG["data_ml.knn_predict"]
    for seed in range(100):
        inst = t.generate(seed)
        rows = _rows(inst.public.code)
        x = [[int(r[1]), int(r[2])] for r in rows]
        y = [r[3] for r in rows]
        k = int(re.search(r"k = (\d)", inst.public.prompt).group(1))
        q = [int(v) for v in re.search(r"точке \((\d+), (\d+)\)", inst.public.prompt).groups()]
        metric = "manhattan" if "манхэттен" in inst.public.prompt else "euclidean"
        clf = nb.KNeighborsClassifier(n_neighbors=k, metric=metric).fit(x, y)
        assert check(inst, str(clf.predict([q])[0])), (seed, inst.key)


def test_gini_split_sklearn_tree():
    tree = pytest.importorskip("sklearn.tree")
    t = REG["data_ml.gini_split"]
    for seed in range(100):
        inst = t.generate(seed)
        rows = _rows(inst.public.code)
        left = [int(v) for v in rows[0][1:]]
        right = [int(v) for v in rows[1][1:]]
        x, y = [], []
        for side, counts in ((0, left), (1, right)):
            for cls, c in enumerate(counts):
                x += [[side]] * c
                y += [cls] * c
        p = inst.public.prompt
        crit = "entropy" if "энтропия" in p else "gini"
        clf = tree.DecisionTreeClassifier(max_depth=1, criterion=crit).fit(x, y)
        imp, ns = clf.tree_.impurity, clf.tree_.n_node_samples
        assert clf.tree_.node_count == 3
        weighted = (ns[1] * imp[1] + ns[2] * imp[2]) / ns[0]
        if "исходном узле" in p:
            value = imp[0]
        elif "взвешенный" in p:
            value = weighted
        else:
            value = imp[0] - weighted
        assert abs(inst.key.value - value) < 1e-9, (seed, p)


# --------------------------------------------------------------------------- статистика


def test_ztest_matches_chi2_and_statsmodels():
    stats = pytest.importorskip("scipy.stats")
    t = REG["data_ml.ab_ztest"]
    for seed in range(100):
        inst = t.generate(seed)
        n1, x1, n2, x2 = (
            int(v) for v in re.findall(r"(\d+) (?:пользователей|конверсий)", inst.public.prompt)
        )
        chi2 = stats.chi2_contingency([[x1, n1 - x1], [x2, n2 - x2]], correction=False)[0]
        sign = 1 if x2 / n2 > x1 / n1 else -1
        assert abs(inst.key.value - sign * math.sqrt(chi2)) < 1e-6
    sm = pytest.importorskip("statsmodels.stats.proportion")
    for seed in range(30):
        inst = t.generate(seed)
        n1, x1, n2, x2 = (
            int(v) for v in re.findall(r"(\d+) (?:пользователей|конверсий)", inst.public.prompt)
        )
        z, _ = sm.proportions_ztest([x2, x1], [n2, n1])
        assert abs(inst.key.value - z) < 1e-6


def test_multiple_testing_statsmodels():
    mt = pytest.importorskip("statsmodels.stats.multitest")
    t = REG["data_ml.multiple_testing"]
    methods = {"Бонферрони": "bonferroni", "Холма": "holm", "Бенджамини": "fdr_bh"}
    for seed in range(150):
        inst = t.generate(seed)
        p = inst.public.prompt
        method = next(v for k, v in methods.items() if k in p)
        alpha = float(re.search(r"α = (\d+(?:\.\d+)?)", p).group(1))
        pvals = [float(v) for v in re.findall(r"p = (\d+(?:\.\d+)?)", inst.public.code)]
        reject = mt.multipletests(pvals, alpha=alpha, method=method)[0]
        _assert_numeric(inst, int(reject.sum()))


def test_psi_matches_scipy_kl():
    special = pytest.importorskip("scipy.special")
    t = REG["data_ml.drift_psi"]
    for seed in range(100):
        inst = t.generate(seed)
        rows = _rows(inst.public.code)
        e = np.array([float(r[1].rstrip("%")) for r in rows]) / 100
        a = np.array([float(r[2].rstrip("%")) for r in rows]) / 100
        assert abs(e.sum() - 1) < 1e-9 and abs(a.sum() - 1) < 1e-9
        value = special.rel_entr(a, e).sum() + special.rel_entr(e, a).sum()
        assert abs(inst.key.value - value) < 1e-9


# --------------------------------------------------------------------------- нейросети


def _parse_linear(code: str) -> list[tuple[int, int, bool]]:
    return [
        (int(a), int(b), not bias)
        for a, b, bias in re.findall(r"nn\.Linear\((\d+), (\d+)(, bias=False)?\)", code)
    ]


def test_param_count_matches_sklearn_mlp():
    nn_mod = pytest.importorskip("sklearn.neural_network")
    t = REG["data_ml.nn_param_count"]
    checked = 0
    for seed in range(120):
        inst = t.generate(seed)
        code = inst.public.code
        layers = _parse_linear(code)
        if "bias=False" in code or "BatchNorm" in code:
            continue  # у MLP из sklearn смещения есть всегда и нет BatchNorm
        d_in, d_out = layers[0][0], layers[-1][1]
        hidden = tuple(b for _, b, _ in layers[:-1])
        rng = np.random.default_rng(seed)
        x = rng.normal(size=(30, d_in))
        y = rng.normal(size=(30, d_out)) if d_out > 1 else rng.normal(size=30)
        mlp = nn_mod.MLPRegressor(hidden_layer_sizes=hidden, max_iter=1)
        with pytest.warns(Warning):
            mlp.fit(x, y)
        total = sum(w.size for w in mlp.coefs_) + sum(b.size for b in mlp.intercepts_)
        _assert_numeric(inst, total)
        checked += 1
    assert checked >= 30


def test_param_count_matches_torch():
    torch = pytest.importorskip("torch")
    t = REG["data_ml.nn_param_count"]
    for seed in range(60):
        inst = t.generate(seed)
        scope: dict = {}
        exec(inst.public.code, scope)
        total = sum(p.numel() for p in scope["model"].parameters() if p.requires_grad)
        _assert_numeric(inst, total)
    assert torch is not None


def test_conv_shape_matches_numpy_windows():
    t = REG["data_ml.conv_output_shape"]
    for seed in range(150):
        inst = t.generate(seed)
        code = inst.public.code
        c_in, c_out, k, s, p = (
            int(v)
            for v in re.search(
                r"Conv2d\((\d+), (\d+), kernel_size=(\d+), stride=(\d+), padding=(\d+)\)", code
            ).groups()
        )
        if "randn" not in code:
            _assert_numeric(inst, k * k * c_in * c_out + c_out)
            continue
        h = int(re.search(r"randn\(8, \d+, (\d+), \d+\)", code).group(1))
        padded = np.zeros((h + 2 * p, h + 2 * p))
        out = np.lib.stride_tricks.sliding_window_view(padded, (k, k))[::s, ::s]
        size = out.shape[0]
        if "MaxPool2d" in code:
            pooled = np.lib.stride_tricks.sliding_window_view(np.zeros((size, size)), (2, 2))
            size = pooled[::2, ::2].shape[0]
        _assert_numeric(inst, size)


def test_gradient_step_matches_numeric_gradient():
    t = REG["data_ml.gradient_step"]
    for seed in range(150):
        inst = t.generate(seed)
        p = inst.public.prompt
        w = float(re.search(r"w = (-?\d+(?:\.\d+)?)", p).group(1))
        b = float(re.search(r"b = (-?\d+(?:\.\d+)?)", p).group(1))
        pairs = [(float(x), float(y)) for x, y in re.findall(r"\(x=(-?\d+), y=(-?\d+)\)", p)]
        lr = float(re.search(r"learning rate (\d+(?:\.\d+)?)", p).group(1))
        xs, ys = np.array([q[0] for q in pairs]), np.array([q[1] for q in pairs])

        def loss(w_, b_, xs=xs, ys=ys):
            return float(np.mean((w_ * xs + b_ - ys) ** 2))

        eps = 1e-6
        gw = (loss(w + eps, b) - loss(w - eps, b)) / (2 * eps)
        gb = (loss(w, b + eps) - loss(w, b - eps)) / (2 * eps)
        value = w - lr * gw if "равен w" in p else b - lr * gb
        assert abs(inst.key.value - value) < 1e-5, (seed, p)


# --------------------------------------------------------------------------- «найди строку»


@pytest.mark.parametrize("tid", ["data_ml.leakage_line", "data_ml.torch_loop_bug"])
def test_find_bug_code_is_valid_python(tid):
    t = REG[tid]
    lines_seen = set()
    for seed in range(150):
        inst = t.generate(seed)
        ast.parse(inst.public.code)
        line = inst.public.code.split("\n")[inst.key - 1].strip()
        assert line and not line.startswith("#"), (seed, line)
        lines_seen.add(inst.key)
    assert len(lines_seen) >= 4


def test_bank_composition():
    from collections import Counter

    assert len(TEMPLATES) == 30
    grades = Counter(t.target_grade for t in TEMPLATES)
    assert grades == {"intern": 6, "junior": 8, "middle": 9, "senior": 7}
    topics = Counter(t.topic for t in TEMPLATES)
    assert len(topics) >= 6 and max(topics.values()) <= 7
    assert {t.format for t in TEMPLATES} == set(ItemFormat)

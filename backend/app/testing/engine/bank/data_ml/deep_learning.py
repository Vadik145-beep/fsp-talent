"""Data Science / ML — нейросети: активации, параметры, свёртки, градиент, цикл обучения."""

from __future__ import annotations

import random

from ...templates import ItemFormat, ItemTemplate, NumericKey, Variant
from ._common import dec_key, fmt_num

# --------------------------------------------------------------------------- функции активации


def _gen_activation(rng: random.Random) -> Variant:
    n = rng.randint(4, 6)
    while True:
        x = [rng.randint(-8, 9) for _ in range(n)]
        if any(v < 0 for v in x) and any(v > 1 for v in x) and x.count(max(x)) == 1:
            break
    var = rng.choice(("x", "z", "h", "logits"))
    kind = rng.choice(("relu", "step", "hardtanh", "relu_sum", "softmax_argmax", "relu6"))
    if kind == "relu":
        body, out = f"print(*np.maximum(0, {var}))", [max(0, v) for v in x]
    elif kind == "step":
        body, out = f"print(*({var} > 0).astype(int))", [1 if v > 0 else 0 for v in x]
    elif kind == "hardtanh":
        body, out = f"print(*np.clip({var}, -1, 1))", [min(1, max(-1, v)) for v in x]
    elif kind == "relu_sum":
        body, out = f"print(np.maximum(0, {var}).sum())", [sum(max(0, v) for v in x)]
    elif kind == "relu6":
        body = f"print(*np.minimum(np.maximum(0, {var}), 6))"
        out = [min(6, max(0, v)) for v in x]
    else:
        body = f"e = np.exp({var} - {var}.max())\np = e / e.sum()\nprint(p.argmax())"
        out = [x.index(max(x))]
    code = f"import numpy as np\n\n{var} = np.array([{', '.join(map(str, x))}])\n{body}"
    return Variant(
        prompt="Что выведет код? Запишите значения через пробел в порядке вывода.",
        key=" ".join(map(str, out)),
        code=code,
        extra={"language": "python"},
        explanation=f"Активация: {kind}.",
    )


ACTIVATION = ItemTemplate(
    id="data_ml.activation_values",
    specialization="data_ml",
    topic="deep_learning",
    target_grade="intern",
    format=ItemFormat.CODE_OUTPUT,
    generator=_gen_activation,
    a=1.1,
    b=-1.2,
    title="Функции активации на векторе",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- число параметров


def _gen_param_count(rng: random.Random) -> Variant:
    d_in = rng.choice((8, 10, 16, 20, 32, 64, 100, 784))
    hidden = [rng.choice((16, 32, 64, 128, 256)) for _ in range(rng.randint(1, 3))]
    d_out = rng.choice((1, 2, 3, 5, 10))
    sizes = [d_in, *hidden, d_out]
    no_bias = rng.randrange(len(sizes) - 1) if rng.random() < 0.25 else -1
    use_bn = rng.random() < 0.3
    use_dropout = rng.random() < 0.5
    lines = ["import torch.nn as nn", "", "model = nn.Sequential("]
    total = 0
    for i in range(len(sizes) - 1):
        a, b = sizes[i], sizes[i + 1]
        bias_arg = ", bias=False" if i == no_bias else ""
        lines.append(f"    nn.Linear({a}, {b}{bias_arg}),")
        total += a * b + (0 if i == no_bias else b)
        if i < len(sizes) - 2:
            if use_bn and i == 0:
                lines.append(f"    nn.BatchNorm1d({b}),")
                total += 2 * b
            lines.append("    nn.ReLU(),")
            if use_dropout:
                lines.append(f"    nn.Dropout({rng.choice((0.1, 0.2, 0.3, 0.5))}),")
    lines.append(")")
    return Variant(
        prompt="Сколько обучаемых параметров (весов и смещений) у этой модели PyTorch?",
        key=NumericKey(total, 0),
        code="\n".join(lines),
        extra={"language": "python", "answer_type": "integer"},
        explanation=f"Слои {sizes}: {total} параметров.",
    )


PARAM_COUNT = ItemTemplate(
    id="data_ml.nn_param_count",
    specialization="data_ml",
    topic="deep_learning",
    target_grade="junior",
    format=ItemFormat.NUMERIC,
    generator=_gen_param_count,
    a=1.3,
    b=-0.5,
    title="Число параметров полносвязной сети",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- свёртка


def conv_out(size: int, k: int, s: int, p: int) -> int:
    return (size + 2 * p - k) // s + 1


def _gen_conv(rng: random.Random) -> Variant:
    while True:
        h = rng.choice((28, 32, 48, 64, 96, 100, 128, 224, 227))
        c_in = rng.choice((1, 3, 16, 32, 64))
        c_out = rng.choice((8, 16, 32, 64, 128))
        k = rng.choice((1, 3, 3, 5, 7, 11))
        s = rng.choice((1, 1, 2, 2, 4))
        p = rng.choice((0, 0, 1, 2, 3))
        if h + 2 * p >= k and (s > 1 or p != (k - 1) // 2):  # не тривиальное «same»
            break
    q = rng.choice(("size", "size", "params", "pool"))
    out = conv_out(h, k, s, p)
    layer = f"nn.Conv2d({c_in}, {c_out}, kernel_size={k}, stride={s}, padding={p})"
    if q == "size":
        value = out
        ask = "Какой будет высота (и ширина) выходной карты признаков?"
        code = f"x = torch.randn(8, {c_in}, {h}, {h})\nconv = {layer}\ny = conv(x)"
    elif q == "pool":
        value = out // 2
        ask = "Какой будет высота (и ширина) выхода после свёртки и пулинга?"
        code = (
            f"x = torch.randn(8, {c_in}, {h}, {h})\nconv = {layer}\n"
            "pool = nn.MaxPool2d(kernel_size=2)\ny = pool(conv(x))"
        )
    else:
        value = k * k * c_in * c_out + c_out
        ask = "Сколько обучаемых параметров у этого свёрточного слоя (с bias)?"
        code = f"conv = {layer}"
    return Variant(
        prompt=f"{ask} Вход — тензор формы (batch, channels, height, width).",
        key=NumericKey(value, 0),
        code="import torch\nimport torch.nn as nn\n\n" + code,
        extra={"language": "python", "answer_type": "integer"},
        explanation=f"out = ({h} + 2·{p} − {k}) // {s} + 1 = {out}; ответ {value}.",
    )


CONV_SHAPE = ItemTemplate(
    id="data_ml.conv_output_shape",
    specialization="data_ml",
    topic="deep_learning",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_conv,
    a=1.4,
    b=0.3,
    title="Размер выхода и параметры свёртки",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- шаг градиента


def gd_step(w: float, b: float, xs: list[int], ys: list[int], lr: float) -> tuple[float, float]:
    n = len(xs)
    errs = [w * x + b - y for x, y in zip(xs, ys, strict=True)]
    gw = 2 / n * sum(e * x for e, x in zip(errs, xs, strict=True))
    gb = 2 / n * sum(errs)
    return w - lr * gw, b - lr * gb


def _gen_gradient(rng: random.Random) -> Variant:
    w = rng.choice((0.5, 1.0, 1.5, 2.0, -0.5, 0.0))
    b = rng.choice((0.0, 0.5, 1.0, -1.0))
    n = rng.choice((1, 2, 2, 3))
    xs = [rng.randint(-3, 4) or 1 for _ in range(n)]
    ys = [rng.randint(-5, 9) for _ in range(n)]
    lr = rng.choice((0.01, 0.05, 0.1))
    new_w, new_b = gd_step(w, b, xs, ys, lr)
    ask_w = rng.random() < 0.7
    value = new_w if ask_w else new_b
    data = ", ".join(f"(x={x}, y={y})" for x, y in zip(xs, ys, strict=True))
    return Variant(
        prompt=(
            f"Линейная модель ŷ = w·x + b, функция потерь — MSE (среднее (ŷ − y)² по объектам). "
            f"Сейчас w = {fmt_num(w)}, b = {fmt_num(b)}. Делаем один шаг градиентного спуска "
            f"по всем объектам {data} с learning rate {lr}. Чему станет равен "
            f"{'w' if ask_w else 'b'}? Ответ округлите до трёх знаков после запятой."
        ),
        key=dec_key(value, 3),
        extra={"answer_type": "decimal", "decimals": 3},
        explanation=f"w = {new_w:.5f}, b = {new_b:.5f}",
    )


GRADIENT_STEP = ItemTemplate(
    id="data_ml.gradient_step",
    specialization="data_ml",
    topic="deep_learning",
    target_grade="middle",
    format=ItemFormat.NUMERIC,
    generator=_gen_gradient,
    a=1.4,
    b=0.6,
    title="Один шаг градиентного спуска",
    time_limit_s=240,
)

# --------------------------------------------------------------------------- цикл обучения PyTorch

_TORCH_BUGS = {
    "softmax": (
        "Loss падает очень медленно и застревает на высоком уровне, хотя на этих данных "
        "похожая модель обычно учится хорошо."
    ),
    "zero_grad": "Loss не меняется от эпохи к эпохе: веса модели не обновляются.",
    "eval": (
        "В модели есть Dropout и BatchNorm. Точность на валидации заметно скачет между "
        "запусками на одних и тех же весах."
    ),
    "item": "Потребление памяти GPU растёт с каждой итерацией, пока обучение не падает с OOM.",
    "shuffle": (
        "Обучающий датасет записан подряд по классам. Loss скачет пилой от батча к батчу, "
        "модель обучается плохо."
    ),
    "lr": "Через несколько итераций loss становится nan.",
}


def _gen_torch_bug(rng: random.Random) -> Variant:
    bug = rng.choice(tuple(_TORCH_BUGS))
    bs = rng.choice((32, 64, 128, 256))
    epochs = rng.choice((10, 20, 30, 50))
    opt = rng.choice(("Adam", "AdamW"))
    lr = rng.choice(("1e-3", "3e-4", "5e-4"))
    xb, yb = rng.choice((("xb", "yb"), ("inputs", "labels"), ("x", "y")))
    head = []
    if rng.random() < 0.5:
        head.append("torch.manual_seed(42)")
    if rng.random() < 0.5:
        head.append('device = "cuda" if torch.cuda.is_available() else "cpu"')
    else:
        head.append('device = "cuda"')
    lines = [
        *head,
        "model = Net().to(device)",
        f"optimizer = torch.optim.{opt}(model.parameters(), lr={'10' if bug == 'lr' else lr})",
        "criterion = nn.CrossEntropyLoss()",
        f"train_loader = DataLoader(train_ds, batch_size={bs}, "
        f"shuffle={'False' if bug == 'shuffle' else 'True'})",
        "",
        f"for epoch in range({epochs}):",
        "    model.train()",
        "    total = 0.0",
        f"    for {xb}, {yb} in train_loader:",
        f"        {xb}, {yb} = {xb}.to(device), {yb}.to(device)",
    ]
    marks: dict[str, int] = {}
    marks["lr"] = len(head) + 1
    marks["shuffle"] = len(head) + 3
    step = [
        "        optimizer.zero_grad()",
        f"        logits = model({xb})"
        if bug != "softmax"
        else f"        logits = torch.softmax(model({xb}), dim=1)",
        f"        loss = criterion(logits, {yb})",
        "        loss.backward()",
        "        optimizer.step()",
        "        total += loss" if bug == "item" else "        total += loss.item()",
    ]
    if bug == "zero_grad":
        step = [step[1], step[2], step[3], step[0], step[4], step[5]]
    base = len(lines)
    marks["softmax"] = base + (1 if bug != "zero_grad" else 0)
    marks["zero_grad"] = base + 3
    marks["item"] = base + 5
    lines += step
    if rng.random() < 0.5:
        lines.append("    scheduler.step()")
        lines.insert(len(head) + 2, "scheduler = torch.optim.lr_scheduler.StepLR(optimizer, 10)")
        for key_ in ("shuffle", "softmax", "zero_grad", "item"):
            marks[key_] += 1
    marks["eval"] = len(lines)
    lines += [
        "    model.train()" if bug == "eval" else "    model.eval()",
        "    with torch.no_grad():",
        "        val_logits = model(X_val.to(device))",
        "        val_acc = (val_logits.argmax(dim=1) == y_val.to(device)).float().mean().item()",
        "    print(epoch, total / len(train_loader), val_acc)",
    ]
    bug_idx = marks[bug]
    return Variant(
        prompt=f"{_TORCH_BUGS[bug]} В какой строке причина? Укажите номер строки.",
        key=bug_idx + 1,
        code="\n".join(lines),
        extra={"language": "python", "line_count": len(lines)},
        explanation=f"{bug}: строка {bug_idx + 1} — {lines[bug_idx].strip()}",
    )


TORCH_LOOP_BUG = ItemTemplate(
    id="data_ml.torch_loop_bug",
    specialization="data_ml",
    topic="deep_learning",
    target_grade="senior",
    format=ItemFormat.FIND_BUG_LINE,
    generator=_gen_torch_bug,
    a=1.5,
    b=1.2,
    title="Ошибка в цикле обучения PyTorch",
    time_limit_s=210,
)

TEMPLATES = [ACTIVATION, PARAM_COUNT, CONV_SHAPE, GRADIENT_STEP, TORCH_LOOP_BUG]

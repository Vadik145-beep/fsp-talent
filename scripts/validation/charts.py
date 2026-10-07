"""Графики валидации: PNG для отчёта и записи `ValidationChart` для экрана «Валидация»."""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from common import GRADE_LABELS, GRADES, r4

# Брендбук ФСП: основной #402FFF; вторая и третья серии проверены валидатором палитры
# (различимы при дальтонизме); базовые линии — нейтральный серый.
OURS = "#402FFF"
S2 = "#eb6834"
S3 = "#1baf7a"
BASE = "#9a9ba1"
BASE_DARK = "#5f6067"
INK = "#1B1C21"
MUTED = "#5f6067"
GRID = "#EDEDED"
AXIS = "#C8C9CA"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": MUTED,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
    }
)


def _save(fig: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=120, metadata={"Software": None})
    plt.close(fig)


def _pct_axis(ax: Any, top: float = 1.0) -> None:
    ax.set_ylim(0, top)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))


def _bars(
    ax: Any, labels: list[str], series: list[tuple[str, list[float], str]], *, pct: bool = True
) -> None:
    """Сгруппированные столбцы с подписями значений (подпись — цветом текста, не серии)."""
    n = len(series)
    width = 0.8 / n
    x = np.arange(len(labels))
    for i, (name, vals, color) in enumerate(series):
        pos = x - 0.4 + width * (i + 0.5)
        bars = ax.bar(pos, vals, width * 0.92, color=color, label=name, zorder=2)
        for b, v in zip(bars, vals, strict=True):
            text = f"{v * 100:.0f}%" if pct else f"{v:.2f}"
            ax.annotate(
                text,
                (b.get_x() + b.get_width() / 2, b.get_height()),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
                color=INK,
            )
    ax.set_xticks(x, labels)
    ax.grid(axis="x", visible=False)
    if n > 1:
        drop = -0.2 if any("\n" in str(lbl) for lbl in labels) else -0.12
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, drop), ncol=n, fontsize=9)


def chart(
    cid: str,
    title: str,
    description: str,
    chart_type: str,
    x_label: str,
    y_label: str,
    series: list[tuple[str, list[tuple[Any, float]]]],
    summary: dict[str, float],
) -> dict[str, Any]:
    return {
        "id": cid,
        "title": title,
        "description": description,
        "chart_type": chart_type,
        "x_label": x_label,
        "y_label": y_label,
        "series": [
            {"name": name, "points": [{"x": x, "y": r4(y)} for x, y in pts]} for name, pts in series
        ],
        "summary": {k: r4(v) for k, v in summary.items()},
        "is_stub": False,
    }


def build(results: dict[str, Any], img_dir: Path) -> list[dict[str, Any]]:
    t = results["testing"]
    acc, cat, stab, disc = t["accuracy"], t["category"], t["stability"], t["discrimination"]
    leak = results["leak"]
    mt = results["matching"]
    sy = mt["systems"]
    charts: list[dict[str, Any]] = []
    glabels = [GRADE_LABELS[g] for g in GRADES]

    # 1. Точность грейда (итоговая категория после онбординга)
    exact = [cat["per_grade"][g]["exact"] for g in GRADES]
    within = [cat["per_grade"][g]["within_one"] for g in GRADES]
    fig, ax = plt.subplots(figsize=(7.5, 4))
    _bars(ax, glabels, [("Точно", exact, OURS), ("±1 грейд", within, S2)])
    _pct_axis(ax, 1.12)
    ax.set_title("Итоговый грейд после теста по истинному грейду")
    _save(fig, img_dir / "grade_accuracy.png")
    charts.append(
        chart(
            "grade_accuracy",
            "Точность определения грейда",
            "Синтетические кандидаты с известным уровнем прошли настоящий тест по банку из 192 "
            "шаблонов (онбординг по правилам платформы). Доля, у кого итоговый грейд совпал "
            "с истинным точно и с ошибкой не больше одного грейда.",
            "bar",
            "Истинный грейд",
            "Доля кандидатов",
            [
                ("Точно", list(zip(glabels, exact, strict=True))),
                ("±1 грейд", list(zip(glabels, within, strict=True))),
            ],
            {
                "exact": cat["exact"],
                "within_one": cat["within_one"],
                "exact_far_from_threshold": cat["exact_far"],
                "theta_grade_exact": acc["grade_exact"],
            },
        )
    )

    # 2. Восстановление θ
    pts = acc["scatter"]
    fig, ax = plt.subplots(figsize=(5.6, 5))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ax.scatter(xs, ys, s=10, color=OURS, alpha=0.35, linewidths=0)
    lo, hi = -3.2, 3.2
    ax.plot([lo, hi], [lo, hi], ls="--", color=BASE_DARK, lw=1)
    for c in (-1, 0, 1):
        ax.axvline(c, color=AXIS, lw=0.8, zorder=0)
        ax.axhline(c, color=AXIS, lw=0.8, zorder=0)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("Истинный уровень θ")
    ax.set_ylabel("Оценка теста θ̂")
    ax.set_title(f"θ̂ против θ: r = {acc['corr_theta']:.3f}, RMSE = {acc['rmse_theta']:.2f}")
    _save(fig, img_dir / "theta_recovery.png")
    step = max(1, len(pts) // 300)
    charts.append(
        chart(
            "theta_recovery",
            "Оценка уровня против истинного",
            "Каждая точка — кандидат (показан каждый "
            f"{step}-й): истинный уровень θ против оценки первого теста θ̂. "
            "Серые линии — пороги грейдов.",
            "scatter",
            "Истинный уровень θ",
            "Оценка теста θ̂",
            [("Кандидаты", [(round(x, 2), round(y, 2)) for x, y in pts[::step]])],
            {
                "correlation": acc["corr_theta"],
                "rmse": acc["rmse_theta"],
                "mean_se": acc["mean_se"],
                "mean_test_length": acc["mean_length"],
            },
        )
    )

    # 3. Стабильность повтора
    labels = [
        "Грейд по θ̂\n(один тест)",
        "Категория\nпосле онбординга",
        "Решение «подтвердил\nзаявленный / нет»",
    ]
    agree = [stab["theta_grade_agreement"], stab["category_agreement"], stab["decision_agreement"]]
    kappa = [stab["theta_grade_kappa"], stab["category_kappa"], stab["decision_kappa"]]
    fig, ax = plt.subplots(figsize=(7.5, 4))
    _bars(ax, labels, [("Доля совпадений", agree, OURS), ("Каппа Коэна", kappa, S2)], pct=False)
    ax.set_ylim(0, 1.1)
    ax.set_title("Повторный тест с другими задачами")
    _save(fig, img_dir / "retest_stability.png")
    flat = [lbl.replace("\n", " ") for lbl in labels]
    charts.append(
        chart(
            "retest_stability",
            "Стабильность при повторном тесте",
            "Те же кандидаты проходят весь онбординг второй раз с другими задачами и вариантами. "
            "Доля совпадений; каппа Коэна в сводке.",
            "bar",
            "Что сравниваем",
            "Доля совпадений",
            [("Доля совпадений", list(zip(flat, agree, strict=True)))],
            {
                "agreement": stab["category_agreement"],
                "cohen_kappa": stab["category_kappa"],
                "decision_agreement": stab["decision_agreement"],
                "decision_kappa": stab["decision_kappa"],
                "theta_grade_agreement": stab["theta_grade_agreement"],
                "theta_grade_kappa": stab["theta_grade_kappa"],
                "theta_retest_corr": stab["retest_corr"],
            },
        )
    )

    # 4. Различающая сила шаблонов
    p = disc["points"]
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.scatter(
        [x[1] for x in p],
        [x[2] for x in p],
        s=22,
        color=OURS,
        alpha=0.6,
        edgecolors="white",
        linewidths=0.8,
        zorder=2,
    )
    ax.axhline(0.2, ls="--", color=S2, lw=1.2)
    ax.annotate(
        "порог 0,2",
        (max(x[1] for x in p), 0.2),
        xytext=(0, 3),
        textcoords="offset points",
        ha="right",
        fontsize=8,
        color=INK,
    )
    ax.set_xlabel("Различающая сила a (из банка)")
    ax.set_ylabel("Точечно-бисериальная r_pb")
    ax.set_ylim(0, max(0.7, max(x[2] for x in p) + 0.05))
    ax.set_title(f"192 шаблона: средняя r_pb = {disc['linear_mean']:.2f}")
    _save(fig, img_dir / "item_discrimination.png")
    charts.append(
        chart(
            "item_discrimination",
            "Различающая сила задач",
            "Каждая точка — шаблон банка: параметр a против точечно-бисериальной корреляции ответа "
            "с суммой по остальным задачам (каждый кандидат решает все шаблоны "
            "своего направления).",
            "scatter",
            "Различающая сила a",
            "Корреляция с баллом (r_pb)",
            [("Шаблоны", [(round(a, 2), round(r, 3)) for _, a, r in p])],
            {
                "mean_point_biserial": disc["linear_mean"],
                "mean_a": disc["mean_a"],
                "share_above_02": disc["linear_share_02"],
                "adaptive_mean_point_biserial": disc["adaptive_mean"],
            },
        )
    )

    # 5. Длина теста и итоговая SE
    ses = results["testing"]["final_se"]
    edges = np.round(np.arange(0.30, max(ses) + 0.021, 0.02), 2)
    counts, _ = np.histogram(ses, bins=edges)
    centers = [f"{a:.2f}–{b:.2f}" for a, b in pairwise(edges)]
    keep = [i for i, c in enumerate(counts) if c > 0]
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.bar([centers[i] for i in keep], [counts[i] for i in keep], color=OURS, width=0.85, zorder=2)
    ax.set_xlabel("Стандартная ошибка θ̂ в конце первого теста")
    ax.set_ylabel("Кандидатов")
    ax.set_title(f"Все тесты дошли до {acc['max_length']} задач; цель SE < 0,30")
    ax.tick_params(axis="x", labelsize=8, rotation=30)
    ax.grid(axis="x", visible=False)
    _save(fig, img_dir / "test_length.png")
    charts.append(
        chart(
            "test_length",
            "Длина теста и точность",
            "Тест останавливается при SE < 0,30 или на 20-й задаче. На банке из 32 шаблонов "
            "на направление цель SE < 0,30 недостижима за 20 задач: все тесты идут до конца. "
            "Столбцы — распределение итоговой SE.",
            "histogram",
            "SE в конце теста",
            "Кандидатов",
            [("Тесты", [(centers[i], float(counts[i])) for i in keep])],
            {
                "mean": acc["mean_length"],
                "share_stopped_by_se": acc["share_se_target"],
                "mean_se": acc["mean_se"],
                "max_length": float(acc["max_length"]),
            },
        )
    )

    # 6. Утечка
    modes = leak["modes"]
    ml = [m["label"].replace(" + ", "\n+ ").replace(", ", ",\n") for m in modes]
    ch = [m["cheater_inflated"] for m in modes]
    hn = [m["honest_inflated"] for m in modes]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    _bars(ax, ml, [("Читеры", ch, S2), ("Честные", hn, OURS)])
    _pct_axis(ax, max(ch) * 1.25)
    ax.set_title("Доля завышенных грейдов при утечке 20% шаблонов")
    ax.tick_params(axis="x", labelsize=8)
    _save(fig, img_dir / "leak_detector.png")
    det = next(m for m in modes if m["mode"] == "detector")
    static = next(m for m in modes if m["mode"] == "static")
    flat = [m["label"] for m in modes]
    charts.append(
        chart(
            "leak_detector",
            "Защита от утечки заданий",
            f"Симуляция: {leak['leaked_items']} из {leak['bank_items']} шаблонов (20%) слиты, 10% "
            "кандидатов — «читеры». Как часто грейд по тесту выше истинного "
            "в каждом режиме защиты.",
            "bar",
            "Режим",
            "Доля завышенных грейдов",
            [
                ("Читеры", list(zip(flat, ch, strict=True))),
                ("Честные", list(zip(flat, hn, strict=True))),
            ],
            {
                "recall": det["item_recall"] or 0.0,
                "precision": det["item_precision"] or 0.0,
                "cheater_recall": static["cand_recall"],
                "cheater_precision": static["cand_precision"] or 0.0,
                "inflated_no_protection": static["cheater_inflated"],
                "inflated_parametrized": next(m for m in modes if m["mode"] == "param")[
                    "cheater_inflated"
                ],
            },
        )
    )

    # 7. Подбор против базовых линий
    names = [
        ("system", "Платформа"),
        ("keywords", "Ключевые слова\n(BM25 по резюме)"),
        ("category_random", "Только категория,\nвнутри случайно"),
        ("random", "Случайно"),
    ]
    lbls = [n for _, n in names]
    p10 = [sy[k]["p10"] for k, _ in names]
    nd = [sy[k]["ndcg10"] for k, _ in names]
    r50 = [sy[k]["r50"] for k, _ in names]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    _bars(ax, lbls, [("precision@10", p10, OURS), ("nDCG@10", nd, S2), ("recall@50", r50, S3)])
    _pct_axis(ax, 1.0)
    ax.set_title("Подбор на 100 потребностях с эталонной разметкой")
    _save(fig, img_dir / "precision_at_10.png")
    flat = [n.replace("\n", " ") for n in lbls]
    charts.append(
        chart(
            "precision_at_10",
            "Качество подбора",
            "100 синтетических потребностей, 1200 кандидатов, эталон по скрытой правде. "
            "Выдача платформы (категория из теста + формула ранжирования) против поиска по "
            "ключевым словам резюме и случайного порядка.",
            "bar",
            "Способ",
            "Значение",
            [
                ("precision@10", list(zip(flat, p10, strict=True))),
                ("nDCG@10", list(zip(flat, nd, strict=True))),
                ("recall@50", list(zip(flat, r50, strict=True))),
            ],
            {
                "precision_at_10": sy["system"]["p10"],
                "ndcg_at_10": sy["system"]["ndcg10"],
                "recall_at_50": sy["system"]["r50"],
                "baseline_precision_at_10": sy["keywords"]["p10"],
                "baseline_ndcg_at_10": sy["keywords"]["ndcg10"],
                "random_precision_at_10": sy["random"]["p10"],
                "relevant_in_top_share": sy["system"]["relevant_in_top_share"],
            },
        )
    )

    # 8. Размер банка
    rows = results["testing"]["bank_sizes"]
    fig, ax = plt.subplots(figsize=(7.5, 4))
    sizes = [r["size"] for r in rows]
    ax.plot(
        sizes,
        [r["corr_theta"] for r in rows],
        marker="o",
        color=OURS,
        lw=2,
        label="Корреляция θ̂ с θ",
    )
    ax.plot(
        sizes,
        [r["grade_exact"] for r in rows],
        marker="o",
        color=S2,
        lw=2,
        label="Грейд по θ̂ точно",
    )
    ax.set_xticks(sizes)
    ax.set_ylim(0.6, 1.0)
    ax.set_xlabel("Шаблонов в банке направления")
    ax.legend(loc="lower right")
    ax.set_title("Точность при урезанном банке (те же кандидаты)")
    _save(fig, img_dir / "bank_size.png")
    charts.append(
        chart(
            "bank_size",
            "Сколько шаблонов нужно в банке",
            "Тот же тест на урезанном банке: первые k шаблонов направления. Чем больше банк, "
            "тем точнее оценка; на 32 шаблонах рост ещё не закончился.",
            "line",
            "Шаблонов в банке",
            "Значение",
            [
                ("Корреляция с истинным уровнем", [(r["size"], r["corr_theta"]) for r in rows]),
                ("Грейд точно", [(r["size"], r["grade_exact"]) for r in rows]),
            ],
            {
                f"se_at_{rows[0]['size']}": rows[0]["mean_se"],
                f"se_at_{rows[-1]['size']}": rows[-1]["mean_se"],
            },
        )
    )

    # 9. Абляция подбора
    abl = [
        ("system", "Вся формула"),
        ("no_test", "Без теста\n(заявленный грейд)"),
        ("no_category", "Без категорий"),
        ("no_stack", "Без стека"),
        ("no_proximity", "Без синонимов\nи смежности"),
        ("no_fsp", "Без ФСП"),
        ("no_theta", "Без θ в счёте"),
    ]
    al = [n for _, n in abl]
    ap = [sy[k]["p10"] for k, _ in abl]
    an = [sy[k]["ndcg10"] for k, _ in abl]
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    _bars(ax, al, [("precision@10", ap, OURS), ("nDCG@10", an, S2)])
    _pct_axis(ax, 0.8)
    ax.set_title("Вклад компонентов: убираем по одному")
    ax.tick_params(axis="x", labelsize=8)
    _save(fig, img_dir / "matching_ablation.png")
    flat = [n.replace("\n", " ") for n in al]
    charts.append(
        chart(
            "matching_ablation",
            "Вклад компонентов подбора",
            "Что будет, если убрать один компонент: тест (категория по заявленному грейду), "
            "категории, стек, синонимы и смежность технологий, ФСП, θ в счёте.",
            "bar",
            "Вариант",
            "Значение",
            [
                ("precision@10", list(zip(flat, ap, strict=True))),
                ("nDCG@10", list(zip(flat, an, strict=True))),
            ],
            {
                "precision_at_10": sy["system"]["p10"],
                "no_test": sy["no_test"]["p10"],
                "no_category": sy["no_category"]["p10"],
                "no_stack": sy["no_stack"]["p10"],
                "no_proximity": sy["no_proximity"]["p10"],
                "no_fsp": sy["no_fsp"]["p10"],
                "no_theta": sy["no_theta"]["p10"],
            },
        )
    )
    for c in charts:  # summary без None
        c["summary"] = {k: v for k, v in c["summary"].items() if v is not None}
    return charts

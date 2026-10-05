"""Общие помощники генераторов backend-банка."""

from __future__ import annotations

PERSON_NAMES = (
    "anna",
    "boris",
    "vera",
    "gleb",
    "dina",
    "egor",
    "zoya",
    "ilya",
    "kira",
    "lev",
    "mila",
    "oleg",
)


def text_table(header: list[str], rows: list[list[str]]) -> str:
    """Таблица в текстовом виде: заголовок, разделитель, строки (как в bank_examples)."""
    widths = [
        max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(header)
    ]
    out = [" | ".join(h.ljust(w) for h, w in zip(header, widths, strict=True)).rstrip()]
    out.append("-+-".join("-" * w for w in widths))
    out += [" | ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip() for r in rows]
    return "\n".join(out)


def sql_value(v: object) -> str:
    """Значение ячейки для текстовой таблицы."""
    return "NULL" if v is None else str(v)


def fmt_num(x: float) -> str:
    """Число без лишних нулей: 3.0 → 3, 2.50 → 2.5."""
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"

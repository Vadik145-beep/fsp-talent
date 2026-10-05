"""Общие помощники шаблонов qa."""

from __future__ import annotations

from ...templates import NumericKey


def dec_key(value: float, decimals: int) -> NumericKey:
    """Ключ для ответа «округлите до N знаков».

    Ключ — точное значение, допуск — половина последнего разряда. Так принимается любое
    верное округление (в том числе 0.625 → 0.62 и 0.63), но не соседнее значение.
    """
    return NumericKey(float(value), 0.5 * 10 ** (-decimals) + 1e-6)


def table(header: list[str], rows: list[list[str]]) -> str:
    """Текстовая таблица с выравниванием по столбцам."""
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(header)]
    out = [" | ".join(h.ljust(w) for h, w in zip(header, widths, strict=True))]
    out.append("-+-".join("-" * w for w in widths))
    out += [" | ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)) for r in rows]
    return "\n".join(out)


def fmt_num(x: float) -> str:
    """Число без лишних нулей: 3.0 → «3», 2.50 → «2.5»."""
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s

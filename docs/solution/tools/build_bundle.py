"""Склейка разделов docs/solution в один Markdown для DOCX/PDF и проверка диаграмм mermaid.

    python docs/solution/tools/build_bundle.py --out <папка>                   # fsp-talent-docs.md
    python docs/solution/tools/build_bundle.py --out <папка> --render-mermaid  # + diagrams/*.png
    python docs/solution/tools/build_bundle.py --check-mermaid                 # только проверить

Для --render-mermaid / --check-mermaid нужен mermaid-cli: `npx -y @mermaid-js/mermaid-cli`
(или путь к mmdc в переменной MMDC). Ссылки между разделами переписываются в якоря
внутри одного файла, ссылки на остальной репозиторий — в адреса GitHub.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs/solution"
ORDER = [
    "index.md",
    "01_architecture.md",
    "02_testing.md",
    "03_matching.md",
    "04_validation.md",
    "05_fsp_integration.md",
    "06_api.md",
    "api_endpoints.md",
    "07_libraries.md",
    "08_deployment.md",
]
REPO_URL = "https://github.com/Vadik145-beep/fsp-talent/blob/main/"
MERMAID = re.compile(r"```mermaid\n(.*?)```", re.S)
LINK = re.compile(r"\]\(([^)#\s]+\.md|[^)#\s]+/)(#[^)]*)?\)")


def mmdc_cmd() -> list[str]:
    if os.environ.get("MMDC"):
        return [os.environ["MMDC"]]
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        sys.exit("нужен mermaid-cli: установите Node.js (npx) или задайте MMDC")
    return [npx, "-y", "@mermaid-js/mermaid-cli"]


def render(code: str, target: Path) -> str | None:
    """Рендер одной диаграммы; None — успех, иначе текст ошибки."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "d.mmd"
        src.write_text(code, encoding="utf-8")
        res = subprocess.run(
            [*mmdc_cmd(), "-i", str(src), "-o", str(target), "-b", "white", "-s", "2"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    if res.returncode != 0 or not target.exists():
        return (res.stderr or res.stdout).strip()[-800:]
    return None


def rewrite_links(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        target, anchor = m.group(1), m.group(2) or ""
        name = Path(target).name
        if "/" not in target and name in ORDER:
            return f"]({anchor or '#' + name.removesuffix('.md')})"
        resolved = (DOCS / target).resolve()
        try:
            rel = resolved.relative_to(ROOT).as_posix()
        except ValueError:
            return m.group(0)
        return f"]({REPO_URL}{rel}{anchor})"

    return LINK.sub(repl, text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, help="папка для fsp-talent-docs.md")
    ap.add_argument("--render-mermaid", action="store_true", help="диаграммы → PNG")
    ap.add_argument("--check-mermaid", action="store_true", help="только проверить диаграммы")
    args = ap.parse_args(argv)
    if not args.out and not args.check_mermaid:
        ap.error("нужен --out или --check-mermaid")

    errors: list[str] = []
    if args.check_mermaid:
        with tempfile.TemporaryDirectory() as tmp:
            n = 0
            for name in ORDER:
                for i, m in enumerate(MERMAID.finditer((DOCS / name).read_text(encoding="utf-8"))):
                    n += 1
                    err = render(m.group(1), Path(tmp) / f"{n}.svg")
                    status = "ok" if err is None else "ОШИБКА"
                    print(f"{name} диаграмма {i + 1}: {status}")
                    if err:
                        errors.append(f"{name} #{i + 1}: {err}")
        for e in errors:
            print(e, file=sys.stderr)
        print(f"диаграмм: {n}, с ошибками: {len(errors)}")
        return 1 if errors else 0

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    img_dir = out / "diagrams"
    parts: list[str] = []
    counter = 0
    for name in ORDER:
        text = (DOCS / name).read_text(encoding="utf-8")
        text = re.sub(r"<!--.*?-->\n?", "", text, flags=re.S)
        if args.render_mermaid:
            img_dir.mkdir(exist_ok=True)

            def to_png(m: re.Match[str], name: str = name) -> str:
                nonlocal counter
                counter += 1
                png = img_dir / f"diagram_{counter:02d}.png"
                err = render(m.group(1), png)
                if err:
                    errors.append(f"{name}: {err}")
                    return m.group(0)
                return f"![Диаграмма {counter}](diagrams/{png.name})"

            text = MERMAID.sub(to_png, text)
        anchor = name.removesuffix(".md")
        parts.append(f'<a id="{anchor}"></a>\n\n' + rewrite_links(text).strip() + "\n")
    bundle = out / "fsp-talent-docs.md"
    bundle.write_text("\n\n---\n\n".join(parts), encoding="utf-8", newline="\n")
    print(f"записано: {bundle}" + (f", диаграмм: {counter}" if args.render_mermaid else ""))
    for e in errors:
        print(f"ошибка диаграммы: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

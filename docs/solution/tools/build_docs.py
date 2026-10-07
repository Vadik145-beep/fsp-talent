"""Единый документ к решению (ТЗ 3.4, 5.2): docs/solution → DOCX и PDF.

    python docs/solution/tools/build_docs.py  # → fsp-talent-documentation.{docx,pdf}
    python docs/solution/tools/build_docs.py --preview <папка>  # + PNG первых страниц PDF

Нужны Node.js (mermaid-cli через npx — диаграммы) и Docker. Шаги:
1. `build_bundle.py --render-mermaid` — разделы в один Markdown, диаграммы в PNG, графики
   валидации рядом, ссылки между разделами — якоря;
2. титульный лист, оглавление, разрывы страниц между разделами, ширина колонок таблиц
   по содержимому;
3. pandoc (Markdown → DOCX) и LibreOffice (`lo_finish.py`: шрифты и цвета брендбука ФСП,
   номера страниц, рамки таблиц, обновление оглавления, встроенные шрифты, экспорт PDF)
   в образе `fsp-docs-render` (`tools/docker/Dockerfile`, собирается сам при первом запуске).
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[2]
sys.path.insert(0, str(TOOLS))
import build_bundle  # noqa: E402

IMAGE = "fsp-docs-render"
NAME = "fsp-talent-documentation"
STAND = "https://159-194-200-243.sslip.io"
REPO = "https://github.com/Vadik145-beep/fsp-talent"
MONTHS = "января февраля марта апреля мая июня июля августа сентября октября ноября декабря"

PAGE_BREAK = '```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```'
TOC = (
    "```{=openxml}\n"
    '<w:sdt><w:sdtPr><w:docPartObj><w:docPartGallery w:val="Table of Contents"/>'
    "<w:docPartUnique/></w:docPartObj></w:sdtPr><w:sdtContent>"
    '<w:p><w:pPr><w:pStyle w:val="TOCHeading"/></w:pPr><w:r><w:t>Оглавление</w:t></w:r></w:p>'
    '<w:p><w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>'
    '<w:r><w:instrText xml:space="preserve"> TOC \\o "1-2" \\h \\z \\u </w:instrText></w:r>'
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    "<w:r><w:t>Оглавление: обновите поле (F9)</w:t></w:r>"
    '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
    "</w:sdtContent></w:sdt>\n```"
)


def title_page(today: dt.date) -> str:
    date = f"{today.day} {MONTHS.split()[today.month - 1]} {today.year}"

    def block(style: str, text: str) -> str:
        return f'::: {{custom-style="{style}"}}\n{text}\n:::\n'

    return "\n".join(
        [
            block("FSP Kind", "Спецтрек ФСП · Лидеры цифровой трансформации 2026"),
            block("FSP Title", "fsp-talent"),
            block(
                "FSP Subtitle",
                "Платформа подбора IT-специалистов с верифицированным профилем достижений "
                "участника ФСП",
            ),
            block("FSP Kind", "Сопроводительная документация к решению"),
            block("FSP Meta", "Команда: [Название команды]"),
            block("FSP Meta", f"Стенд: <{STAND}>"),
            block("FSP Meta", f"Swagger API: <{STAND}/api/docs>"),
            block("FSP Meta", f"Репозиторий: <{REPO}>"),
            block("FSP Meta", f"Версия документа: {date}"),
            block(
                "FSP Note",
                "Документ собран из разделов docs/solution репозитория "
                "(python docs/solution/tools/build_docs.py). Разделы 1–8 соответствуют "
                "пунктам ТЗ 3.4.",
            ),
        ]
    )


def split_row(line: str) -> list[str]:
    cells = re.split(r"(?<!\\)\|", line.strip())
    return [c.strip() for c in cells[1:-1]]


SEPARATOR = re.compile(r"^\|(\s*:?-+:?\s*\|)+\s*$")


def fit_tables(text: str) -> str:
    """Ширина колонок pipe-таблиц по содержимому: pandoc берёт доли из числа дефисов."""
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    in_code = False
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            in_code = not in_code
        if (
            not in_code
            and line.startswith("|")
            and i + 1 < len(lines)
            and SEPARATOR.match(lines[i + 1])
        ):
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            rows = [split_row(r) for r in [lines[i], *lines[i + 2 : j]]]
            n = len(split_row(lines[i + 1]))
            widths = []
            for c in range(n):
                lens = sorted(len(r[c]) if c < len(r) else 0 for r in rows)
                typical = lens[int(len(lens) * 0.8)] if lens else 3
                head = len(rows[0][c]) if c < len(rows[0]) else 0
                # самое длинное слово колонки не должно рваться посередине
                words = (len(w) for r in rows[1:] if c < len(r) for w in r[c].split())
                word = max(words, default=0)
                widths.append(min(70, max(10, typical, min(word, 20) + 9, min(head, 20) + 3)))
            out.append(line)
            out.append("|" + "|".join("-" * w for w in widths) + "|")
            out.extend(lines[i + 2 : j])
            i = j
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def prepare(bundle: str, today: dt.date) -> str:
    # разделы склеены через «---»: вместо линии — новая страница
    body = bundle.replace("\n\n---\n\n[]{#sec-", f"\n\n{PAGE_BREAK}\n\n[]{{#sec-")
    body = fit_tables(body)
    meta = "---\nlang: ru-RU\n---\n"
    return "\n\n".join([meta, title_page(today), PAGE_BREAK, TOC, PAGE_BREAK, body]) + "\n"


def docker(work: Path, image: str, *cmd: str) -> None:
    subprocess.run(
        ["docker", "run", "--rm", "-v", f"{work}:/work", "-w", "/work", image, *cmd],
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", type=Path, default=ROOT / "docs/solution")
    ap.add_argument("--work", type=Path, help="рабочая папка (по умолчанию временная)")
    ap.add_argument("--preview", type=Path, help="папка для PNG первых страниц PDF")
    ap.add_argument("--preview-pages", type=int, default=6)
    ap.add_argument("--image", default=IMAGE)
    args = ap.parse_args(argv)

    if subprocess.run(["docker", "image", "inspect", args.image], capture_output=True).returncode:
        subprocess.run(["docker", "build", "-t", args.image, str(TOOLS / "docker")], check=True)

    work = args.work or Path(tempfile.mkdtemp(prefix="fsp-docs-"))
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    if build_bundle.main(["--out", str(work), "--render-mermaid"]) != 0:
        print("ошибка сборки бандла или диаграмм", file=sys.stderr)
        return 1
    bundle = (work / "fsp-talent-docs.md").read_text(encoding="utf-8")
    (work / "doc.md").write_text(prepare(bundle, dt.date.today()), encoding="utf-8", newline="\n")
    shutil.copyfile(TOOLS / "lo_finish.py", work / "lo_finish.py")

    docker(
        work,
        args.image,
        "pandoc",
        "doc.md",
        "-f",
        "markdown+gfm_auto_identifiers",
        "-t",
        "docx",
        "--resource-path=/work",
        "-o",
        "raw.docx",
    )
    docker(work, args.image, "python3", "lo_finish.py", "raw.docx", f"{NAME}.docx", f"{NAME}.pdf")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for ext in ("docx", "pdf"):
        shutil.copyfile(work / f"{NAME}.{ext}", args.out_dir / f"{NAME}.{ext}")
        print(f"записано: {args.out_dir / f'{NAME}.{ext}'}")

    if args.preview:
        docker(
            work,
            args.image,
            "pdftoppm",
            "-png",
            "-r",
            "60",
            "-f",
            "1",
            "-l",
            str(args.preview_pages),
            f"{NAME}.pdf",
            "page",
        )
        args.preview.mkdir(parents=True, exist_ok=True)
        for png in sorted(work.glob("page*.png")):
            shutil.copyfile(png, args.preview / png.name)
        print(f"превью страниц: {args.preview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

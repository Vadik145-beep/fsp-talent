"""Выгрузка OpenAPI-схемы бэкенда в docs/api/openapi.json (по ней фронт генерирует TS-типы).

Запуск из корня репозитория (нужны зависимости бэкенда):
    python scripts/export_openapi.py            # записать файл
    python scripts/export_openapi.py --check    # проверить, что файл актуален (для CI)
БД для выгрузки не нужна.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "api" / "openapi.json"
sys.path.insert(0, str(ROOT / "backend"))


def render() -> str:
    from app.main import app

    return json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    content = render()
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if json.loads(current or "{}") != json.loads(content):
            print("docs/api/openapi.json устарел: выполните python scripts/export_openapi.py")
            return 1
        print("docs/api/openapi.json актуален")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"Записано: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

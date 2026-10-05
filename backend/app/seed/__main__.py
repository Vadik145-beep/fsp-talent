"""CLI загрузчика демо-данных.

Запуск из каталога backend/:
    python -m app.seed            # догрузить недостающее (идемпотентно)
    python -m app.seed --reset    # очистить таблицы и залить заново
База — из DATABASE_URL, каталог фикстур — из SEED_DIR (по умолчанию data/seed).
"""

import argparse
import asyncio
import sys
from pathlib import Path

from app.seed.loader import run_seed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.seed", description=__doc__)
    parser.add_argument("--reset", action="store_true", help="очистить таблицы и залить заново")
    parser.add_argument("--seed-dir", type=Path, default=None, help="каталог с *.json")
    parser.add_argument("--database-url", default=None, help="по умолчанию DATABASE_URL")
    args = parser.parse_args(argv)
    report = asyncio.run(run_seed(args.database_url, reset=args.reset, seed_dir=args.seed_dir))
    print(report.format())
    return 0


if __name__ == "__main__":
    sys.exit(main())

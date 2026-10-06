"""CLI: синхронизировать шаблоны движка в таблицу `items` (идемпотентно).

Запуск из каталога backend/ (после `python -m app.seed`):
    python -m app.testing.sync_bank
База — из DATABASE_URL. Подробности решения — в `app/testing/bank.py`.
"""

import argparse
import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.testing.bank import SyncReport, sync_bank


async def run_sync(database_url: str | None = None) -> SyncReport:
    engine = create_async_engine(database_url or get_settings().database_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            report = await sync_bank(session)
            await session.commit()
            return report
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.testing.sync_bank", description=__doc__)
    parser.add_argument("--database-url", default=None, help="по умолчанию DATABASE_URL")
    args = parser.parse_args(argv)
    print(asyncio.run(run_sync(args.database_url)).format())
    return 0


if __name__ == "__main__":
    sys.exit(main())

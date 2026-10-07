"""CLI периодических работ регулярных заданий (для cron).

Запуск из каталога backend/:
    python -m app.tasks distribute   # раздать задания (раз в N дней)
    python -m app.tasks daily        # просрочить задания без ответа, снизить свежесть (раз в сутки)
    python -m app.tasks tick         # всё сразу
База — из DATABASE_URL.
"""

import argparse
import asyncio
import json
import sys

from app.core.db import dispose_engine, get_session
from app.tasks.jobs import JobName, run_job


async def _run(job: JobName) -> dict[str, object]:
    try:
        async for session in get_session():
            return dict(await run_job(session, job))
        raise RuntimeError("нет сессии БД")
    finally:
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.tasks", description=__doc__)
    parser.add_argument("job", nargs="?", default="tick", choices=["distribute", "daily", "tick"])
    args = parser.parse_args(argv)
    print(json.dumps(asyncio.run(_run(args.job)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

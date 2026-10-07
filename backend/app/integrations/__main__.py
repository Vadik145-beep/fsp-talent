"""CLI повторной доставки вебхуков (для cron, например раз в минуту).

Запуск из каталога backend/:
    python -m app.integrations      # отправить доставки, у которых подошло время повтора
База — из DATABASE_URL.
"""

import asyncio
import json
import sys

from app.core.db import dispose_engine, get_session
from app.integrations.webhooks import deliver_pending


async def _run() -> dict[str, int]:
    try:
        async for session in get_session():
            return await deliver_pending(session)
        raise RuntimeError("нет сессии БД")
    finally:
        await dispose_engine()


def main() -> int:
    print(json.dumps(asyncio.run(_run()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

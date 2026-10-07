"""Периодические работы регулярных заданий — для планировщика (cron) и админа.

- `distribute` — раздать активные задания кандидатам без активного задания (раз в N дней,
  например раз в неделю: `0 9 * * 1 python -m app.tasks distribute`);
- `daily` — просрочить задания без ответа и снизить свежесть профилей (раз в сутки);
- `tick` — всё сразу.
"""

from datetime import datetime
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.clock import now_msk
from app.tasks.service import TaskService

JobName = Literal["distribute", "daily", "tick"]


async def run_job(session: AsyncSession, job: JobName = "tick", now: datetime | None = None) -> Any:
    now = now or now_msk()
    service = TaskService(session)
    result: dict[str, Any] = {"job": job, "expired": 0, "assigned": 0, "freshness_factor": 1.0}
    if job in ("daily", "tick"):
        result["expired"] = await service.expire_overdue(now)
    if job in ("distribute", "tick"):
        result["assigned"] = await service.distribute_all(now)
    if job in ("daily", "tick"):
        result["freshness_factor"] = (await service.decay_freshness(now))["factor"]
    await session.commit()
    return result

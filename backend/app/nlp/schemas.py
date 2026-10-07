"""Схемы ответов модуля «Тексты и ИИ» — расширения контракта (только новые поля, старые как были).

- `SelectedItemOut`: + `template_id` (шаблон банка), `target_grade`.
- `ItemDraftOut`: + `item_id` (строка в банке задач со статусом draft — её одобряет админ через
  `/api/admin/items/{item_id}/approve`), `origin` (llm | vocabulary), `reused`.
- `VacancyTestOut`: + `created_at`.
"""

from datetime import datetime

from pydantic import Field

from app.admin.schemas import ItemDraft, SelectedItem, VacancyTestResult
from app.common.enums import GradeCode


class SelectedItemOut(SelectedItem):
    template_id: str | None = Field(default=None, description="id шаблона в банке задач")
    target_grade: GradeCode | None = None


class ItemDraftOut(ItemDraft):
    item_id: int | None = Field(
        default=None, description="id черновика в банке задач (status=draft) для одобрения"
    )
    origin: str | None = Field(default=None, description="llm | vocabulary")
    reused: bool = Field(default=False, description="Черновик по теме и грейду уже был")


class VacancyTestOut(VacancyTestResult):
    items: list[SelectedItemOut]  # type: ignore[assignment]
    drafts: list[ItemDraftOut]  # type: ignore[assignment]
    created_at: datetime | None = None

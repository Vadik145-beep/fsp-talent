"""Общие схемы API: пагинация, вилка зарплаты, простые ответы."""

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

SALARY_MAX = 10_000_000


class ApiModel(BaseModel):
    """База схем API: лишние поля во входных данных запрещены."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class OutModel(BaseModel):
    """База схем ответа: лишние поля фикстур игнорируются (проекция)."""

    model_config = ConfigDict(extra="ignore", from_attributes=True)


class Page[T](BaseModel):
    items: list[T]
    total: int = Field(ge=0, description="Сколько всего записей с учётом фильтров")
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)


def paginate[T](items: list[T], page: int, page_size: int) -> dict[str, Any]:
    start = (page - 1) * page_size
    return {
        "items": items[start : start + page_size],
        "total": len(items),
        "page": page,
        "page_size": page_size,
    }


class SalaryRangeMixin(BaseModel):
    """Зарплата от–до в рублях. Обязательна в приглашении, вакансии и потребности [ТЗ 2.2 п.1]."""

    salary_from: int = Field(gt=0, le=SALARY_MAX, description="Зарплата от, ₽ в месяц")
    salary_to: int = Field(gt=0, le=SALARY_MAX, description="Зарплата до, ₽ в месяц")

    @model_validator(mode="after")
    def _check_salary_range(self) -> Self:
        if self.salary_from > self.salary_to:
            raise PydanticCustomError(
                "salary_range_invalid",
                "Зарплата «от» не может быть больше зарплаты «до»",
            )
        return self


class MessageResponse(OutModel):
    ok: bool = True
    message: str = Field(examples=["Готово"])


class LabeledCode(OutModel):
    """Код справочника с русской подписью."""

    id: str
    label: str

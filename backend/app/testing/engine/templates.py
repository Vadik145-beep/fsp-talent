"""Параметрические шаблоны задач.

Шаблон = генератор параметров + проверка ответа + IRT-параметры (a, b).
`generate(seed)` детерминированно собирает вариант: одинаковый seed — одинаковый вариант.
Каждый кандидат получает свой seed, поэтому числа, имена, данные и порядок вариантов
у всех разные, и подсмотренный чужой ответ к своему варианту не подходит.

Публичная часть варианта (`PublicItem`) — то, что уходит клиенту. Ключ ответа хранится
только в `ItemInstance.key` и наружу не отдаётся. Идентификатор шаблона и seed тоже не
входят в публичную часть: сервер хранит их у себя, клиенту — непрозрачный id показа.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, NoReturn

from .constants import check_grade, check_specialization


class ItemFormat(StrEnum):
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    NUMERIC = "numeric"
    SHORT_TEXT = "short_text"
    CODE_OUTPUT = "code_output"
    FIND_BUG_LINE = "find_bug_line"
    ORDERING = "ordering"


class TemplateStatus(StrEnum):
    DRAFT = "draft"  # черновик, в тесты не попадает
    PILOT = "pilot"  # непроверочная: показывается, но не влияет на θ (калибровка)
    ACTIVE = "active"  # рабочая, влияет на θ
    RETIRED = "retired"  # выведена из оборота (утечка, устарела)


@dataclass(frozen=True, slots=True)
class NumericKey:
    """Ключ числового ответа: значение и допустимое отклонение."""

    value: float
    tolerance: float = 0.0


@dataclass(frozen=True)
class Variant:
    """Что возвращает генератор шаблона.

    Ключ по форматам:
    - single_choice — индекс верного варианта (int);
    - multi_choice — множество индексов верных вариантов (frozenset[int]);
    - numeric — NumericKey;
    - short_text — кортеж допустимых ответов (tuple[str, ...]);
    - code_output — ожидаемый вывод (str), сравнение по токенам;
    - find_bug_line — номер строки с ошибкой, с 1 (int);
    - ordering — верный порядок как кортеж индексов options (tuple[int, ...]).
    """

    prompt: str
    key: Any
    options: tuple[str, ...] = ()
    code: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)
    explanation: str = ""  # служебное пояснение для админа; кандидату не показывать


@dataclass(frozen=True)
class PublicItem:
    """Публичная часть варианта: только то, что можно показать кандидату."""

    format: ItemFormat
    prompt: str
    options: tuple[str, ...] = ()
    code: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": str(self.format),
            "prompt": self.prompt,
            "options": list(self.options),
            "code": self.code,
            "extra": dict(self.extra),
        }


@dataclass(frozen=True)
class ItemInstance:
    """Сгенерированный вариант задачи. `key` и `explanation` — только на сервере."""

    template_id: str
    seed: int
    public: PublicItem
    key: Any
    explanation: str = ""

    @property
    def format(self) -> ItemFormat:
        return self.public.format

    @property
    def fingerprint(self) -> str:
        """Хэш публичного содержания: одинаковый текст варианта — одинаковый хэш."""
        raw = json.dumps(self.public.to_dict(), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


Generator = Callable[[random.Random], Variant]


@dataclass
class ItemTemplate:
    """Параметрический шаблон задачи."""

    id: str
    specialization: str
    topic: str
    target_grade: str
    format: ItemFormat
    generator: Generator
    a: float = 1.0
    b: float = 0.0
    status: TemplateStatus = TemplateStatus.ACTIVE
    title: str = ""
    time_limit_s: int = 180

    def __post_init__(self) -> None:
        check_specialization(self.specialization)
        check_grade(self.target_grade)
        self.format = ItemFormat(self.format)
        self.status = TemplateStatus(self.status)
        if not self.a > 0:
            raise ValueError(f"{self.id}: параметр a должен быть > 0")
        if not math.isfinite(self.b):
            raise ValueError(f"{self.id}: параметр b должен быть конечным числом")

    def generate(self, seed: int) -> ItemInstance:
        """Детерминированно собрать вариант по seed."""
        rng = random.Random(f"{self.id}#{int(seed)}")
        variant = self.generator(rng)
        _validate_variant(self.id, self.format, variant)
        public = PublicItem(
            format=self.format,
            prompt=variant.prompt,
            options=tuple(variant.options),
            code=variant.code,
            extra=dict(variant.extra),
        )
        return ItemInstance(
            template_id=self.id,
            seed=int(seed),
            public=public,
            key=variant.key,
            explanation=variant.explanation,
        )

    def check(self, instance: ItemInstance, response: Any) -> bool:
        """Проверить ответ на вариант этого шаблона."""
        if instance.template_id != self.id:
            raise ValueError("Вариант сгенерирован другим шаблоном")
        return check(instance, response)


# --------------------------------------------------------------------------- проверка ответов


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"\s*[+-]?\d+\s*", value):
        return int(value)
    return None


def _as_int_list(value: Any) -> list[int] | None:
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        return None
    out: list[int] = []
    for v in value:
        iv = _as_int(v)
        if iv is None:
            return None
        out.append(iv)
    return out


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        f = float(value)
    elif isinstance(value, str):
        s = value.strip().replace(" ", "").replace(" ", "").replace(",", ".")
        if not re.fullmatch(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?", s):
            return None
        f = float(s)
    else:
        return None
    return f if math.isfinite(f) else None


_TRIM_CHARS = " \t\r\n.,;:!?\"'«»`"


def normalize_text(value: str) -> str:
    """Нормализация короткого ответа: регистр, ё→е, пробелы, кавычки и точка по краям."""
    s = value.lower().replace("ё", "е")
    s = re.sub(r"\s+", " ", s).strip(_TRIM_CHARS)
    return s


def output_tokens(value: str) -> list[str]:
    """Вывод программы как список токенов: разделители — пробелы, переводы строк, запятые."""
    return [t for t in re.split(r"[\s,;]+", value.strip()) if t]


def check(instance: ItemInstance, response: Any) -> bool:
    """Проверить ответ кандидата. На мусорный ввод возвращает False, не падает."""
    fmt = instance.format
    key = instance.key
    if fmt is ItemFormat.SINGLE_CHOICE or fmt is ItemFormat.FIND_BUG_LINE:
        iv = _as_int(response)
        return iv is not None and iv == key
    if fmt is ItemFormat.MULTI_CHOICE:
        items = _as_int_list(response)
        return items is not None and len(items) == len(set(items)) and frozenset(items) == key
    if fmt is ItemFormat.ORDERING:
        items = _as_int_list(response)
        return items is not None and tuple(items) == tuple(key)
    if fmt is ItemFormat.NUMERIC:
        fv = _as_float(response)
        return fv is not None and abs(fv - key.value) <= key.tolerance + 1e-9
    if fmt is ItemFormat.SHORT_TEXT:
        if not isinstance(response, str):
            return False
        norm = normalize_text(response)
        return bool(norm) and norm in {normalize_text(k) for k in key}
    if fmt is ItemFormat.CODE_OUTPUT:
        if not isinstance(response, str):
            return False
        return output_tokens(response) == output_tokens(key)
    return False


def correct_response(instance: ItemInstance) -> Any:
    """Ответ, который проверка примет (для превью в админке и тестов)."""
    fmt = instance.format
    key = instance.key
    if fmt is ItemFormat.MULTI_CHOICE:
        return sorted(key)
    if fmt is ItemFormat.ORDERING:
        return list(key)
    if fmt is ItemFormat.NUMERIC:
        return key.value
    if fmt is ItemFormat.SHORT_TEXT:
        return key[0]
    return key


def _validate_variant(template_id: str, fmt: ItemFormat, v: Variant) -> None:
    def fail(msg: str) -> NoReturn:
        raise ValueError(f"{template_id}: {msg}")

    if not v.prompt.strip():
        fail("пустая формулировка")
    n = len(v.options)
    if fmt in (ItemFormat.SINGLE_CHOICE, ItemFormat.MULTI_CHOICE, ItemFormat.ORDERING):
        if n < 2:
            fail("нужно минимум 2 варианта")
        if len(set(v.options)) != n:
            fail("варианты ответа повторяются")
    if fmt is ItemFormat.SINGLE_CHOICE:
        if not isinstance(v.key, int) or not 0 <= v.key < n:
            fail("ключ single_choice — индекс варианта")
    elif fmt is ItemFormat.MULTI_CHOICE:
        if not isinstance(v.key, frozenset) or not v.key or not all(0 <= k < n for k in v.key):
            fail("ключ multi_choice — непустое frozenset индексов")
    elif fmt is ItemFormat.ORDERING:
        if tuple(sorted(v.key)) != tuple(range(n)):
            fail("ключ ordering — перестановка индексов")
    elif fmt is ItemFormat.NUMERIC:
        if not isinstance(v.key, NumericKey):
            fail("ключ numeric — NumericKey")
    elif fmt is ItemFormat.SHORT_TEXT:
        if not isinstance(v.key, tuple) or not v.key or not all(isinstance(k, str) for k in v.key):
            fail("ключ short_text — непустой кортеж строк")
    elif fmt is ItemFormat.CODE_OUTPUT:
        if not v.code or not isinstance(v.key, str) or not output_tokens(v.key):
            fail("code_output требует код и непустой ожидаемый вывод")
    elif fmt is ItemFormat.FIND_BUG_LINE:
        if not v.code:
            fail("find_bug_line требует код")
        lines = v.code.split("\n")
        if not isinstance(v.key, int) or not 1 <= v.key <= len(lines):
            fail("ключ find_bug_line — номер строки с 1")


# --------------------------------------------------------------------------- помощники генераторов


def make_single_choice(
    rng: random.Random,
    prompt: str,
    correct: str,
    distractors: Sequence[str],
    *,
    n_options: int = 4,
    code: str | None = None,
    extra: Mapping[str, Any] | None = None,
    explanation: str = "",
) -> Variant:
    """Вариант с одним верным ответом: случайные дистракторы и случайный порядок."""
    pool = list(dict.fromkeys(d for d in distractors if d != correct))
    k = min(n_options - 1, len(pool))
    if k < 1:
        raise ValueError("Нужен хотя бы один дистрактор")
    options = [correct, *rng.sample(pool, k)]
    rng.shuffle(options)
    return Variant(
        prompt=prompt,
        key=options.index(correct),
        options=tuple(options),
        code=code,
        extra=dict(extra or {}),
        explanation=explanation,
    )


def make_multi_choice(
    rng: random.Random,
    prompt: str,
    correct: Sequence[str],
    wrong: Sequence[str],
    *,
    code: str | None = None,
    extra: Mapping[str, Any] | None = None,
    explanation: str = "",
) -> Variant:
    """Вариант с несколькими верными ответами: все correct и wrong в случайном порядке."""
    options = list(dict.fromkeys([*correct, *wrong]))
    rng.shuffle(options)
    correct_set = set(correct)
    key = frozenset(i for i, o in enumerate(options) if o in correct_set)
    return Variant(
        prompt=prompt,
        key=key,
        options=tuple(options),
        code=code,
        extra=dict(extra or {}),
        explanation=explanation,
    )


def make_ordering(
    rng: random.Random,
    prompt: str,
    steps_in_order: Sequence[str],
    *,
    code: str | None = None,
    extra: Mapping[str, Any] | None = None,
    explanation: str = "",
) -> Variant:
    """Упорядочивание: шаги перемешиваются (не совпадая с верным порядком)."""
    steps = list(steps_in_order)
    order = list(range(len(steps)))
    while True:
        rng.shuffle(order)
        if len(steps) < 2 or order != sorted(order):
            break
    options = tuple(steps[i] for i in order)
    # key[k] — индекс в options шага, который должен стоять k-м
    key = tuple(order.index(i) for i in range(len(steps)))
    return Variant(
        prompt=prompt,
        key=key,
        options=options,
        code=code,
        extra=dict(extra or {}),
        explanation=explanation,
    )


# --------------------------------------------------------------------------- реестр


class TemplateRegistry:
    """Реестр шаблонов по id с фильтрами."""

    def __init__(self, templates: Iterable[ItemTemplate] = ()) -> None:
        self._items: dict[str, ItemTemplate] = {}
        for t in templates:
            self.register(t)

    def register(self, template: ItemTemplate) -> ItemTemplate:
        if template.id in self._items:
            raise ValueError(f"Шаблон {template.id!r} уже зарегистрирован")
        self._items[template.id] = template
        return template

    def get(self, template_id: str) -> ItemTemplate:
        try:
            return self._items[template_id]
        except KeyError:
            raise KeyError(f"Нет шаблона {template_id!r}") from None

    def __contains__(self, template_id: object) -> bool:
        return template_id in self._items

    def __iter__(self) -> Iterator[ItemTemplate]:
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def filter(
        self,
        *,
        specialization: str | None = None,
        status: TemplateStatus | str | Iterable[TemplateStatus | str] | None = None,
        topic: str | None = None,
        target_grade: str | None = None,
        format: ItemFormat | str | None = None,
    ) -> list[ItemTemplate]:
        if status is None:
            statuses = None
        elif isinstance(status, str):
            statuses = {TemplateStatus(status)}
        else:
            statuses = {TemplateStatus(s) for s in status}
        fmt = ItemFormat(format) if format is not None else None
        return [
            t
            for t in self._items.values()
            if (specialization is None or t.specialization == specialization)
            and (statuses is None or t.status in statuses)
            and (topic is None or t.topic == topic)
            and (target_grade is None or t.target_grade == target_grade)
            and (fmt is None or t.format is fmt)
        ]

    def topics(self, specialization: str | None = None) -> list[str]:
        seen = dict.fromkeys(
            t.topic
            for t in self._items.values()
            if specialization is None or t.specialization == specialization
        )
        return list(seen)

    def instance(self, template_id: str, seed: int) -> ItemInstance:
        return self.get(template_id).generate(seed)

    def check(self, instance: ItemInstance, response: Any) -> bool:
        return self.get(instance.template_id).check(instance, response)

"""Схемы ответов мока реестра ФСП — наше предложение контракта будущего API ФСП."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

DisciplineCode = Literal["product", "algorithmic", "security", "uav", "robotics"]
LevelCode = Literal["regional", "national", "international"]


class Discipline(BaseModel):
    code: DisciplineCode = Field(description="Код дисциплины спортивного программирования")
    title: str = Field(examples=["Продуктовое программирование"])


class Level(BaseModel):
    code: LevelCode = Field(description="Уровень соревнования")
    title: str = Field(examples=["Всероссийский"])


class Competition(BaseModel):
    id: str = Field(examples=["COMP-2024-05"])
    title: str = Field(description="Название соревнования")
    organizer: str = Field(description="Организатор")
    region: str | None = Field(None, description="Регион проведения (для региональных)")
    participants_total: int = Field(description="Сколько участников или команд было в зачёте")
    protocol_url: str = Field(description="Ссылка на итоговый протокол (в моке — заглушка)")


class Result(BaseModel):
    kind: Literal["place", "diploma", "participant"] = Field(
        description="place — место в зачёте, diploma — диплом степени, participant — участие"
    )
    place: int | None = Field(None, description="Место (для kind=place)")
    diploma_degree: Literal[1, 2, 3] | None = Field(None, description="Степень диплома")
    label: str = Field(description="Готовая подпись", examples=["Диплом I степени", "2 место"])


class Team(BaseModel):
    name: str = Field(description="Название команды")
    size: int = Field(description="Размер команды")
    role: str = Field(description="Роль участника в команде", examples=["бэкенд-разработчик"])
    is_captain: bool = Field(description="Был ли капитаном")


class Achievement(BaseModel):
    id: str = Field(examples=["ACH-000001-01"])
    competition: Competition
    discipline: Discipline
    level: Level
    date: dt.date = Field(description="Дата окончания соревнования")
    result: Result
    participation: Literal["individual", "team"] = Field(description="Личный или командный зачёт")
    team: Team | None = Field(None, description="Команда (только для командного зачёта)")
    rating_points: int = Field(description="Рейтинг-очки реестра за этот результат")
    verified: bool = Field(True, description="Результат подтверждён протоколом ФСП")


class ParticipantSummary(BaseModel):
    achievements_count: int
    rating_points_total: int
    disciplines: list[DisciplineCode] = Field(description="Дисциплины, в которых участвовал")
    best_level: LevelCode | None = Field(None, description="Высший уровень соревнований")
    prizes_count: int = Field(description="Призовые результаты: 1–3 место или диплом")
    last_achievement_date: dt.date | None = None


class Participant(BaseModel):
    fsp_id: str = Field(examples=["FSP-000001"], pattern=r"^FSP-\d{6}$")
    last_name: str
    first_name: str
    middle_name: str | None = None
    full_name: str
    region: str = Field(description="Регион участника")
    registered_at: dt.date = Field(description="Дата регистрации в ФСП")
    profile_url: str = Field(description="Публичная страница участника в реестре (заглушка)")
    has_history: bool = Field(description="Есть ли у участника хотя бы одно достижение")
    summary: ParticipantSummary
    updated_at: dt.datetime = Field(description="Когда данные участника последний раз менялись")


class AchievementList(BaseModel):
    fsp_id: str
    has_history: bool
    total: int
    items: list[Achievement] = Field(description="Достижения по дате, от старых к новым")
    updated_at: dt.datetime


class ParticipantBatch(BaseModel):
    items: list[Participant]
    not_found: list[str] = Field(description="Запрошенные ФСП ID, которых нет в реестре")


class Dictionaries(BaseModel):
    disciplines: list[Discipline]
    levels: list[Level]


class Health(BaseModel):
    status: Literal["ok"]
    participants: int
    synthetic: bool


class ErrorBody(BaseModel):
    code: str = Field(examples=["participant_not_found"])
    message: str = Field(examples=["Участник ФСП с таким ID не найден"])
    details: dict = Field(default_factory=dict)

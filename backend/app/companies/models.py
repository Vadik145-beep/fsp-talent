"""Компании работодателей и их рекрутеры."""

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    industry: Mapped[str] = mapped_column(String(100), default="")
    website: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str | None] = mapped_column(String(100))
    contact_email: Mapped[str] = mapped_column(String(254))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    inn: Mapped[str | None] = mapped_column(String(12))
    verified_domain: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    trust_score: Mapped[float] = mapped_column(Float, default=50)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    invite_code: Mapped[str | None] = mapped_column(String(32), unique=True)


class Recruiter(Base):
    __tablename__ = "recruiters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    position: Mapped[str] = mapped_column(String(100), default="")
    phone: Mapped[str | None] = mapped_column(String(32))
    telegram: Mapped[str | None] = mapped_column(String(64))
    is_company_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

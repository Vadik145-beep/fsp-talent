# fsp-talent — частые команды. Бэкенд-цели ожидают окружение с зависимостями:
#   cd backend && pip install -e ".[dev]"
PY ?= python
COMPOSE = docker compose -p fsp-talent
LOCAL_DB = postgresql+asyncpg://fsp:fsp@localhost:15432/fsp_talent

.PHONY: help up up-backend down logs ps migrate test lint fmt typecheck fixtures openapi check

help:
	@echo "up          — поднять весь стек (docker compose up --build -d)"
	@echo "up-backend  — только postgres, backend, mailpit"
	@echo "down        — остановить стек"
	@echo "logs        — логи бэкенда"
	@echo "migrate     — применить миграции к БД на localhost:15432"
	@echo "test        — pytest (нужна БД на localhost:15432)"
	@echo "lint / fmt  — ruff check / ruff format"
	@echo "typecheck   — mypy"
	@echo "fixtures    — перегенерировать data/seed/*.json"
	@echo "openapi     — выгрузить docs/api/openapi.json"
	@echo "check       — lint + typecheck + test + проверка openapi"

up:
	$(COMPOSE) up --build -d

up-backend:
	$(COMPOSE) up --build -d postgres backend mailpit

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f backend

ps:
	$(COMPOSE) ps

migrate:
	cd backend && DATABASE_URL=$(LOCAL_DB) alembic upgrade head

test:
	cd backend && DATABASE_URL=$(LOCAL_DB) pytest

lint:
	cd backend && ruff check . && ruff check --config pyproject.toml ../scripts

fmt:
	cd backend && ruff format . && ruff format --config pyproject.toml ../scripts

typecheck:
	cd backend && mypy

fixtures:
	$(PY) scripts/seed/generate_fixtures.py

openapi:
	$(PY) scripts/export_openapi.py

check: lint typecheck test
	$(PY) scripts/export_openapi.py --check

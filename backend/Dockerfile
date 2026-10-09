# Контекст сборки — корень репозитория (нужен data/seed). Исключения — backend/Dockerfile.dockerignore.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SEED_DIR=/app/data/seed

WORKDIR /app/backend

# Сначала только зависимости — слой кэшируется, пока не меняется pyproject.toml
COPY backend/pyproject.toml ./
RUN python -c "import tomllib; d = tomllib.load(open('pyproject.toml', 'rb')); print('\n'.join(d['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt

COPY backend/ /app/backend/
COPY data/seed/ /app/data/seed/
# результаты валидации для /api/eval/* (scripts/validation/run_all.py)
COPY data/validation/ /app/data/validation/

RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3)"

# процессов uvicorn: по умолчанию 2 (по числу ядер стенда), задаётся UVICORN_WORKERS
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}"]

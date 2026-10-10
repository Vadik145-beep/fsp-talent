# 7. Библиотеки и компоненты с версиями

<!-- Файл сгенерирован: python docs/solution/tools/gen_libraries.py. Не править руками. -->

Снято 07.10.2026 с локального dev-стека: версии Python-пакетов — из установленных в контейнерах, версии npm — из `package-lock.json`, образы — из compose-файлов и Dockerfile. Лицензия проекта — MIT (`LICENSE`).

**Лицензии.** Все компоненты — открытые: MIT, BSD, Apache-2.0, ISC, PSF и аналогичные разрешительные. MPL-2.0 (certifi — корневые сертификаты; lightningcss и caniuse-lite — только при сборке CSS) — слабый копилефт на уровне файла, на наш код не распространяется; шрифты Inter и JetBrains Mono — SIL OFL-1.1. Проприетарных и закрытых компонентов нет. LLM — открытая модель Qwen2.5-1.5B-Instruct (Apache-2.0, GGUF Q4_K_M) в llama.cpp (MIT) на нашем же сервере; внешний LLM-провайдер не нужен.

## Платформа

| Компонент | Версия |
|---|---|
| Python (бэкенд, мок реестра) | 3.12.15 (в `pyproject.toml`: `>=3.12`) |
| Node.js (dev-сервер и сборка фронта) | 22.23.3 (образ `node:22-alpine`) |
| PostgreSQL | 16.15 |
| Keycloak (ФСП ID) | 25.0.6 |

## Библиотеки

### Бэкенд (`backend/pyproject.toml`)

Python 3.12.15 (в образе). Прямых зависимостей: 14, всего с транзитивными: 44.

| Пакет | Объявлено | Установлено | Лицензия | Зачем |
|---|---|---|---|---|
| alembic | `alembic>=1.14` | 1.20.0 | MIT | миграции схемы БД |
| asyncpg | `asyncpg>=0.30` | 0.31.0 | Apache-2.0 | драйвер PostgreSQL |
| email-validator | `email-validator>=2.2` | 2.3.0 | Unlicense | проверка адресов почты |
| fastapi | `fastapi>=0.115,<1.0` | 0.142.2 | MIT | веб-фреймворк API, OpenAPI/Swagger |
| httpx | `httpx>=0.27` | 0.28.1 | BSD-3-Clause | HTTP-клиент: Keycloak, реестр ФСП, LLM |
| numpy | `numpy>=2.0` | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | движок адаптивного теста (IRT, EAP, калибровка) |
| pdfplumber | `pdfplumber>=0.11` | 0.11.10 | MIT License | разбор PDF-резюме |
| pydantic | `pydantic>=2.9,<3` | 2.13.5 | MIT | схемы запросов и ответов, валидация |
| pydantic-settings | `pydantic-settings>=2.6` | 2.15.0 | MIT | настройки из переменных окружения |
| PyJWT | `pyjwt[crypto]>=2.9` | 2.15.1 | MIT | JWT сессий и проверка ID-токенов Keycloak (JWKS) |
| python-multipart | `python-multipart>=0.0.12` | 0.0.32 | Apache-2.0 | загрузка файлов (PDF-резюме) |
| reportlab | `reportlab>=4.2` | 5.0.1 | BSD License | генерация PDF-профиля кандидата |
| SQLAlchemy | `sqlalchemy[asyncio]>=2.0.36,<2.1` | 2.0.54 | MIT | ORM, асинхронный доступ к PostgreSQL |
| uvicorn | `uvicorn[standard]>=0.30` | 0.54.0 | BSD-3-Clause | ASGI-сервер |
| pytest | `pytest>=8.3` | только в dev-окружении | — | автотесты |
| ruff | `ruff>=0.7` | только в dev-окружении | — | линтер и форматтер |
| mypy | `mypy>=1.13` | только в dev-окружении | — | проверка типов |

Транзитивные: annotated-doc 0.0.5 (MIT), annotated-types 0.8.0 (MIT), anyio 4.15.1 (MIT), certifi 2026.7.22 (MPL-2.0), cffi 2.1.1 (MIT-0), charset-normalizer 3.5.2 (MIT), click 8.5.0 (BSD-3-Clause), cryptography 50.0.2 (Apache-2.0 OR BSD-3-Clause), dnspython 2.8.0 (ISC), greenlet 3.5.6 (MIT AND PSF-2.0), h11 0.16.0 (MIT), httpcore 1.0.9 (BSD-3-Clause), httptools 0.8.0 (MIT), idna 3.20 (BSD-3-Clause), Mako 1.4.3 (MIT), MarkupSafe 3.0.4 (BSD-3-Clause), opentelemetry-api 1.45.1 (Apache-2.0), pdfminer.six 20260107 (MIT), pillow 12.3.0 (MIT-CMU), pycparser 3.0 (BSD-3-Clause), pydantic_core 2.46.5 (MIT), pypdfium2 5.14.0 (BSD-3-Clause, Apache-2.0, dependency licenses), python-dotenv 1.2.4 (BSD-3-Clause), PyYAML 6.0.3 (MIT), starlette 1.7.0 (BSD-3-Clause), typing_extensions 4.16.0 (PSF-2.0), typing-inspection 0.4.4 (MIT), uvloop 0.23.0 (MIT License), watchfiles 1.3.0 (MIT), websockets 17.2 (BSD-3-Clause).

### Мок реестра ФСП (`services/fsp-registry-mock/requirements.txt`)

Python 3.12.15 (в образе). Прямых зависимостей: 3, всего с транзитивными: 14.

| Пакет | Объявлено | Установлено | Лицензия | Зачем |
|---|---|---|---|---|
| fastapi | `fastapi==0.142.2` | 0.142.2 | MIT | веб-фреймворк API, OpenAPI/Swagger |
| pydantic | `pydantic==2.13.5` | 2.13.5 | MIT | схемы запросов и ответов, валидация |
| uvicorn | `uvicorn==0.54.0` | 0.54.0 | BSD-3-Clause | ASGI-сервер |

Транзитивные: annotated-doc 0.0.5 (MIT), annotated-types 0.8.0 (MIT), anyio 4.15.1 (MIT), click 8.5.0 (BSD-3-Clause), h11 0.16.0 (MIT), idna 3.20 (BSD-3-Clause), opentelemetry-api 1.45.0 (Apache-2.0), pydantic_core 2.46.5 (MIT), starlette 1.7.0 (BSD-3-Clause), typing_extensions 4.16.0 (PSF-2.0), typing-inspection 0.4.4 (MIT).

### Фронтенд (`frontend/package.json`, версии из `package-lock.json`)

**Попадают в сборку:**

| Пакет | Объявлено | Установлено | Лицензия | Зачем |
|---|---|---|---|---|
| @fontsource/inter | `^5.3.0` | 5.3.0 | OFL-1.1 | шрифт Inter (брендбук ФСП), без CDN |
| @fontsource/jetbrains-mono | `^5.3.0` | 5.3.0 | OFL-1.1 | шрифт JetBrains Mono (брендбук ФСП), без CDN |
| @tanstack/react-query | `^5.104.1` | 5.104.1 | MIT | запросы к API и кэш |
| clsx | `^2.1.1` | 2.1.1 | MIT | склейка CSS-классов |
| lucide-react | `^1.52.0` | 1.52.0 | ISC | иконки |
| react | `^18.3.1` | 18.3.1 | MIT | UI |
| react-dom | `^18.3.1` | 18.3.1 | MIT | UI (рендер в браузере) |
| react-router | `^7.18.4` | 7.18.4 | MIT | маршруты кабинетов |
| recharts | `^3.10.1` | 3.10.1 | MIT | графики (валидация, дашборды) |
| tailwind-merge | `^3.7.0` | 3.7.0 | MIT | склейка классов Tailwind |

**Для разработки и сборки:**

| Пакет | Объявлено | Установлено | Лицензия | Зачем |
|---|---|---|---|---|
| @eslint/js | `^10.0.1` | 10.0.1 | MIT | линтер |
| @tailwindcss/vite | `^4.3.3` | 4.3.3 | MIT | Tailwind для Vite |
| @testing-library/dom | `^10.4.2` | 10.4.2 | MIT | тесты компонентов |
| @testing-library/jest-dom | `^7.0.1` | 7.0.1 | MIT | проверки DOM в тестах |
| @testing-library/react | `^16.3.3` | 16.3.3 | MIT | тесты компонентов |
| @testing-library/user-event | `^14.6.7` | 14.6.7 | MIT | клики и ввод в тестах |
| @types/node | `^22.20.5` | 22.20.5 | MIT | типы Node.js |
| @types/react | `^18.3.31` | 18.3.31 | MIT | типы React |
| @types/react-dom | `^18.3.7` | 18.3.7 | MIT | типы React DOM |
| @vitejs/plugin-react | `^6.1.2` | 6.1.2 | MIT | React для Vite |
| eslint | `^10.12.0` | 10.12.0 | MIT | линтер |
| eslint-plugin-react-hooks | `^7.1.1` | 7.1.1 | MIT | линтер хуков React |
| eslint-plugin-react-refresh | `^0.5.7` | 0.5.7 | MIT | линтер Fast Refresh |
| globals | `^17.13.0` | 17.13.0 | MIT | линтер (глобальные имена) |
| jsdom | `^30.1.2` | 30.1.2 | MIT | DOM для тестов |
| msw | `^2.15.0` | 2.15.0 | MIT | моки API в браузере (прототип без бэкенда) |
| openapi-typescript | `^7.13.0` | 7.13.0 | MIT | TS-типы из OpenAPI |
| tailwindcss | `^4.3.3` | 4.3.3 | MIT | стили |
| typescript | `~5.9.3` | 5.9.3 | Apache-2.0 | типизация |
| typescript-eslint | `^8.71.1` | 8.71.1 | MIT | линтер TypeScript |
| vite | `^8.3.2` | 8.3.2 | MIT | сборка и dev-сервер |
| vitest | `^5.0.3` | 5.0.3 | MIT | автотесты фронтенда |

Всего пакетов в lock-файле: 410 (в сборку — 56, только для разработки — 354).

| Лицензия | В сборку | Для разработки |
|---|---|---|
| MIT | 40 | 269 |
| ISC | 12 | 20 |
| MPL-2.0 | 0 | 24 |
| Apache-2.0 | 0 | 19 |
| BSD-2-Clause | 0 | 8 |
| BSD-3-Clause | 1 | 3 |
| BlueOak-1.0.0 | 0 | 4 |
| (MIT OR CC0-1.0) | 0 | 2 |
| MIT-0 | 0 | 2 |
| OFL-1.1 | 2 | 0 |
| CC-BY-4.0 | 0 | 1 |
| CC0-1.0 | 0 | 1 |
| MIT AND ISC | 1 | 0 |
| Python-2.0 | 0 | 1 |

Лицензии вне списка MIT/BSD/Apache/ISC/PSF (проверены вручную, все открытые): @fontsource/inter 5.3.0 (OFL-1.1); @fontsource/jetbrains-mono 5.3.0 (OFL-1.1).

## Образы Docker

| Образ (тег) | Точная версия | Лицензия | Роль | Где используется |
|---|---|---|---|---|
| `axllent/mailpit:latest` | 1.31.4 | MIT | почта в разработке и на демо-стенде | docker-compose.yml, infra/stand/compose.yml |
| `caddy:2-alpine` | образ не скачан локально | Apache-2.0 | HTTPS (Let's Encrypt), обратный прокси и статика фронта на стенде | infra/stand/compose.yml |
| `ghcr.io/ggml-org/llama.cpp:server-b11541` | b11541 | MIT | локальная LLM: сервер llama.cpp с моделью Qwen2.5-1.5B-Instruct (Apache-2.0) | docker-compose.yml, infra/stand/compose.yml |
| `node:22-alpine` | 22.23.3 (по образу `fsp-talent-frontend`) | MIT | dev-сервер фронта и сборка статики | frontend/Dockerfile, infra/stand/deploy.sh |
| `postgres:16-alpine` | 16.15 | PostgreSQL License | СУБД | docker-compose.yml, infra/stand/compose.yml |
| `python:3.12-slim` | 3.12.15 (по образу `fsp-talent-backend`) | PSF-2.0 | база образов backend и мока реестра | backend/Dockerfile, services/fsp-registry-mock/Dockerfile |
| `quay.io/keycloak/keycloak:25.0` | 25.0.6 | Apache-2.0 | ФСП ID: OIDC-провайдер, realm fsp | docker-compose.yml, infra/stand/compose.yml |

Собственные образы: `backend` (python:3.12-slim + зависимости бэкенда), `fsp-registry-mock` (python:3.12-slim), `frontend` (node:22-alpine, только для dev). На стенде фронт собирается в статику одноразовым контейнером `node:22-alpine` и раздаётся Caddy.

# fsp-talent

Платформа подбора IT-специалистов с верифицированным профилем достижений участника ФСП.
Спецтрек ФСП, ЛЦТ 2026.

Работодатель описывает потребность, получает подборку по **категориям** (специализация × грейд),
подтверждённым адаптивным тестом и достижениями ФСП, и приглашает кандидата с зарплатной вилкой.
До принятия приглашения профиль кандидата обезличен.

Три роли: соискатель (`candidate`), рекрутер (`recruiter`), администратор (`admin`).

## Быстрый старт

Нужен Docker (Docker Desktop, 8 ГБ памяти достаточно).

```bash
cp .env.example .env          # необязательно: без .env работают значения по умолчанию
docker compose up --build     # весь стек
```

Только бэкенд (без фронтенда, Keycloak и мока реестра):

```bash
docker compose up --build postgres backend mailpit
```

Проверка: http://localhost:18000/api/health → `{"status": "ok", "db": "ok", ...}`,
Swagger — http://localhost:18000/api/docs.

Остановить: `docker compose -p fsp-talent down` (с удалением БД — `down -v`).

## Сервисы и порты

| Сервис | Адрес на хосте | Что это |
|---|---|---|
| backend | http://localhost:18000/api | FastAPI; Swagger `/api/docs`, схема `/api/openapi.json` |
| frontend | http://localhost:15173 | React + Vite (dev-сервер) |
| postgres | localhost:15432 | PostgreSQL 16, БД `fsp_talent`, пользователь `fsp` / `fsp` |
| mailpit | http://localhost:18025 (SMTP 11025) | письма в разработке |
| keycloak | http://localhost:18180 | вход и привязка через ФСП ID, realm `fsp`, админ `admin` / `admin` |
| fsp-registry-mock | http://localhost:18100 | мок реестра достижений ФСП |

У каждого сервиса есть healthcheck. Бэкенд при старте применяет миграции (`alembic upgrade head`).

## Демо-учётки

| Роль | Почта | Пароль | Кто это |
|---|---|---|---|
| Соискатель | candidate@example.com | demo1234 | Backend · Middle, с ФСП ID, есть приглашения и задание |
| Соискатель без ФСП | candidate.nofsp@example.com | demo1234 | Frontend · Junior, истории ФСП нет |
| Рекрутер | recruiter@example.com | demo1234 | компания «Северный код» |
| Администратор | admin@example.com | demo1234 | оператор платформы |

Все люди, компании и почты в демо-данных вымышлены (`@example.com`).

## Авторизация до волны 2: заголовок `X-Demo-Role`

Настоящая авторизация (JWT, argon2, подтверждение почты) появится в волне 2. До неё
API определяет пользователя по заголовкам-заглушкам:

- `X-Demo-Role: candidate | recruiter | admin` — роль. Без заголовка защищённые методы отвечают 401,
  с чужой ролью — 403.
- `X-Demo-User-Id: <id>` — необязательно, id из `data/seed/users.json`. По умолчанию — демо-аккаунт
  роли: соискатель — пользователь 1, рекрутер — 41, админ — 48. Соискатель без ФСП — `26`.

```bash
curl -H "X-Demo-Role: recruiter" http://localhost:18000/api/matching/needs
```

Заглушка выключается переменной `DEMO_AUTH_ENABLED=false`. `POST /api/auth/login` с демо-учёткой
уже отвечает токеном и ставит refresh-cookie, но остальные методы пока смотрят только на заголовки.

## Контракт API v0

- Префикс `/api`, ошибки всегда `{"code": "...", "message": "...", "details": {...}}`.
- У каждого метода описаны модель ответа, примеры и коды ошибок (`responses`).
- Схема выгружается в [`docs/api/openapi.json`](docs/api/openapi.json):
  `python scripts/export_openapi.py` (или `make openapi`). CI проверяет, что файл актуален.
  По этой схеме фронтенд генерирует TS-типы (`openapi-typescript`).
- Заглушки отдают данные из `data/seed/*.json` и **не сохраняют** изменения: POST/PUT возвращают
  результат, но фикстуры не меняются.

Правила видимости, отражённые в схемах:

- рекрутер видит обезличенный профиль (`CandidateCard`, `AnonymousCandidateProfile`): псевдоним
  «Кандидат #XXXX», категория, темы теста, стек, бейджи ФСП — без ФИО, почты, телефона, мессенджеров
  и минимальной зарплаты;
- контакты — отдельный объект (`contacts`, `candidate_contacts`), он заполняется только после
  принятия приглашения или отклика кандидата на вакансию компании;
- зарплата «от–до» обязательна в приглашении, вакансии и потребности, «от» ≤ «до»
  (ошибка `salary_range_invalid` в `details.errors`); вилка ниже минимума кандидата —
  `422 salary_below_expectations` без раскрытия суммы;
- статусы приглашения: `sent`, `viewed`, `accepted`, `declined`, `expired`, `withdrawn`;
  недопустимый переход — `409 invalid_transition`; причины отказа — enum `DeclineReason`.

## Фикстуры `data/seed`

Один источник данных для моков фронтенда (MSW) и заглушек бэкенда. Генерируются детерминированно:

```bash
python scripts/seed/generate_fixtures.py    # make fixtures
```

Каждый файл — массив объектов с `id`; поля совпадают со схемами API (это проверяет `tests/test_fixtures.py`).

| Файл | Схема API | Примечание |
|---|---|---|
| `specializations`, `grades`, `categories`, `topics`, `skills`, `decline_reasons` | `Specialization`, `Grade`, `Category`, `Topic`, `Skill`, `DeclineReasonItem` | справочники |
| `users` | `UserRecord` | 40 соискателей, 7 рекрутеров, 2 админа |
| `demo_accounts` | — | учётки для входа (не API) |
| `candidates` | `CandidateProfile` | полный профиль (видит сам кандидат). Рекрутеру — проекция `CandidateCard`, см. `backend/app/candidates/service.py::to_card` |
| `companies`, `recruiters` | `Company`, `Recruiter` | 3 компании |
| `invitations` | `InvitationRecord` | API-ответ `Invitation` = запись + `candidate`, `candidate_contacts`, `recruiter_contacts` по роли |
| `invitation_events` | `InvitationEvent` | |
| `vacancies` | `Vacancy` | |
| `applications` | `ApplicationRecord` | API-ответ `Application` = запись + `candidate`, `candidate_contacts` (для рекрутера) |
| `needs` | `Need` | потребности рекрутеров |
| `items` | `ItemDetail` | 30 шаблонов; в списке (`ItemSummary`) нет `description` и `preview_variants` |
| `test_sessions`, `grade_history`, `survey_questions` | `TestSession`, `GradeHistoryEntry`, `SurveyQuestion` | |
| `fsp_achievements` | `FspAchievement` | у FSP-000001…020; FSP-000031…035 привязаны без истории |
| `regular_tasks`, `task_submissions` | `RegularTask`, `TaskSubmission` | |
| `reports`, `audit_log` | `Report`, `AuditEntry` | |
| `platform_settings` | `PlatformSettings` | один объект `id = "default"` |
| `validation_charts`, `vacancy_tests` | `ValidationChart`, `VacancyTestResult` | графики валидации — заглушка (`is_stub: true`) |

## Структура репозитория

```
backend/                 FastAPI-приложение
  app/
    core/                настройки, БД, ошибки, логирование, заглушка авторизации
    common/              общие enum'ы, схемы, чтение фикстур
    auth users catalog candidates companies testing fsp
    matching invitations vacancies tasks admin eval
                         модули: router / service / repository / models / schemas
    testing/engine/      адаптивный движок теста (отдельный трек)
  alembic/               миграции
  tests/
frontend/                React + TypeScript + Vite
services/fsp-registry-mock/   мок реестра ФСП
infra/keycloak/          импорт realm `fsp`
data/seed/               фикстуры (моки фронта = сид бэкенда)
docs/architecture/       ER-диаграмма и архитектура
docs/api/                выгрузка OpenAPI
scripts/                 генератор фикстур, выгрузка OpenAPI
```

## Разработка бэкенда

```bash
cd backend
pip install -e ".[dev]"               # Python 3.12+
docker compose up -d postgres          # БД на localhost:15432
DATABASE_URL=postgresql+asyncpg://fsp:fsp@localhost:15432/fsp_talent alembic upgrade head
DATABASE_URL=postgresql+asyncpg://fsp:fsp@localhost:15432/fsp_talent pytest
ruff check . && ruff format --check . && mypy
```

Или из корня: `make check` (lint + mypy + pytest + проверка OpenAPI).

## Лицензия

MIT — см. [LICENSE](LICENSE).

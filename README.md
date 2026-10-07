# fsp-talent

Платформа подбора IT-специалистов с верифицированным профилем достижений участника ФСП.
Спецтрек ФСП, ЛЦТ 2026.

**Стенд:** https://159-194-200-243.sslip.io · **Swagger:** https://159-194-200-243.sslip.io/api/docs

Работодатель описывает потребность, получает подборку по **категориям** (специализация × грейд),
подтверждённым адаптивным тестом и достижениями ФСП, видит объяснение «почему в подборке» и сам
приглашает кандидата с зарплатной вилкой. До принятия приглашения профиль кандидата обезличен,
после — обе стороны видят контакты. Отклик кандидата на вакансию — дополнительный сценарий.

Три роли: соискатель (`candidate`), рекрутер (`recruiter`), администратор (`admin`).

## Документация

Сопроводительная документация (все 8 пунктов ТЗ 3.4) — [`docs/solution/`](docs/solution/index.md),
одним файлом — [PDF](docs/solution/fsp-talent-documentation.pdf) и
[DOCX](docs/solution/fsp-talent-documentation.docx):

1. [Архитектура](docs/solution/01_architecture.md) — роли, контейнеры, модули, экраны, потоки, безопасность
2. [Механика тестирования](docs/solution/02_testing.md) — параметрические шаблоны, IRT, адаптивный тест, детектор утечек
3. [Механика подбора и категоризации](docs/solution/03_matching.md) — категории, ранжирование, объяснимость, приглашения
4. [Валидация и результаты](docs/solution/04_validation.md) — синтетика с известной правдой: категория точно 78,8%, precision@10 0,486 против 0,253 у поиска по ключевым словам
5. [Интеграция с реестром ФСП](docs/solution/05_fsp_integration.md) — ФСП ID (Keycloak), API реестра, вебхук
6. [API](docs/solution/06_api.md) и [таблица методов по ролям](docs/solution/api_endpoints.md)
7. [Библиотеки и компоненты с версиями](docs/solution/07_libraries.md)
8. [Сборка, развёртывание и запуск](docs/solution/08_deployment.md)

## Быстрый старт

Нужен Docker с Compose v2 (Docker Desktop, 4–8 ГБ памяти).

```bash
git clone https://github.com/Vadik145-beep/fsp-talent.git && cd fsp-talent
cp .env.example .env              # и поставить VITE_USE_MOCKS=false — фронт на реальном API
docker compose up -d --build      # весь стек; первый запуск — несколько минут
docker compose exec backend python -m app.seed   # демо-данные (идемпотентно)
```

Открыть http://localhost:15173. Проверка API: http://localhost:18000/api/health →
`{"status": "ok", "db": "ok", ...}`. Остановить: `docker compose down` (с удалением БД — `down -v`).

Только прототип интерфейса на моках, без бэкенда: `cd frontend && npm ci && npm run dev`.

Подробно (переменные окружения, стенд на сервере, частые проблемы) —
[`docs/solution/08_deployment.md`](docs/solution/08_deployment.md).

## Демо-учётки

| Роль | Почта | Пароль | Кто это |
|---|---|---|---|
| Соискатель | candidate@example.com | demo1234 | Backend · Middle, с ФСП ID, есть приглашения и задание |
| Соискатель без ФСП | candidate.nofsp@example.com | demo1234 | Frontend · Junior, истории ФСП нет |
| Рекрутер | recruiter@example.com | demo1234 | компания «Северный код» |
| Администратор | admin@example.com | demo1234 | оператор платформы |

Тестовые участники ФСП ID (Keycloak): `fsp.user01` … `fsp.user05`, `fsp.nohistory`, пароль
`Fsp-demo-2026`. Все люди, компании и почты в демо-данных вымышлены.

## Сервисы и порты (dev-стек)

| Сервис | Адрес на хосте | Что это |
|---|---|---|
| frontend | http://localhost:15173 | React + Vite |
| backend | http://localhost:18000/api | FastAPI; Swagger `/api/docs`, схема `/api/openapi.json` |
| postgres | localhost:15432 | PostgreSQL 16, БД `fsp_talent`, пользователь `fsp` / `fsp` |
| mailpit | http://localhost:18025 (SMTP 11025) | письма подтверждения и приглашений |
| keycloak | http://localhost:18180 | ФСП ID, realm `fsp`, админ `admin` / `admin` |
| fsp-registry-mock | http://localhost:18100 | мок реестра достижений ФСП |

Стенд на сервере — `infra/stand/` (Caddy + HTTPS на одном адресе, выкладка `deploy.sh`).

## Структура репозитория

```
backend/                 FastAPI-приложение (модульный монолит)
  app/
    core/ common/        настройки, БД, ошибки, безопасность, enum'ы
    auth users catalog candidates companies testing fsp
    matching invitations vacancies tasks admin eval integrations
                         модули: router / service / repository / models / schemas
    testing/engine/      движок адаптивного теста (IRT, CAT, шаблоны, утечки, калибровка)
    nlp/                 разбор резюме, потребностей, вакансий
    seed/                загрузка демо-данных
  alembic/               миграции
  tests/
frontend/                React + TypeScript + Vite
services/fsp-registry-mock/   мок реестра ФСП
infra/keycloak/          realm `fsp` для ФСП ID
infra/stand/             стенд: compose, Caddyfile, deploy.sh
data/seed/               фикстуры (моки фронта = сид бэкенда)
data/samples/            образцы резюме, вакансий, формулировок потребностей
data/validation/         синтетика для валидации, эталон, результаты
docs/                    документация (solution/ — для жюри), OpenAPI, ER-схема, валидация
scripts/                 генератор фикстур, выгрузка OpenAPI, валидация (validation/run_all.py)
```

## Разработка

```bash
cd backend && pip install -e ".[dev]"        # Python 3.12+
make check       # ruff + mypy + pytest + актуальность docs/api/openapi.json (нужна БД на :15432)
make openapi     # выгрузить docs/api/openapi.json
make validate    # валидация: синтетика, симуляции, графики, docs/validation/report.md
cd frontend && npm run gen:api               # TS-типы из OpenAPI
```

Контракт API: префикс `/api`, ошибки всегда `{"code": "...", "message": "...", "details": {...}}`,
авторизация `Authorization: Bearer <JWT>` (вход `POST /api/auth/login`), refresh — httpOnly cookie.
В dev (`DEMO_AUTH_ENABLED=true`) можно вместо токена передать `X-Demo-Role` и `X-Demo-User-Id`.

## Лицензия

MIT — см. [LICENSE](LICENSE).

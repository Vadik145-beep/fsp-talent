# 8. Сборка, развёртывание и локальный запуск

Решение запускается одной командой `docker compose` на любой ОС с Docker. Ниже — три
сценария: **локальный запуск полного стека** (для эксперта), **стенд на сервере**
(как развёрнут https://159-194-200-243.sslip.io) и **разработка**.

## 8.1. Что нужно

| Что | Версия / объём |
|---|---|
| Docker Engine или Docker Desktop с Compose v2 | Docker 24+, Compose 2.24+ (проверено на Docker Desktop, Compose 5.5) |
| Память для Docker | 4 ГБ минимум, 8 ГБ комфортно (лимиты dev-стека в сумме ≈ 3,3 ГБ) |
| Диск | ≈ 5 ГБ под образы |
| git | любой |
| Свободные порты | 18000, 15173, 15432, 18025, 11025, 18180, 18100 (+ 18090 с профилем `llm`) |

Интернет нужен только при первой сборке (образы, pip, npm) и для разовой загрузки файла
модели ≈ 1,1 ГБ. Внешние API и ключи не нужны: LLM — своя открытая модель
(раздел 9), реестр ФСП и Keycloak — свои контейнеры.

## 8.2. Локальный запуск полного стека

```bash
git clone https://github.com/Vadik145-beep/fsp-talent.git
cd fsp-talent

cp .env.example .env
# в .env поменять одну строку — фронт на реальном API вместо моков:
#   VITE_USE_MOCKS=false

docker compose up -d --build                      # первый запуск — 5–15 минут (сборка образов)
                                                  # если упал на «postgres is unhealthy» — повторить
docker compose exec backend python -m app.seed    # демо-данные: учётки, кандидаты, компании, приглашения
docker compose ps                                 # все сервисы — healthy (Keycloak стартует ~1–2 мин)
```

Бэкенд при старте сам применяет миграции (`alembic upgrade head`) и создаёт администратора.
Загрузка демо-данных идемпотентна: повторный запуск ничего не дублирует
(`python -m app.seed --reset` — очистить и залить заново). Банк задач (192 шаблона)
бэкенд кладёт в БД сам при первом обращении к тесту; явно — `docker compose exec backend
python -m app.testing.sync_bank`.

Открыть:

| Что | Адрес |
|---|---|
| Приложение | http://localhost:15173 |
| Swagger API | http://localhost:18000/api/docs |
| Почта (письма подтверждения, приглашений) | http://localhost:18025 |
| Keycloak (ФСП ID), админка `admin` / `admin` | http://localhost:18180 |
| Мок реестра ФСП, Swagger | http://localhost:18100/docs |
| PostgreSQL | `localhost:15432`, БД `fsp_talent`, пользователь `fsp` / `fsp` |

**Демо-учётки** (пароль `demo1234`):

| Роль | Почта | Что показать |
|---|---|---|
| Соискатель | `candidate@example.com` | Backend · Middle, ФСП ID с достижениями, есть приглашения и задание |
| Соискатель без ФСП | `candidate.nofsp@example.com` | Frontend · Junior, истории ФСП нет — путь без штрафа |
| Рекрутер | `recruiter@example.com` | компания «Северный код», потребности и приглашения |
| Администратор | `admin@example.com` | банк задач, детектор утечек, настройки, валидация |

Тестовые участники ФСП ID для привязки (в Keycloak): `fsp.user01` … `fsp.user05`
(с достижениями), `fsp.nohistory` (без истории), пароль `Fsp-demo-2026`.

Новый пользователь регистрируется на `/register`; письмо со ссылкой подтверждения приходит
в Mailpit (http://localhost:18025).

### Проверка работоспособности

```bash
curl http://localhost:18000/api/health
# {"status":"ok","version":"0.1.0","db":"ok","db_revision":"0007_merge_wave5"}

curl -s -H 'Content-Type: application/json' \
  -d '{"email":"recruiter@example.com","password":"demo1234"}' \
  http://localhost:18000/api/auth/login
# {"access_token":"…","token_type":"bearer","expires_in":900,"user":{…,"role":"recruiter"}}

curl http://localhost:18100/health
# {"status":"ok","participants":40,"synthetic":true}
```

Сквозной сценарий в браузере: войти рекрутером → «Потребности» → открыть потребность →
подборка с «почему в подборке» → «Пригласить» (вилка, способ связи) → выйти, войти соискателем
`candidate@example.com` → «Приглашения» → принять → у рекрутера появились контакты.

### Облегчённые варианты

| Задача | Команда |
|---|---|
| Только бэкенд и БД (без фронта и Keycloak) | `docker compose up -d --build postgres backend mailpit fsp-registry-mock` |
| Локальная LLM (как на стенде) | `docker compose --profile llm up -d llm` и в `.env` строки из блока LLM в `.env.example`; затем `docker compose up -d backend` |
| Только прототип интерфейса на моках, без бэкенда | `cd frontend && npm ci && npm run dev` → http://localhost:15173 (`VITE_USE_MOCKS` не задан = моки) |

### Остановка

```bash
docker compose down        # остановить, данные БД сохраняются в томе pgdata
docker compose down -v     # остановить и удалить данные
```

## 8.3. Переменные окружения

`docker-compose.yml` берёт значения из `.env` в корне (шаблон — `.env.example`); без `.env`
работают значения по умолчанию. Основные:

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `VITE_USE_MOCKS` | `true` | `false` — фронт ходит в настоящий API (Vite проксирует `/api` на backend) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `fsp` / `fsp` / `fsp_talent` | учётка и база PostgreSQL |
| `APP_ENV` | `dev` | `dev` / `prod`; вне `dev` refresh-cookie ставится с флагом `Secure` (нужен HTTPS) |
| `LOG_LEVEL` | `INFO` | уровень логов бэкенда |
| `JWT_SECRET` | `change-me-in-production` | ключ подписи JWT — на сервере обязательно свой, 32+ символа |
| `DEMO_AUTH_ENABLED` | `true` | демо-заголовки `X-Demo-Role` вместо JWT; на сервере — `false` |
| `PUBLIC_FRONTEND_URL` | `http://localhost:15173` | адрес фронта для ссылок в письмах и redirect ФСП ID |
| `KEYCLOAK_PUBLIC_URL` | `http://localhost:18180` | адрес Keycloak, который видит браузер |
| `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD` | `admin` / `admin` | админка Keycloak |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | пусто (на стенде `http://llm:8080/v1`, `local`, `qwen2.5-1.5b-instruct`) | OpenAI-совместимый endpoint (`/chat/completions`); пусто — всё на правилах |
| `LLM_JSON_SCHEMA` | `false` (на стенде `true`) | передавать JSON-схему ответа — llama.cpp строит по ней грамматику |
| `LLM_DISPLAY_NAME`, `LLM_LOCAL` | пусто, `false` (на стенде `Qwen2.5-1.5B`, `true`) | подпись модели в админке и признак «работает на нашем сервере» |
| `LLM_DISABLED` | `false` | `true` — модель не вызывается вовсе |

Задаются в compose и обычно не меняются: `DATABASE_URL`, `SMTP_HOST` / `SMTP_PORT` (Mailpit),
`KEYCLOAK_INTERNAL_URL`, `KEYCLOAK_REALM=fsp`, `KEYCLOAK_CLIENT_ID=fsp-talent`,
`FSP_REGISTRY_URL`, `SEED_DIR`.

Дополнительные настройки бэкенда — переменные окружения контейнера `backend`, значения по
умолчанию — в коде. Dev-compose их в контейнер **не передаёт** (действуют значения
по умолчанию); чтобы поменять, добавьте строку в `environment` сервиса `backend`. На стенде
часть из них задаётся в `infra/stand/.env`:

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `SEED_ON_STARTUP` | `false` | загружать демо-данные при старте (на стенде `true`) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | `admin@example.com` / `demo1234` | администратор, создаётся при старте, если такой почты ещё нет; локально всегда `demo1234` (строка `ADMIN_PASSWORD` в корневом `.env` в контейнер не попадает), на стенде — из `infra/stand/.env` |
| `CORS_ORIGINS` | `["http://localhost:15173","http://127.0.0.1:15173"]` | разрешённые origin фронта (JSON-список) |
| `ACCESS_TOKEN_TTL_MIN` / `REFRESH_TOKEN_TTL_DAYS` | `15` / `30` | срок жизни токенов |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_WINDOW_MIN` | `5` / `15` | лимит неудачных входов |
| `SMTP_HOST` / `SMTP_PORT` | `mailpit` / `1025` | SMTP-сервер; на стенде обязательны (`smtp.yandex.ru` / `465`) |
| `SMTP_USER`, `SMTP_PASSWORD` | пусто | логин и пароль приложения почтового ящика |
| `SMTP_SSL` / `SMTP_STARTTLS` | `false` / `false` | SMTPS (порт 465) или STARTTLS (порт 587); на стенде `SMTP_SSL=true` |
| `SMTP_FROM` / `SMTP_FROM_NAME` | пусто (= `SMTP_USER`) / `ФСП · Таланты` | адрес и имя отправителя; Яндекс и Mail.ru принимают только адрес самого ящика |
| `FSP_WEBHOOK_SECRET` | `dev-fsp-webhook-secret` | секрет HMAC вебхука реестра; пусто — вебхук выключен |
| `FSP_REGISTRY_TOKEN` | пусто | сервисный токен для реестра |
| `TESTING_CAT_SE_STOP` / `TESTING_CAT_MAX_ITEMS` / `TESTING_CAT_MIN_ITEMS` | `0.30` / `20` / `6` | правило остановки теста |
| `TESTING_LEAK_SCAN_EVERY` | `50` | детектор утечек после каждой N-й сессии |
| `RESUME_MAX_BYTES` / `RESUME_MAX_PAGES` | 5 МБ / `10` | ограничения PDF-резюме |
| `LLM_DRAFT_TIMEOUT_SEC` / `LLM_NEED_TIMEOUT_SEC` / `LLM_RESUME_TIMEOUT_SEC` | `90` / `25` / `40` | таймауты вызова модели: черновик задачи, разбор потребности, дозаполнение резюме; по таймауту — правила |
| `LLM_MAX_DRAFTS` | `2` | сколько черновиков задач на одну вакансию пишет модель (остальные — из словаря тем) |
| `TASKS_FRESHNESS_ANSWER_BONUS` / `TASKS_FRESHNESS_GRADE_BASE` / `TASKS_FRESHNESS_GRADE_PER_POINT` | `0.08` / `0.04` / `0.03` | прибавки свежести профиля за ответ и за оценку 0–3 |
| `TASKS_FRESHNESS_HALF_LIFE_DAYS` / `TASKS_MAX_ASSIGN_PER_RUN` | `30` / `50` | полураспад свежести; сколько кандидатов получают задание за проход |
| `INTEGRATIONS_WEBHOOK_MAX_ATTEMPTS` / `INTEGRATIONS_WEBHOOK_TIMEOUT_SEC` | `5` / `5` | попытки доставки вебхука ATS и таймаут запроса |
| `INTEGRATIONS_ALLOW_PRIVATE_URLS` | `true` | разрешить адреса localhost и частных сетей в вебхуках; на проде — `false` (защита от SSRF) |

Пороги θ, кулдауны, квота и срок приглашений, веса ранжирования — не переменные, а настройки
платформы в БД: их меняет администратор на экране «Справочники».

## 8.4. Стенд на сервере (один сервер, Caddy + HTTPS)

Так развёрнут https://159-194-200-243.sslip.io. Файлы — `infra/stand/`: `compose.yml`
(Caddy, backend, PostgreSQL, Keycloak, мок реестра, локальная LLM `llm`), `Caddyfile`, `.env.example`,
`deploy.sh`; скрипт скачивания модели — `infra/llm/start.sh`. Сервер: 2 vCPU / 4 ГБ, Ubuntu с Docker, открыты порты 80 и 443. Домен —
бесплатный `<ip-через-дефисы>.sslip.io`, сертификат Let's Encrypt Caddy получает сам.

Один адрес обслуживает всё:

| Путь | Куда |
|---|---|
| `/` | статика фронта (`infra/stand/site`, собранная с `VITE_USE_MOCKS=false`) |
| `/api/*` | backend |
| `/kc/*` | Keycloak (`KC_HTTP_RELATIVE_PATH=/kc`) |

Первый запуск:

```bash
git clone https://github.com/Vadik145-beep/fsp-talent.git /opt/fsp-talent/app
cd /opt/fsp-talent/app/infra/stand
cp .env.example .env
# в .env: STAND_HOST=<ваш-ip-через-дефисы>.sslip.io и случайные секреты:
#   POSTGRES_PASSWORD, JWT_SECRET (32+ символа), KEYCLOAK_ADMIN_PASSWORD, FSP_WEBHOOK_SECRET
#   (например: openssl rand -hex 24); ADMIN_PASSWORD — пароль администратора;
#   SMTP_USER / SMTP_PASSWORD — почтовый ящик и пароль приложения (без них стенд не стартует)
chmod 600 .env
./deploy.sh
```

`deploy.sh` делает: `git reset --hard origin/main` → сборку фронта в одноразовом контейнере
`node:22-alpine` с `VITE_USE_MOCKS=false` → копирование `frontend/dist` в `infra/stand/site` →
`docker compose --env-file .env up -d --build` → `python -m app.testing.sync_bank`. Повторный
запуск — обновление стенда до свежего `main`. Скрипт рассчитан на путь `/opt/fsp-talent/app`
(переменная `APP` в начале файла).

**Локальная LLM на стенде.** Контейнер `llm` (образ `ghcr.io/ggml-org/llama.cpp:server-b11541`)
берёт модель из папки сервера `/opt/fsp-talent/models` (переменная `LLM_MODELS_DIR`), смонтированной
только для чтения. Файл кладётся один раз:

```bash
mkdir -p /opt/fsp-talent/models && cd /opt/fsp-talent/models
curl -fL -o qwen2.5-1.5b-instruct-q4_k_m.gguf https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf
echo "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e  qwen2.5-1.5b-instruct-q4_k_m.gguf" | sha256sum -c -
```

Сервер llama.cpp: контекст 4096, 2 потока, один запрос за раз,
лимит памяти 1,8 ГБ, приоритет процессора ниже, чем у бэкенда и базы. Порт наружу не открыт.
Бэкенд модель не ждёт: пока она загружается или если контейнер остановлен, всё работает на
правилах. Переменные `LLM_*` у бэкенда заданы в `compose.yml` по умолчанию, в `.env` их можно
не писать; выключить — `LLM_DISABLED=true` или `docker compose stop llm`. Подробно — раздел 9.

```bash
docker compose --env-file .env logs -f llm     # загрузка модели
docker compose --env-file .env exec llm curl -s localhost:8080/health   # {"status":"ok"}
```

Отличия стенда от dev-стека: `APP_ENV=prod` (secure-cookie), `DEMO_AUTH_ENABLED=false`
(только JWT), `SEED_ON_STARTUP=true` (демо-данные загружаются сами), фронт — собранная
статика, а не Vite; наружу открыт только Caddy; письма уходят настоящей почтой через
SMTP-ящик из `.env` (Mailpit на стенде нет).

Проверка стенда:

```bash
curl https://<STAND_HOST>/api/health
docker compose -f infra/stand/compose.yml --env-file infra/stand/.env ps
docker compose -f infra/stand/compose.yml --env-file infra/stand/.env logs -f backend
```

Резервная копия БД:
`docker compose --env-file .env exec -T postgres pg_dump -U fsp fsp_talent > backup.sql`.

## 8.5. Разработка

Бэкенд без Docker (Python 3.12+), БД — из compose:

```bash
docker compose up -d postgres
cd backend
pip install -e ".[dev]"
export DATABASE_URL=postgresql+asyncpg://fsp:fsp@localhost:15432/fsp_talent
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 18000
```

Проверки (то же делает CI, `.github/workflows/ci.yml`):

```bash
make check      # ruff + mypy + pytest + актуальность docs/api/openapi.json
cd frontend && npm ci && npm run lint && npm run typecheck && npm test -- --run && npm run build
```

Полезное: `make openapi` — выгрузить схему API; `cd frontend && npm run gen:api` — TS-типы
из схемы; `make fixtures` — перегенерировать `data/seed`; `make validate` — полная валидация
(данные, симуляции, графики, `docs/validation/report.md`; нужен `matplotlib`); симуляция
движка теста — `PYTHONPATH=backend python -m app.testing.engine.simulate --seed 20261011`.

## 8.6. Периодические задачи (cron)

Бэкенд не держит фоновых потоков: периодические работы — отдельные команды, которые
запускаются в контейнере `backend` (их же можно вызвать без cron — см. последнюю строку).

| Команда | Что делает | Как часто |
|---|---|---|
| `python -m app.tasks daily` | просрочить регулярные задания без ответа, снизить свежесть профилей (полураспад 30 дней) | раз в сутки |
| `python -m app.tasks distribute` | дополнить задачи недели кандидатов до трёх от разных компаний | раз в неделю (понедельник) |
| `python -m app.integrations` | повторно отправить вебхуки ATS, у которых подошло время повтора | раз в минуту |
| `POST /api/tasks/jobs/run?job=daily` (или `distribute`, `tick`) | то же для заданий по запросу администратора | вручную |

Пример crontab на сервере стенда (`crontab -e` пользователя с доступом к Docker):

```cron
C="docker compose -f /opt/fsp-talent/app/infra/stand/compose.yml --env-file /opt/fsp-talent/app/infra/stand/.env exec -T backend"
15 3 * * *  $C python -m app.tasks daily
0 9 * * 1   $C python -m app.tasks distribute
* * * * *   $C python -m app.integrations
```

Локально (dev-стек) — `docker compose exec backend python -m app.tasks daily` и т.д.
Повторный или пропущенный запуск безопасен: снижение свежести считается по времени
с прошлого запуска, раздача не выдаёт задание дважды, доставка вебхука не повторяется
после успеха. Compose-файл стенда cron не поднимает — расписание ставится на хосте,
как показано выше.

## 8.7. Частые проблемы

| Симптом | Причина и решение |
|---|---|
| `port is already allocated` | порт занят другим процессом — освободите его или поменяйте левую часть `ports` в `docker-compose.yml` |
| Фронт показывает данные, но вход демо-учёткой «не настоящий», в шапке плашка «Смотреть как» | фронт на моках: в `.env` нет `VITE_USE_MOCKS=false`; после правки — `docker compose up -d frontend` (пересоздать контейнер) |
| Вход демо-учёткой работает, но кабинеты пустые (нет кандидатов, потребностей, приглашений) | не загружены демо-данные: `docker compose exec backend python -m app.seed` (в dev вход демо-учёток работает и до загрузки — за счёт режима `DEMO_AUTH_ENABLED`) |
| Первый `docker compose up` завершился ошибкой `dependency failed to start: container …-postgres-1 is unhealthy` | на медленном диске первичная инициализация PostgreSQL дольше таймаута healthcheck; подождите минуту и повторите `docker compose up -d` — данные уже на месте |
| Новый пользователь не может войти: `403 email_not_verified` | подтвердите почту по ссылке из письма в Mailpit (http://localhost:18025) |
| Тест не стартует: `409 bank_empty` | банк задач не синхронизирован: `docker compose exec backend python -m app.testing.sync_bank` |
| Keycloak долго `starting`, вход через ФСП ID отвечает 503 | Keycloak стартует 1–2 минуты и требует до 1 ГБ памяти; подождите или увеличьте память Docker. Основной вход работает без Keycloak |
| После перезагрузки страницы на сервере без HTTPS сессия теряется | при `APP_ENV=prod` refresh-cookie только для HTTPS; локально используйте `APP_ENV=dev` или стенд с Caddy |
| Фронт на другом адресе получает ошибку CORS | добавьте адрес в `CORS_ORIGINS` (JSON-список) |
| Не хватает памяти на маленьком сервере | лимиты заданы `mem_limit` в compose; на 4 ГБ включите swap 2 ГБ |
| Черновики задач и разбор помечены «по словарю» / `parser: rules`, хотя LLM включена | модель не поднялась (нет файла в `/opt/fsp-talent/models`?) или ещё загружается: `docker compose logs llm`; после `{"status":"ok"}` на `/health` новые запросы пойдут в модель |
| `llm` перезапускается с `failed to load model` | файла модели нет или он битый: скачайте заново и сверьте SHA-256 (команды выше) |

# Банк задач: Backend

30 параметрических шаблонов (T4.3). Код: `backend/app/testing/engine/bank/backend/`,
тесты: `backend/tests/engine/test_bank_backend_*.py`. Примеры из `bank_examples`
(сложность циклов, число строк JOIN) сюда не входят и не дублируются.

Каждый шаблон даёт от 100 разных вариантов на 400 seed (проверяет тест состава), ответ
вычисляет генератор. Стартовые `a`, `b` заданы экспертно по грейду и уточняются калибровкой.

## Шаблоны

Как сверен ответ:
- **Python** — код варианта выполняется настоящим интерпретатором (`exec`), результат
  сравнивается с ключом;
- **SQLite** — таблицы из условия загружаются в SQLite, запрос выполняется как есть;
- **PostgreSQL** — расписание из условия разыгрывается в двух сессиях PostgreSQL 16
  (необязательный тест, нужен `FSP_BANK_PG_DSN`);
- **модель** — вторая, независимая реализация в тесте (другой алгоритм, разбор текста варианта);
- **вручную** — ключ сверен по документации, в тесте проверяется эталонная таблица.

| id | тема | формат | грейд | a | b | что проверяет | как сверен ответ |
|---|---|---|---|---|---|---|---|
| backend.binary_search_steps | algorithms | numeric | intern | 1.1 | −1.4 | трассировка бинарного поиска: сколько итераций | Python |
| backend.ds_choice | algorithms | single_choice | intern | 1.0 | −1.6 | выбор структуры (set, deque, heapq, dict, стек, Counter) под задачу | вручную (сложность операций по докам Python) |
| backend.complexity_scaling | algorithms | numeric | junior | 1.2 | −0.6 | как вырастет время при росте n для O(n), O(n²), O(n log n), O(log n), O(2ⁿ) | модель (формула через math) |
| backend.py_slicing | python | code_output | intern | 1.0 | −1.5 | индексы, срезы, шаг, отрицательный шаг, срез за границей | Python |
| backend.py_mutable_default | python | code_output | junior | 1.3 | −0.5 | изменяемый аргумент по умолчанию, `is`, исправленная версия с None | Python |
| backend.py_late_binding | python | code_output | middle | 1.4 | 0.4 | позднее связывание в замыканиях, `i=i`, фабрика, область видимости генератора списка | Python |
| backend.sql_where_filter | sql | numeric | intern | 1.1 | −1.2 | приоритет AND/OR, BETWEEN, `<> 0` и `= NULL` с NULL, NOT IN с NULL | SQLite |
| backend.sql_group_having | sql | code_output | junior | 1.3 | −0.4 | WHERE до группировки, HAVING после, агрегат в HAVING ≠ агрегат в SELECT | SQLite |
| backend.sql_window_rank | sql | code_output | middle | 1.4 | 0.6 | RANK/DENSE_RANK/ROW_NUMBER, PARTITION BY, SUM() OVER с фреймом RANGE и ROWS | SQLite |
| backend.sql_index_usage | sql | multi_choice | middle | 1.3 | 0.7 | левый префикс составного индекса, функции над столбцом, OR, `<>`, IN, диапазон | SQLite (EXPLAIN QUERY PLAN) |
| backend.sql_isolation_read | sql | single_choice | senior | 1.5 | 1.4 | что видит SELECT при READ COMMITTED / REPEATABLE READ / SERIALIZABLE; снимок с первого запроса, нет грязного чтения | PostgreSQL |
| backend.handler_status | http_api | single_choice | intern | 1.0 | −1.3 | порядок проверок в обработчике: 401/403/404/400/422 | Python |
| backend.http_retry_safe | http_api | multi_choice | junior | 1.2 | −0.6 | какие запросы можно повторить после таймаута (идемпотентность методов) | вручную (RFC 9110, 9.2.2) |
| backend.http_conditional | http_api | short_text | middle | 1.3 | 0.3 | ETag, If-None-Match/If-Match (слабое/сильное сравнение), If-Modified-Since, `*`, 304/412/201 | модель (алгоритм RFC 9110, 13.2.2, по тексту запроса) |
| backend.http_cache_control | http_api | single_choice | middle | 1.3 | 0.8 | max-age, no-cache, no-store, private, s-maxage, stale-while-revalidate для браузера и CDN | модель (разбор заголовков) + эталоны |
| backend.pagination_offset | http_api | numeric | middle | 1.2 | 0.5 | дубли и пропуски при OFFSET-пагинации, курсорная пагинация | SQLite |
| backend.async_total_time | concurrency | numeric | junior | 1.3 | −0.3 | время asyncio-кода: await подряд, gather, create_task, wait_for, задача без await | Python (asyncio с виртуальными часами) |
| backend.async_blocking_bug | concurrency | find_bug_line | junior | 1.2 | −0.4 | блокирующий вызов в async (time.sleep, requests, subprocess, pbkdf2) среди корректных to_thread | модель (структурная проверка: единственный вызов без await) |
| backend.lock_order_deadlock | concurrency | multi_choice | senior | 1.5 | 1.2 | взаимоблокировки по порядку вложенных with; общая внешняя блокировка; with подряд | модель (полный перебор чередований двух потоков) |
| backend.lost_update | concurrency | numeric | senior | 1.5 | 1.6 | потерянное обновление: атомарный UPDATE, чтение-запись в приложении, FOR UPDATE, версия строки, RC и RR | PostgreSQL |
| backend.lru_misses | caching_queues | numeric | junior | 1.2 | −0.6 | промахи/попадания LRU и FIFO | Python (`functools.lru_cache`) + модель для FIFO |
| backend.queue_redelivery | caching_queues | single_choice | senior | 1.3 | 1.0 | at-least-once: подтверждение до/после обработки, дедупликация в транзакции | модель (эмуляция брокера по строкам кода) |
| backend.sql_injection_line | security | find_bug_line | intern | 1.1 | −1.3 | где ввод попадает в текст SQL (f-string, %, +, format) среди параметризованных запросов | Python + SQLite (инъекция реально срабатывает) |
| backend.password_hashing | security | single_choice | junior | 1.2 | −0.5 | хранение и проверка пароля (bcrypt/argon2) на Python, Node.js, Go | вручную (OWASP Password Storage) |
| backend.path_traversal | security | single_choice | middle | 1.4 | 0.5 | обход каталога: join с абсолютным путём, startswith без «/», replace("../") | Python |
| backend.retry_backoff_time | distributed_systems | numeric | middle | 1.2 | 0.6 | время до ошибки и число попыток при экспоненциальной паузе с потолком | Python (поддельные часы) |
| backend.idempotency_charges | distributed_systems | numeric | senior | 1.4 | 1.5 | идемпотентные ключи: проверка-потом-запись, уникальный ключ, TTL, двойной клик | модель (эмуляция трёх серверов, SQLite UNIQUE) |
| backend.outbox_crash | distributed_systems | single_choice | senior | 1.4 | 1.7 | падение между записью в БД и событием: commit→publish, publish→commit, outbox+relay | вручную (таблица исходов в тесте) |
| backend.saga_compensation | distributed_systems | ordering | middle | 1.2 | 0.7 | порядок компенсаций в саге после сбоя шага | вручную (проверка обратного порядка в тесте) |
| backend.raft_partition | distributed_systems | single_choice | senior | 1.4 | 1.8 | etcd/Raft при разделении сети: запись, линеаризуемое и serializable-чтение | вручную (правило большинства в тесте) |

Итого: сверено с настоящей системой 17 шаблонов (Python — 10, SQLite — 5, PostgreSQL — 2),
второй независимой реализацией — 7, вручную по документации с эталонами в тестах — 6.

## Покрытие тем × грейдов

| тема | intern | junior | middle | senior | всего |
|---|---|---|---|---|---|
| algorithms | 2 | 1 | — | — | 3 |
| python | 1 | 1 | 1 | — | 3 |
| sql | 1 | 1 | 2 | 1 | 5 |
| http_api | 1 | 1 | 3 | — | 5 |
| concurrency | — | 2 | — | 2 | 4 |
| caching_queues | — | 1 | — | 1 | 2 |
| security | 1 | 1 | 1 | — | 3 |
| distributed_systems | — | — | 2 | 3 | 5 |
| **всего** | **6** | **8** | **9** | **7** | **30** |

Форматы: single_choice 9, numeric 9, code_output 5, multi_choice 3, find_bug_line 2,
short_text 1, ordering 1.

## Как сверялись ответы

- **Python.** Тест запускает код из условия через `exec` и сравнивает вывод или возвращённое
  значение с ключом (150 seed). Для asyncio используется настоящий event loop с виртуальными
  часами: таймеры срабатывают сразу, а время копится — так проверяется точное число секунд
  без ожидания. Для ретраев подменяются `time.sleep` и функция запроса.
- **SQLite.** Таблицы из условия загружаются в базу, запрос из условия выполняется как есть
  (200 seed). Для индексов разбирается `EXPLAIN QUERY PLAN`: `SEARCH … USING INDEX`.
  Конструкции подобраны так, чтобы SQLite и PostgreSQL вели себя одинаково (регистр
  строк, порядок сортировки, фрейм окна по умолчанию). Задача про индексы прямо названа
  задачей про SQLite: в PostgreSQL 18 и MySQL 8 есть skip scan, и ответ мог бы отличаться.
- **PostgreSQL.** `test_bank_backend_postgres.py` разыгрывает расписание из условия в двух
  сессиях; команда, которая ждёт блокировку, выполняется в отдельном потоке. Тест
  необязательный (в CI нет PostgreSQL), запуск:
  ```
  docker run -d --rm --name fsp-bank-pg -e POSTGRES_PASSWORD=pg -p 15499:5432 postgres:16-alpine
  cd backend && FSP_BANK_PG_DSN="postgresql://postgres:pg@127.0.0.1:15499/postgres" pytest -k postgres
  ```
  Нужен пакет `psycopg[binary]` (в зависимости проекта не добавлен).
- **Модели.** Независимые реализации в тестах: перебор всех чередований двух потоков для
  deadlock, алгоритм предусловий RFC 9110 по тексту запроса, разбор Cache-Control,
  эмуляция серверов идемпотентности и брокера сообщений.
- **Вручную.** Источники: документация Python (сложность операций), RFC 9110 (методы,
  условные запросы), RFC 9111 и 5861 (кэш), OWASP Password Storage Cheat Sheet, документация
  PostgreSQL (Transaction Isolation, Explicit Locking), статья о Raft и документация etcd
  (`--consistency`), описание паттернов Transactional Outbox и Saga (microservices.io).

## Ограничения

- Задачи про изоляцию и потерянное обновление сверены с PostgreSQL только при ручном запуске
  теста; в CI работает проверка модели.
- `ds_choice`, `http_retry_safe`, `password_hashing`, `outbox_crash`, `saga_compensation`,
  `raft_partition` — знания, а не вычисления; ключ проверен вручную, тест следит за
  согласованностью ключа с эталонной таблицей.
- Равенство вариантов внутри шаблона по сложности — допущение (например, в `lost_update`
  сценарий «атомарный UPDATE» проще, чем «чтение-запись при REPEATABLE READ»). Проверяется
  калибровкой по группам вариантов, при большом разбросе шаблон стоит разделить.

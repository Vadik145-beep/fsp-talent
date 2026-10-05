# Банк задач: QA

30 параметрических шаблонов (T4.3). Код — `backend/app/testing/engine/bank/qa/`, сверка ключей — `backend/tests/engine/test_bank_qa_verify.py`.

Каждый шаблон даёт не меньше 50 разных вариантов, ответ вычисляет генератор. Общие проверки (контракт, ≥ 50 вариантов, позиция верного ответа) — `test_engine_bank_full.py`. Стартовые `a`, `b` заданы экспертно по целевому грейду и уточняются калибровкой.

Как сверен ключ: **система** — настоящей библиотекой или программой (8); **пересчёт** — независимой реализацией в тесте (11); **экспертно** — ответ задан автором, машиной не проверить (11).

Тесты сверки пропускаются, если нужной библиотеки нет (в CI ставятся только зависимости бэкенда). Для полной сверки: `pip install pandas scikit-learn scipy statsmodels jsonschema lxml cssselect pyyaml cryptography`; для bash-шаблонов нужен bash (на Windows — Git Bash).

| id | тема | формат | грейд | a | b | что проверяет | как сверен ключ |
|---|---|---|---|---|---|---|---|
| `qa.pagination_check` | api_testing | numeric | Стажёр | 1.1 | -1.3 | Пагинация: ожидаемое число записей | пересчёт: срезы списка Python |
| `qa.test_level_choice` | automation | single_choice | Стажёр | 1.0 | -1.6 | Какой уровень теста выбрать | экспертно: экспертно |
| `qa.repro_steps_order` | bug_reports | ordering | Стажёр | 0.9 | -1.8 | Шаги воспроизведения бага | экспертно: экспертно |
| `qa.severity_priority` | bug_reports | single_choice | Стажёр | 1.0 | -1.4 | Серьёзность и приоритет дефекта | экспертно: экспертно |
| `qa.equivalence_classes` | test_design | single_choice | Стажёр | 1.2 | -1.5 | Классы эквивалентности | пересчёт: независимый пересчёт классов по условию |
| `qa.test_run_stats` | test_management | numeric | Стажёр | 1.0 | -1.3 | Статистика тестового прогона | пересчёт: независимый пересчёт |
| `qa.curl_method` | api_testing | short_text | Junior | 1.2 | -0.3 | Какой метод отправит curl | система: настоящий curl против локального HTTP-сервера |
| `qa.idempotent_methods` | api_testing | multi_choice | Junior | 1.3 | -0.4 | Идемпотентные и безопасные методы | экспертно: экспертно (RFC 9110) |
| `qa.locator_choice` | automation | single_choice | Junior | 1.3 | -0.4 | Уникальный локатор элемента | система: lxml + cssselect: находится ровно один нужный элемент |
| `qa.bug_report_quality` | bug_reports | multi_choice | Junior | 1.1 | -0.8 | Что не так с баг-репортом | экспертно: экспертно (отчёт собирается из заданных недостатков) |
| `qa.load_test_types` | performance | single_choice | Junior | 1.1 | -0.6 | Виды тестов производительности | экспертно: экспертно |
| `qa.vuln_type` | security | single_choice | Junior | 1.2 | -0.5 | Класс уязвимости по симптому | экспертно: экспертно |
| `qa.sql_where_null` | sql | numeric | Junior | 1.4 | -0.3 | SQL: NULL в условиях и агрегатах | система: SQLite |
| `qa.decision_table` | test_design | single_choice | Junior | 1.2 | -0.7 | Таблица решений | пересчёт: независимое применение таблицы к входным данным |
| `qa.json_contract` | api_testing | multi_choice | Middle | 1.4 | 0.4 | Ответ API против контракта | система: jsonschema по схеме, собранной из контракта |
| `qa.flaky_test_line` | automation | find_bug_line | Middle | 1.4 | 0.5 | Почему тест нестабилен | экспертно: код разбирается ast; строка — экспертно |
| `qa.response_percentile` | performance | numeric | Middle | 1.2 | 0.1 | Перцентили времени ответа | система: numpy.percentile(method='inverted_cdf') |
| `qa.sql_group_having` | sql | code_output | Middle | 1.3 | 0.2 | SQL: результат GROUP BY и HAVING | система: SQLite |
| `qa.sql_query_choice` | sql | single_choice | Middle | 1.4 | 0.5 | SQL: какой запрос находит аномалии | система: SQLite: верный запрос даёт ожидаемое, дистракторы — нет или падают |
| `qa.pairwise_count` | test_design | numeric | Middle | 1.3 | 0.6 | Попарное тестирование: сколько тестов | пересчёт: построение набора из a·b тестов и проверка покрытия всех пар |
| `qa.state_transitions` | test_design | multi_choice | Middle | 1.4 | 0.3 | Диаграмма переходов состояний | пересчёт: независимая симуляция автомата по таблице |
| `qa.defect_metrics` | test_management | numeric | Middle | 1.1 | 0.0 | Метрики дефектов: DRE, плотность, переоткрытия | пересчёт: независимый пересчёт |
| `qa.release_readiness` | test_management | single_choice | Middle | 1.1 | 0.2 | Критерии выхода: можно ли выпускать | пересчёт: независимая проверка критериев |
| `qa.rate_limit` | api_testing | numeric | Senior | 1.4 | 1.3 | Сколько запросов получат 429 | пересчёт: независимая симуляция token bucket и скользящего окна |
| `qa.pytest_fixture_order` | automation | code_output | Senior | 1.5 | 1.4 | Порядок фикстур pytest | система: запуск pytest -s на сгенерированном файле |
| `qa.littles_law` | performance | numeric | Senior | 1.3 | 1.2 | Закон Литтла в нагрузочном тесте | пересчёт: дискретная симуляция закрытой модели нагрузки |
| `qa.load_bottleneck` | performance | single_choice | Senior | 1.3 | 1.1 | Найти узкое место по метрикам | экспертно: экспертно |
| `qa.oauth_pkce_order` | security | ordering | Senior | 1.2 | 1.0 | Поток OAuth 2.0 + PKCE | экспертно: экспертно (RFC 6749, RFC 7636) |
| `qa.vulnerable_line` | security | find_bug_line | Senior | 1.5 | 1.3 | Найди уязвимую строку | экспертно: код разбирается ast; строка — экспертно |
| `qa.regression_scope` | test_management | multi_choice | Senior | 1.2 | 1.0 | Объём регресса по зависимостям | пересчёт: независимый обход графа зависимостей |

## Покрытие: темы × грейды

| тема | Стажёр | Junior | Middle | Senior | всего |
|---|---|---|---|---|---|
| test_design | 1 | 1 | 2 | 0 | 4 |
| bug_reports | 2 | 1 | 0 | 0 | 3 |
| api_testing | 1 | 2 | 1 | 1 | 5 |
| sql | 0 | 1 | 2 | 0 | 3 |
| automation | 1 | 1 | 1 | 1 | 4 |
| test_management | 1 | 0 | 2 | 1 | 4 |
| performance | 0 | 1 | 1 | 2 | 4 |
| security | 0 | 1 | 0 | 2 | 3 |
| **всего** | 6 | 8 | 9 | 7 | 30 |

## Форматы

| формат | шаблонов |
|---|---|
| single_choice | 10 |
| numeric | 8 |
| multi_choice | 5 |
| ordering | 2 |
| code_output | 2 |
| find_bug_line | 2 |
| short_text | 1 |

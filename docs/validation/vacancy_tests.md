# Тест из текста вакансии (T4.8)

Образцы: `data/samples/vacancies/` (5 вакансий, разметка в `*.json`). Режим — правила и словарь тем `app/nlp/vacancy_topics.py`, без LLM (черновики — по заготовкам словаря). Банк — `bank_registry()` (192 шаблона). Отчёт генерирует `python -m app.nlp.validation`; пороги проверяет `backend/tests/test_vacancy_tests.py`.

**Специализация верна: 5 из 5; грейд верен: 5 из 5; ожидаемые темы найдены: 25 из 25.** Тема из `expected_topics` считается найденной, если её слова совпали с подписью или ключевыми словами хотя бы одной найденной темы (это ориентир, не точный эталон).

| Вакансия | Спец. / грейд | Найденные темы (уверенность) | Тест: шаблоны банка [грейд] | Черновики (нет в банке) | Ожидаемые темы |
|---|---|---|---|---|---|
| 01_backend_go_senior.md | ✅ / ✅ | Базы данных и SQL (0.95); Конкурентность и асинхронность (0.95); Очереди и брокеры сообщений (0.95); Язык Go (0.93); Мониторинг и инциденты (0.85); gRPC и контракты API (0.70); Kubernetes: объекты и отладка (0.63); HTTP и REST API (0.55) | backend.sql_isolation_read [senior]; backend.lock_order_deadlock [senior]; backend.queue_redelivery [senior]; devops.burn_rate [senior]; devops.k8s_rollout [senior]; backend.http_cache_control [middle] | Язык Go; gRPC и контракты API | ✅ Go: конкурентность (горутины, каналы, context); ✅ PostgreSQL: транзакции, изоляция, индексы; ✅ Kafka: гарантии доставки и идемпотентность; ✅ gRPC и проектирование API; ✅ Kubernetes: деплой и диагностика |
| 02_frontend_react_middle.md | ✅ / ✅ | React и хуки (0.95); HTML, CSS и адаптивная вёрстка (0.95); Браузер: рендеринг и производительность (0.85); Управление состоянием (Redux) (0.85); TypeScript (0.55); JavaScript и event loop (0.55); Тестирование фронтенда (0.55); Доступность интерфейса (0.55) | frontend.react_list_keys [middle]; frontend.css_flex_distribution [middle]; frontend.cors_preflight [middle]; frontend.ts_compile_error [middle]; frontend.js_this_binding [middle]; frontend.a11y_focusable [intern] | Управление состоянием (Redux); Тестирование фронтенда | ✅ React: хуки и жизненный цикл; ✅ TypeScript: типизация компонентов; ✅ Управление состоянием (Redux Toolkit); ✅ HTML/CSS и адаптивная вёрстка; ✅ Браузер: рендеринг, event loop, производительность |
| 03_mobile_android_junior.md | ✅ / ✅ | Kotlin: основы и null-safety (0.95); Вёрстка экранов (Jetpack Compose / SwiftUI) (0.95); Жизненный цикл Activity/Fragment (0.85); HTTP и REST API (0.63); Работа с сетью и REST API (0.62); Сборка и публикация (0.55); Git: ветки и merge request (0.55); Хранение данных на устройстве (0.48) | mobile.kotlin_collections [junior]; mobile.android_lifecycle [junior]; backend.http_retry_safe [junior]; mobile.retry_backoff [junior]; mobile.android_runtime_permission_flow [junior]; mobile.room_query_result [junior] | Вёрстка экранов (Jetpack Compose / SwiftUI); Git: ветки и merge request | ✅ Kotlin: основы языка и null-safety; ✅ Android: жизненный цикл Activity/Fragment; ✅ Jetpack Compose: вёрстка экранов; ✅ Работа с REST API; ✅ Git: ветки и merge request |
| 04_data_ml_middle.md | ✅ / ✅ | Рекомендательные системы (0.95); Нейросети (PyTorch) (0.85); SQL: оконные функции и JOIN (0.85); Метрики качества и ранжирования (0.85); Статистика и A/B-тесты (0.70); Обработка данных (pandas) (0.70); Вывод моделей в прод (MLOps) (0.70); Классическое ML (scikit-learn) (0.55) | data_ml.conv_output_shape [middle]; backend.sql_index_usage [middle]; data_ml.roc_auc_pairs [middle]; data_ml.ab_ztest [middle]; data_ml.numpy_view_copy [middle]; data_ml.crisp_dm_order [junior]; data_ml.gini_split [middle] | Рекомендательные системы | ✅ Рекомендательные системы и метрики ранжирования; ✅ SQL: оконные функции и JOIN; ✅ Классическое ML (scikit-learn): валидация, переобучение; ✅ PyTorch: обучение нейросетей; ✅ Статистика A/B-тестов |
| 05_devops_middle.md | ✅ / ✅ | Linux: сети, процессы, диагностика (0.95); Мониторинг и инциденты (0.95); CI/CD (0.85); Docker и контейнеризация (0.70); Kubernetes: объекты и отладка (0.62); Инфраструктура как код (Terraform) (0.62); Git: ветки и merge request (0.50) | devops.cidr_subnet [middle]; devops.error_budget [middle]; devops.deploy_strategies [junior]; devops.dockerfile_layers [middle]; devops.k8s_manifest_bug [middle]; devops.terraform_plan [senior] | Git: ветки и merge request | ✅ Linux: сети, процессы, диагностика; ✅ Docker: образы и контейнеризация; ✅ Kubernetes: объекты и отладка; ✅ Terraform: состояние и модули; ✅ CI/CD на GitLab CI |

## Ответ API и расширение контракта

`POST /api/admin/vacancy-tests` сохраняет собранный тест (таблица `vacancy_tests`), `GET` отдаёт список собранных (новые сверху; пока пусто — демо-примеры из фикстур). К форме `VacancyTestResult` добавлены только новые поля:

- `drafts[].item_id` — id черновика в таблице `items` (status=draft, source=llm_vacancy); его одобряет админ (`/api/admin/items/{item_id}/approve`) и шаблон идёт в тесты как непроверочный; `drafts[].origin` — `llm` или `vocabulary`; `drafts[].reused` — черновик по той же теме и грейду уже был, новый не создан;
- `items[].template_id` и `items[].target_grade` — шаблон банка и его грейд (`items[].item_id` — строка `items`; если шаблона там ещё нет, он регистрируется);
- `created_at` — когда собран тест.

Без ключа LLM `parser: rules`, черновики — по заготовкам словаря тем; с ключом черновик пишет LLM (ответ проверяется pydantic, при ошибке — заготовка).

## Объяснение выбора (как его видит админ)

### 01_backend_go_senior.md
- Специализация Backend — по словам: Go, бэкенд, Kafka
- Грейд Senior взят из заголовка вакансии («Senior»)
- Тема «Базы данных и SQL» найдена по словам: PostgreSQL, транзакций, изоляции; грейд Senior совпадает с вакансией
- Тема «Конкурентность и асинхронность» найдена по словам: конкурентности, горутины, каналы; грейд Senior совпадает с вакансией
- Тема «Очереди и брокеры сообщений» найдена по словам: Kafka, брокером, очередями; грейд Senior совпадает с вакансией
- Тема «Мониторинг и инциденты» найдена по словам: Prometheus, Grafana, наблюдаемость; грейд Senior совпадает с вакансией
- Тема «Kubernetes: объекты и отладка» найдена по словам: Kubernetes, под упал; грейд Senior совпадает с вакансией
- Тема «HTTP и REST API» найдена по словам: API; ближайший доступный грейд Middle (шаблонов Senior по теме в банке нет)

### 02_frontend_react_middle.md
- Специализация Frontend — по словам: React, Frontend, TypeScript
- Грейд Middle взят из заголовка вакансии («Middle»)
- Тема «React и хуки» найдена по словам: React, хуки, компонентов; грейд Middle совпадает с вакансией
- Тема «HTML, CSS и адаптивная вёрстка» найдена по словам: HTML, CSS, вёрстка; грейд Middle совпадает с вакансией
- Тема «Браузер: рендеринг и производительность» найдена по словам: браузер, рендеринг, скоростью загрузки; грейд Middle совпадает с вакансией
- Тема «TypeScript» найдена по словам: TypeScript; грейд Middle совпадает с вакансией
- Тема «JavaScript и event loop» найдена по словам: event loop; грейд Middle совпадает с вакансией
- Тема «Доступность интерфейса» найдена по словам: доступностью интерфейса; ближайший доступный грейд Стажёр (шаблонов Middle по теме в банке нет)

### 03_mobile_android_junior.md
- Специализация Mobile — по словам: Android, Jetpack Compose, Android SDK
- Грейд Junior взят из заголовка вакансии («Junior»)
- Тема «Kotlin: основы и null-safety» найдена по словам: Kotlin, null-safety, лямбды; грейд Junior совпадает с вакансией
- Тема «Жизненный цикл Activity/Fragment» найдена по словам: жизненный цикл, Activity, Fragment; грейд Junior совпадает с вакансией
- Тема «HTTP и REST API» найдена по словам: REST, API; грейд Junior совпадает с вакансией
- Тема «Работа с сетью и REST API» найдена по словам: REST API, Retrofit; грейд Junior совпадает с вакансией
- Тема «Сборка и публикация» найдена по словам: Google Play, RuStore; грейд Junior совпадает с вакансией
- Тема «Хранение данных на устройстве» найдена по словам: Room; грейд Junior совпадает с вакансией

### 04_data_ml_middle.md
- Специализация Data Science / ML — по словам: ML, pandas, scikit-learn, PyTorch
- Грейд Middle взят из заголовка вакансии («Middle»)
- Тема «Нейросети (PyTorch)» найдена по словам: PyTorch, нейросетей, эмбеддинги; грейд Middle совпадает с вакансией
- Тема «SQL: оконные функции и JOIN» найдена по словам: SQL, оконных функций, JOIN; грейд Middle совпадает с вакансией
- Тема «Метрики качества и ранжирования» найдена по словам: метрикам, precision, nDCG; грейд Middle совпадает с вакансией
- Тема «Статистика и A/B-тесты» найдена по словам: статистики, A/B; грейд Middle совпадает с вакансией
- Тема «Обработка данных (pandas)» найдена по словам: pandas, признаки; грейд Middle совпадает с вакансией
- Тема «Вывод моделей в прод (MLOps)» найдена по словам: MLflow, Airflow, в прод; ближайший доступный грейд Junior (шаблонов Middle по теме в банке нет)
- Тема «Классическое ML (scikit-learn)» найдена по словам: scikit-learn; грейд Middle совпадает с вакансией

### 05_devops_middle.md
- Специализация DevOps — по словам: DevOps, Kubernetes, Terraform, GitLab CI
- Грейд Middle взят из заголовка вакансии («Middle»)
- Тема «Linux: сети, процессы, диагностика» найдена по словам: Linux, systemd, процессы; грейд Middle совпадает с вакансией
- Тема «Мониторинг и инциденты» найдена по словам: мониторинг, алерты, Prometheus; грейд Middle совпадает с вакансией
- Тема «CI/CD» найдена по словам: GitLab CI, пайплайны, деплой; ближайший доступный грейд Junior (шаблонов Middle по теме в банке нет)
- Тема «Docker и контейнеризация» найдена по словам: Docker, контейнеризацией; грейд Middle совпадает с вакансией
- Тема «Kubernetes: объекты и отладка» найдена по словам: Kubernetes, Helm; грейд Middle совпадает с вакансией
- Тема «Инфраструктура как код (Terraform)» найдена по словам: Terraform, Ansible; ближайший доступный грейд Senior (шаблонов Middle по теме в банке нет)

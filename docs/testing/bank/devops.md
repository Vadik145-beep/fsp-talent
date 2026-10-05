# Банк задач: DevOps

30 параметрических шаблонов (T4.3). Код — `backend/app/testing/engine/bank/devops/`, сверка ключей — `backend/tests/engine/test_bank_devops_verify.py`.

Каждый шаблон даёт не меньше 50 разных вариантов, ответ вычисляет генератор. Общие проверки (контракт, ≥ 50 вариантов, позиция верного ответа) — `test_engine_bank_full.py`. Стартовые `a`, `b` заданы экспертно по целевому грейду и уточняются калибровкой.

Как сверен ключ: **система** — настоящей библиотекой или программой (12); **пересчёт** — независимой реализацией в тесте (6); **экспертно** — ответ задан автором, машиной не проверить (12).

Тесты сверки пропускаются, если нужной библиотеки нет (в CI ставятся только зависимости бэкенда). Для полной сверки: `pip install pandas scikit-learn scipy statsmodels jsonschema lxml cssselect pyyaml cryptography`; для bash-шаблонов нужен bash (на Windows — Git Bash).

| id | тема | формат | грейд | a | b | что проверяет | как сверен ключ |
|---|---|---|---|---|---|---|---|
| `devops.bash_basic_output` | bash | code_output | Стажёр | 1.1 | -1.4 | bash: переменные, арифметика, циклы | система: выполнение в bash (на Windows — Git Bash) |
| `devops.pipeline_order` | ci_cd | ordering | Стажёр | 1.0 | -1.5 | Порядок стадий CI/CD | экспертно: экспертно |
| `devops.semver_bump` | ci_cd | short_text | Стажёр | 1.1 | -1.2 | Следующая версия по SemVer | система: packaging.version |
| `devops.chmod_octal` | linux | short_text | Стажёр | 1.2 | -1.3 | Права доступа: восьмеричная и символьная запись | система: stat.filemode |
| `devops.linux_commands` | linux | single_choice | Стажёр | 1.0 | -1.6 | Команда под задачу | экспертно: экспертно |
| `devops.well_known_ports` | networking | short_text | Стажёр | 1.0 | -1.7 | Стандартные порты сервисов | система: socket.getservbyname (база services ОС) |
| `devops.deploy_strategies` | ci_cd | single_choice | Junior | 1.1 | -0.6 | Стратегия выкладки под задачу | экспертно: экспертно |
| `devops.docker_network` | containers | single_choice | Junior | 1.3 | -0.5 | Адреса сервисов в docker compose | экспертно: экспертно |
| `devops.terraform_state` | iac | multi_choice | Junior | 1.1 | -0.4 | Состояние Terraform | экспертно: экспертно |
| `devops.k8s_probes` | kubernetes | single_choice | Junior | 1.2 | -0.3 | Liveness, readiness и startup probes | экспертно: экспертно |
| `devops.file_access` | linux | multi_choice | Junior | 1.3 | -0.4 | Кто может читать, писать, запускать | пересчёт: независимый пересчёт через константы модуля stat |
| `devops.signals` | linux | single_choice | Junior | 1.2 | -0.6 | Сигналы процессов | система: bash: kill -s SIG даёт код 128+N; остальное экспертно |
| `devops.cidr_hosts_count` | networking | numeric | Junior | 1.3 | -0.3 | Размеры подсетей CIDR | система: ipaddress |
| `devops.dns_records` | networking | single_choice | Junior | 1.1 | -0.7 | Тип DNS-записи под задачу | экспертно: экспертно |
| `devops.bash_redirection` | bash | code_output | Middle | 1.5 | 0.5 | bash: stdout, stderr и перенаправления | система: выполнение в bash, stdout и stderr вместе |
| `devops.text_pipeline` | bash | code_output | Middle | 1.4 | 0.3 | Конвейеры grep, awk, sort, uniq | система: выполнение в bash (grep, awk, sort, uniq, cut) |
| `devops.multistage_contents` | containers | multi_choice | Middle | 1.3 | 0.3 | Что попадёт в итоговый образ multi-stage | экспертно: экспертно |
| `devops.k8s_manifest_bug` | kubernetes | find_bug_line | Middle | 1.5 | 0.6 | Ошибка в манифесте Kubernetes | система: PyYAML: ошибка в манифесте ровно одна и в указанной строке |
| `devops.k8s_resources` | kubernetes | numeric | Middle | 1.4 | 0.5 | Сколько подов поместится на ноду | пересчёт: независимый разбор quantity и пересчёт |
| `devops.k8s_service_port` | kubernetes | single_choice | Middle | 1.3 | 0.2 | Как достучаться до Service | экспертно: экспертно |
| `devops.error_budget` | monitoring | numeric | Middle | 1.3 | 0.2 | Бюджет ошибок по SLO | пересчёт: независимый пересчёт |
| `devops.promql_query` | monitoring | single_choice | Middle | 1.4 | 0.6 | Запрос PromQL под вопрос | экспертно: экспертно |
| `devops.subnet_overlap` | networking | multi_choice | Middle | 1.4 | 0.5 | Можно ли создать подсеть в VPC | система: ipaddress: subnet_of, overlaps |
| `devops.bash_quoting` | bash | code_output | Senior | 1.5 | 1.3 | bash: кавычки, $@ и разбиение на слова | система: выполнение в bash |
| `devops.terraform_plan` | iac | code_output | Senior | 1.4 | 1.1 | Итог terraform plan | пересчёт: независимый разбор HCL и подсчёт add/change/destroy |
| `devops.incident_response_order` | incidents | ordering | Senior | 1.1 | 0.9 | Порядок действий при инциденте | экспертно: экспертно |
| `devops.incident_triage` | incidents | single_choice | Senior | 1.3 | 1.0 | Причина инцидента по симптомам | экспертно: экспертно |
| `devops.k8s_rollout` | kubernetes | numeric | Senior | 1.4 | 1.2 | maxSurge и maxUnavailable | пересчёт: пересчёт по правилам округления Kubernetes |
| `devops.burn_rate` | monitoring | numeric | Senior | 1.4 | 1.4 | Скорость сжигания бюджета ошибок | пересчёт: независимый пересчёт |
| `devops.tls_san_match` | networking | multi_choice | Senior | 1.4 | 1.2 | Подойдёт ли сертификат к имени хоста | система: TLS-рукопожатие OpenSSL (ssl) с сертификатом из cryptography |

## Покрытие: темы × грейды

| тема | Стажёр | Junior | Middle | Senior | всего |
|---|---|---|---|---|---|
| linux | 2 | 2 | 0 | 0 | 4 |
| networking | 1 | 2 | 1 | 1 | 5 |
| containers | 0 | 1 | 1 | 0 | 2 |
| kubernetes | 0 | 1 | 3 | 1 | 5 |
| ci_cd | 2 | 1 | 0 | 0 | 3 |
| iac | 0 | 1 | 0 | 1 | 2 |
| bash | 1 | 0 | 2 | 1 | 4 |
| monitoring | 0 | 0 | 2 | 1 | 3 |
| incidents | 0 | 0 | 0 | 2 | 2 |
| **всего** | 6 | 8 | 9 | 7 | 30 |

## Форматы

| формат | шаблонов |
|---|---|
| single_choice | 9 |
| multi_choice | 5 |
| numeric | 5 |
| code_output | 5 |
| short_text | 3 |
| ordering | 2 |
| find_bug_line | 1 |

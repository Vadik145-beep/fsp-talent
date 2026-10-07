# Разбор свободного текста потребности (T6.1)

Образцы: `data/samples/needs_phrases.json` (12 формулировок с эталоном). Режим — правила (без ключа LLM). Отчёт генерирует `python -m app.nlp.validation`; те же цифры проверяет тест `backend/tests/test_nlp_need_parser.py` (порог — не меньше 10 из 12).

**Итог: верно разобрано 12 из 12** (формулировка верна, если верны все поля).

Правила подбирались с оглядкой на эти образцы, поэтому отдельно проверены формулировки, которых в образцах нет (`test_unseen_phrases`). Точка входа — `parse_need(text)`; эндпоинт `POST /api/matching/needs/parse` должен вызывать именно её.

Как сравниваем: специализация, грейд, формат, город, вилка — точно (с учётом `acceptable`); стек — множества кодов после справочника синонимов отдельно для обязательного и желательного; технологии вне справочника платформы (Nuxt) тоже должны быть узнаны и попасть в нужный список (наружу они уходят в `unrecognized`); предметная область — мягко: хотя бы одна часть эталона есть в `team_description`.

| Поле | Верно |
|---|---|
| specialization | 12 / 12 |
| grade | 12 / 12 |
| stack_required | 12 / 12 |
| stack_optional | 12 / 12 |
| salary | 12 / 12 |
| work_format | 12 / 12 |
| city | 12 / 12 |
| domain | 12 / 12 |

| # | Текст | Итог | Распознано | Ошибки |
|---|---|---|---|---|
| need-01 | нужен сеньор на Go в финтех, удалёнка, 300–400к | ✅ | backend, senior, req=['go'], des=[], 300000–400000, remote, None, «финтех» | — |
| need-02 | Ищем джуна фронтендера, реакт + тайпскрипт, офис в Москве, до 120 тыс | ✅ | frontend, junior, req=['react', 'typescript'], des=[], None–120000, office, Москва, «None» | — |
| need-03 | мидл питонист на бэк, джанго/постгрес, гибрид спб, 180-230 | ✅ | backend, middle, req=['django', 'postgresql', 'python'], des=[], 180000–230000, hybrid, Санкт-Петербург, «None» | — |
| need-04 | Нужен специалист по данным уровня middle+, обязательно SQL и Python, желательно Airflow. Команда антифрода в банке. Вилка 250 000 – 300 000 руб. | ✅ | data_ml, middle, req=['python', 'sql'], des=['airflow'], 250000–300000, None, None, «антифрод, банк» | — |
| need-05 | сроно нужен девопс, кубер терраформ, удаленка | ✅ | devops, None, req=['kubernetes', 'terraform'], des=[], None–None, remote, None, «None» | — |
| need-06 | Тестировщик-автоматизатор на Java (Selenium), junior/middle, гибрид, Казань, от 150к | ✅ | qa, junior, req=['java', 'selenium'], des=[], 150000–None, hybrid, Казань, «None» | — |
| need-07 | ios разработчик сеньор swift swiftui, фуллремоут, 350-450 тыс. на руки | ✅ | mobile, senior, req=['swift', 'swiftui'], des=[], 350000–450000, remote, None, «None» | — |
| need-08 | Стажёр в ML-команду, Python, базовая математика, можно студент, офис Новосибирск, 60 000 | ✅ | data_ml, intern, req=['python'], des=[], 60000–60000, office, Новосибирск, «None» | — |
| need-09 | ищем фронта на вью, мидл, гибрид мск, денег 200-250к, плюсом nuxt | ✅ | frontend, middle, req=['vue'], des=['nuxt'], 200000–250000, hybrid, Москва, «None» | — |
| need-10 | Бэкенд на Java/Kotlin + Spring, уровень сеньор или лид, highload e-commerce, вилка до 500к | ✅ | backend, senior, req=['java', 'kotlin', 'spring'], des=[], None–500000, None, None, «highload, e-commerce» | — |
| need-11 | Flutter dev джун+ на удалёнке, проект для доставки еды, 100-140 т.р. | ✅ | mobile, junior, req=['flutter'], des=[], 100000–140000, remote, None, «доставка еды» | — |
| need-12 | нужен sre/девопс мидл в облачный сервис: линукс, докер, prometheus+grafana, ci/cd на гитлабе. офис/гибрид, екб. зп обсуждается | ✅ | devops, middle, req=['docker', 'gitlab_ci', 'grafana', 'linux', 'prometheus'], des=[], None–None, hybrid, Екатеринбург, «облачный сервис» | — |

# Образцы данных для проверки (синтетика)

Все люди, компании, телефоны и почты выдуманы, почты — на домене `example.com`.
Коды справочников — общие для проекта: специализации `backend`, `frontend`, `mobile`,
`data_ml`, `qa`, `devops`; грейды `intern`, `junior`, `middle`, `senior`;
формат работы `office`, `hybrid`, `remote`.

Проверка образцов: `python scripts/samples/check_samples.py` (зависимости —
`scripts/samples/requirements.txt`).

## resumes/ — 5 PDF-резюме (T3.2)

Генерируются скриптом `scripts/samples/generate_resumes.py` (повторный запуск даёт те же байты).

| Файл | Специализация, грейд | Оформление |
|---|---|---|
| `01_backend_python_middle.pdf` | Backend, Middle | одна колонка, шрифт с засечками |
| `02_frontend_react_senior.pdf` | Frontend, Senior | две колонки, тёмная боковая панель |
| `03_data_ml_junior.pdf` | Data/ML, Junior | таблицы: контакты, навыки с уровнями, опыт |
| `04_qa_intern_minimal.pdf` | QA, Стажёр | полстраницы, без разделов и отчества |
| `05_devops_senior_long.pdf` | DevOps, Senior | длинное, 2 страницы, стек по группам |

Рядом `<имя>.expected.json` — эталон разбора:

| Поле | Как сравнивать |
|---|---|
| `full_name`, `email`, `city` | точное совпадение (без учёта регистра и лишних пробелов) |
| `phone` | нормализован в `+7XXXXXXXXXX`; в PDF записан по-разному (`8-913-…`, `+7 (917) …`) |
| `stack` | множество технологий; метрика — precision / recall по элементам |
| `experience_years` | сумма периодов работы на октябрь 2026; допуск ±0,5 года |
| `grade` | код грейда, если указан в резюме, иначе `null` |
| `specialization` | код специализации |
| `roles`, `soft_skills` | как написано в резюме; сравнивать мягко (по смыслу / после сопоставления со справочником) |
| `work_format` | код формата или `null`, если не указан |
| `links` | ссылки (сейчас только `github`) |

Подсказка для парсера: в резюме №2 построчное извлечение текста смешивает колонки;
помогает резать страницу по колонкам (`page.crop(...)` в pdfplumber), как в `check_samples.py`.

## vacancies/ — 5 вакансий (T4.8)

`<имя>.md` — текст как на сайте вакансий, `<имя>.json` — разметка:
`specialization`, `grade`, `stack_required`, `stack_optional`, `salary_from`, `salary_to`
(рубли), `currency`, `salary_gross` (до вычета налогов или нет; `null` — не указано),
`work_format`, `city` (`null` при удалёнке), `experience_years_min`, `team_description`,
`company`, `expected_topics` — темы, которые разумно проверять тестом по этой вакансии
(ориентир для «заданий из вакансий», не точный эталон).

| Файл | Вакансия |
|---|---|
| `01_backend_go_senior` | Senior Go, финтех, удалённо, 350–450 тыс. |
| `02_frontend_react_middle` | Middle React, e-commerce, Москва гибрид, 200–260 тыс. |
| `03_mobile_android_junior` | Junior Android (Kotlin), Казань офис, 110–150 тыс. |
| `04_data_ml_middle` | Middle ML, рекомендации, удалённо, 250–320 тыс. |
| `05_devops_middle` | Middle DevOps, Новосибирск гибрид, 220–290 тыс. |

## needs_phrases.json — 12 формулировок потребности (T6.1)

Свободный текст работодателя в разной манере (сленг «джун/мидл», опечатки, без зарплаты,
одна сумма вместо вилки, смесь русского и английского) и эталонный разбор `expected`:
`specialization`, `grade`, `stack_required`, `stack_optional`, `salary_from`, `salary_to`,
`work_format`, `city`, `domain`. `null` — не указано в тексте.
`acceptable` — допустимые альтернативы при спорной трактовке (например, «junior/middle»).
Критерий T6.1: верный разбор ≥ 8 из 10 (у нас 12 формулировок).

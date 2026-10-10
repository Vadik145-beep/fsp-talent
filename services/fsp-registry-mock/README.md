# fsp-registry-mock — мок реестра ФСП

Маленький FastAPI-сервис: отдаёт участников ФСП и их достижения по ФСП ID.
Это наша версия будущего API реестра ФСП (реального API организаторы не дают).
Схема интеграции и обоснование полей — `docs/integration/fsp.md`.

**Все данные синтетические**: ФИО, команды, соревнования, места и рейтинги выдуманы.

## Данные

- `FSP-000001`…`FSP-000030` — с достижениями (от 1 до 8 у каждого);
- `FSP-000031`…`FSP-000040` — без истории: `has_history: false`, `items: []`;
- `FSP-000101`…`FSP-000180` — с достижениями (от 1 до 6), привязаны к кандидатам демо-банка платформы;
- любой другой ID формата `FSP-NNNNNN` — 404, неверный формат — 422.

Файл `data/participants.json` собирает детерминированный генератор (seed фиксирован):

```bash
python services/fsp-registry-mock/tools/generate_participants.py
```

Руками JSON не править: тест `test_committed_json_matches_generator` сверяет файл с генератором.

## Методы

| Метод | Ответ |
|---|---|
| `GET /health` | `{"status": "ok", "participants": 120, "synthetic": true}` |
| `GET /participants/{fsp_id}` | профиль + `summary` (число достижений, очки, дисциплины, высший уровень, призы) |
| `GET /participants/{fsp_id}/achievements?discipline=&level=` | `{fsp_id, has_history, total, items, updated_at}` |
| `GET /participants?ids=FSP-000001,FSP-000031` | `{items, not_found}`, до 100 ID |
| `GET /dictionaries` | дисциплины и уровни с подписями |
| `GET /docs`, `GET /openapi.json` | Swagger и схема |

Ошибки: `{"code": "...", "message": "...", "details": {...}}`.

## Переменные окружения

| Переменная | По умолчанию | Зачем |
|---|---|---|
| `FSP_MOCK_API_TOKEN` | пусто (выключено) | если задан — все методы, кроме `/health`, требуют `Authorization: Bearer <токен>` |
| `FSP_MOCK_DATA_PATH` | `data/participants.json` | другой файл с данными |

## Запуск

```bash
# локально
cd services/fsp-registry-mock
pip install -r requirements-dev.txt
pytest
uvicorn app.main:app --port 18100

# в Docker (внутри контейнера порт 8000)
docker build -t fsp-registry-mock services/fsp-registry-mock
docker run --rm -p 18100:8000 fsp-registry-mock
```

В образе есть `HEALTHCHECK` (запрос к `/health` через python, curl в образе нет).

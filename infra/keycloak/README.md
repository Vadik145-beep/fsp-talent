# Keycloak: realm `fsp` (ФСП ID на учебном стенде)

Файл импорта: `realm-fsp.json`. Keycloak 25 импортирует его при старте с флагом `--import-realm`
(папка монтируется в `/opt/keycloak/data/import`). Если realm уже есть — импорт пропускается.

## Что внутри

- **Realm `fsp`**, вход по логину или почте, русская страница входа по умолчанию
  (`internationalization`: ru, en), защита от перебора паролей включена, регистрация выключена.
- **Атрибут пользователя `fsp_id`** объявлен в User Profile (формат `FSP-000001`,
  пользователь видит, менять может только админ).
- **Клиент `fsp-talent`** — для приложения: public, только Standard Flow (Authorization Code),
  PKCE S256 обязателен. Redirect URI: `http://localhost:15173/*`, `http://localhost:18000/*`;
  web origins: `http://localhost:15173`, `http://localhost:18000`.
- **Клиент `fsp-talent-test`** — **только для автопроверки**: public, только Direct Access
  Grants (логин + пароль → токен, без браузера). Нужен тестам и проверке стенда.
  На проде клиента быть не должно.
- В обоих клиентах protocol mapper `fsp_id` (атрибут пользователя → claim `fsp_id`
  в ID-токене, access-токене, userinfo и introspection).

## Тестовые пользователи

Пароль у всех: **`Fsp-demo-2026`** (учебный стенд, не секрет).
ФИО и ФСП ID совпадают с данными мока реестра (`services/fsp-registry-mock`).

| Логин | ФСП ID | Имя | История в реестре |
|---|---|---|---|
| `fsp.user01` | FSP-000001 | Никита Латыпов | 7 достижений |
| `fsp.user02` | FSP-000002 | Артём Белов | 5 |
| `fsp.user03` | FSP-000003 | Кирилл Волков | 4 |
| `fsp.user04` | FSP-000004 | Арсений Лебедев | 6 |
| `fsp.user05` | FSP-000005 | Софья Зайцева | 3 |
| `fsp.nohistory` | FSP-000031 | Илья Белов | нет истории |

## Проверка токена

```bash
curl -s -X POST http://localhost:18180/realms/fsp/protocol/openid-connect/token \
  -d grant_type=password -d client_id=fsp-talent-test -d scope=openid \
  -d username=fsp.user01 -d password=Fsp-demo-2026
```

В `id_token` и `access_token` будет `"fsp_id": "FSP-000001"`.

## Настройки контейнера (для docker-compose)

```yaml
image: quay.io/keycloak/keycloak:25.0
command: start-dev --import-realm
ports: ["18180:8080"]
volumes: ["./infra/keycloak:/opt/keycloak/data/import:ro"]
environment:
  KEYCLOAK_ADMIN: admin
  KEYCLOAK_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD}
  KC_HEALTH_ENABLED: "true"
  KC_HOSTNAME: http://localhost:18180      # iss в токенах всегда такой
  KC_HOSTNAME_BACKCHANNEL_DYNAMIC: "true"  # backend может ходить на http://keycloak:8080
healthcheck:
  test: ["CMD-SHELL", "exec 3<>/dev/tcp/127.0.0.1/9000 && printf 'GET /health/ready HTTP/1.1\\r\\nHost: localhost\\r\\nConnection: close\\r\\n\\r\\n' >&3 && cat <&3 | grep -q '\"UP\"'"]
```

В образе Keycloak нет curl, поэтому healthcheck через `/dev/tcp` к порту управления 9000.
Память в режиме dev — около 630 МБ.

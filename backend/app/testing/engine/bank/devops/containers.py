"""DevOps — контейнеры: сеть docker compose, что попадает в итоговый образ multi-stage."""

from __future__ import annotations

import random
from typing import Any

from ...templates import ItemFormat, ItemTemplate, Variant, make_multi_choice, make_single_choice

# --------------------------------------------------------------------------- сеть compose

_BACKENDS = (
    ("db", "postgres:16", 5432),
    ("cache", "redis:7", 6379),
    ("mysql", "mysql:8.4", 3306),
    ("broker", "rabbitmq:3", 5672),
    ("search", "elasticsearch:8.15.0", 9200),
)


def _gen_compose_net(rng: random.Random) -> Variant:
    name, image, port = rng.choice(_BACKENDS)
    app = rng.choice(("api", "worker", "web", "backend"))
    host_port = rng.choice([p for p in (15432, 16379, 13306, 15672, 19200, 25000) if p != port])
    q = rng.choice(("from_app", "from_host", "from_app", "from_host"))
    code = "\n".join(
        [
            "services:",
            f"  {app}:",
            f"    build: ./{app}",
            "    depends_on:",
            f"      - {name}",
            f"  {name}:",
            f"    image: {image}",
            "    ports:",
            f'      - "{host_port}:{port}"',
        ]
    )
    if q == "from_app":
        ask = (
            f"Контейнеры запущены через docker compose up. По какому адресу приложение в "
            f"контейнере {app} должно подключаться к {name}?"
        )
        correct = f"{name}:{port}"
    else:
        ask = (
            f"Контейнеры запущены через docker compose up. По какому адресу разработчик "
            f"подключается к {name} с хост-машины, где запущен Docker?"
        )
        correct = f"localhost:{host_port}"
    options = [f"{name}:{port}", f"{name}:{host_port}"]
    options += [f"localhost:{port}", f"localhost:{host_port}"]
    return make_single_choice(
        rng,
        ask,
        correct,
        [o for o in options if o != correct],
        code=code,
        extra={"language": "yaml"},
        explanation=f"Внутри сети compose — имя сервиса и порт контейнера; с хоста — "
        f"опубликованный порт {host_port}.",
    )


COMPOSE_NET = ItemTemplate(
    id="devops.docker_network",
    specialization="devops",
    topic="containers",
    target_grade="junior",
    format=ItemFormat.SINGLE_CHOICE,
    generator=_gen_compose_net,
    a=1.3,
    b=-0.5,
    title="Адреса сервисов в docker compose",
    time_limit_s=120,
)

# --------------------------------------------------------------------------- multi-stage


def _stacks(rng: random.Random) -> list[dict[str, Any]]:
    go_bin = rng.choice(("server", "api", "worker"))
    return [
        {
            "build": [
                f"FROM golang:{rng.choice(('1.22', '1.23'))} AS build",
                "WORKDIR /src",
                "COPY . .",
                f"RUN go build -o /out/{go_bin} ./cmd/{go_bin}",
            ],
            "final_base": "alpine:3.20",
            "final": [
                "RUN apk add --no-cache ca-certificates",
                f"COPY --from=build /out/{go_bin} /usr/local/bin/{go_bin}",
                f'CMD ["{go_bin}"]',
            ],
            "items": [
                (f"Бинарник /usr/local/bin/{go_bin}", True, True),
                ("Пакет ca-certificates", True, False),
                ("Компилятор Go (команда go)", False, True),
                ("Исходный код в /src", False, True),
                (f"Файл /out/{go_bin}", False, True),
            ],
        },
        {
            "build": [
                f"FROM node:{rng.choice(('20', '22'))} AS build",
                "WORKDIR /app",
                "COPY package*.json ./",
                "RUN npm ci",
                "COPY . .",
                "RUN npm run build",
            ],
            "final_base": "nginx:1.27-alpine",
            "final": [
                "COPY --from=build /app/dist /usr/share/nginx/html",
                "COPY nginx.conf /etc/nginx/conf.d/default.conf",
            ],
            "items": [
                ("Собранная статика в /usr/share/nginx/html", True, True),
                ("Свой nginx.conf в /etc/nginx/conf.d/", True, False),
                ("Каталог /app/node_modules", False, True),
                ("Node.js и npm", False, True),
                ("Исходники /app/src", False, True),
            ],
        },
        {
            "build": [
                f"FROM python:{rng.choice(('3.12', '3.13'))} AS build",
                "WORKDIR /w",
                "COPY requirements.txt .",
                "RUN pip wheel --wheel-dir /wheels -r requirements.txt",
            ],
            "final_base": f"python:{rng.choice(('3.12', '3.13'))}-slim",
            "final": [
                "COPY --from=build /wheels /wheels",
                "RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels",
                "COPY app/ /srv/app/",
                'CMD ["python", "-m", "app"]',
            ],
            "items": [
                ("Установленные зависимости из requirements.txt", True, True),
                ("Код приложения в /srv/app", True, False),
                ("Каталог /wheels", False, True),
                ("Компилятор gcc из полного образа python", False, True),
                ("Файл /w/requirements.txt", False, True),
            ],
        },
        {
            "build": [
                "FROM maven:3.9-eclipse-temurin-21 AS build",
                "WORKDIR /src",
                "COPY . .",
                "RUN mvn -q package -DskipTests",
            ],
            "final_base": "eclipse-temurin:21-jre",
            "final": [
                "COPY --from=build /src/target/app.jar /opt/app.jar",
                'CMD ["java", "-jar", "/opt/app.jar"]',
            ],
            "items": [
                ("Файл /opt/app.jar", True, True),
                ("Среда выполнения Java (JRE)", True, True),
                ("Maven (команда mvn)", False, True),
                ("Исходники в /src", False, True),
                ("Локальный репозиторий Maven ~/.m2", False, True),
            ],
        },
    ]


def _gen_multistage(rng: random.Random) -> Variant:
    st = rng.choice(_stacks(rng))
    lines = [*st["build"], "", f"FROM {st['final_base']}", *st["final"]]
    items = rng.sample(st["items"], 4)
    if rng.random() < 0.5:
        items.append(("Каталог .git из контекста сборки", False, False))
    correct = [t for t, present, _ in items if present]
    wrong = [t for t, present, _ in items if not present]
    if not correct:
        correct = [next(t for t, present, _ in st["items"] if present)]
    return make_multi_choice(
        rng,
        "Что окажется в итоговом образе после docker build по этому Dockerfile? Отметьте всё, "
        "что в нём будет.",
        correct,
        wrong,
        code="\n".join(lines),
        extra={"language": "dockerfile", "min_choices": 1},
        explanation="В образ попадает только последняя стадия и то, что в неё скопировано.",
    )


MULTISTAGE = ItemTemplate(
    id="devops.multistage_contents",
    specialization="devops",
    topic="containers",
    target_grade="middle",
    format=ItemFormat.MULTI_CHOICE,
    generator=_gen_multistage,
    a=1.3,
    b=0.3,
    title="Что попадёт в итоговый образ multi-stage",
    time_limit_s=180,
)

TEMPLATES = [COMPOSE_NET, MULTISTAGE]

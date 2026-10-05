"""DevOps: подсети CIDR (short_text), кэш слоёв и ошибки Dockerfile (find_bug_line)."""

from __future__ import annotations

import ipaddress
import random
from typing import TypedDict

from ..templates import ItemFormat, ItemTemplate, Variant

# --------------------------------------------------------------------------- CIDR

_QUESTIONS = {
    "network": "адрес сети",
    "broadcast": "широковещательный (broadcast) адрес",
    "first_host": "первый адрес, который можно выдать хосту",
    "last_host": "последний адрес, который можно выдать хосту",
}


def _random_private_ip(rng: random.Random) -> ipaddress.IPv4Address:
    block = rng.choice(("10", "172", "192"))
    if block == "10":
        raw = f"10.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"
    elif block == "172":
        raw = f"172.{rng.randint(16, 31)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"
    else:
        raw = f"192.168.{rng.randint(0, 255)}.{rng.randint(1, 254)}"
    return ipaddress.IPv4Address(raw)


def _gen_cidr(rng: random.Random) -> Variant:
    while True:
        ip = _random_private_ip(rng)
        prefix = rng.randint(18, 29)
        net = ipaddress.IPv4Network(f"{ip}/{prefix}", strict=False)
        # адрес не должен совпадать с ответом — иначе вопрос решается копированием
        edges = (
            net.network_address,
            net.network_address + 1,
            net.broadcast_address - 1,
            net.broadcast_address,
        )
        if ip not in edges:
            break
    q = rng.choice(tuple(_QUESTIONS))
    answers = {
        "network": net.network_address,
        "broadcast": net.broadcast_address,
        "first_host": net.network_address + 1,
        "last_host": net.broadcast_address - 1,
    }
    answer = str(answers[q])
    return Variant(
        prompt=(
            f"Сервер получил адрес {ip}/{prefix}. Укажите {_QUESTIONS[q]} этой подсети "
            "в формате a.b.c.d."
        ),
        key=(answer,),
        extra={"answer_type": "ipv4"},
        explanation=f"Сеть {net}, ответ {answer}.",
    )


CIDR = ItemTemplate(
    id="devops.cidr_subnet",
    specialization="devops",
    topic="networking",
    target_grade="middle",
    format=ItemFormat.SHORT_TEXT,
    generator=_gen_cidr,
    a=1.4,
    b=0.6,
    title="Подсети и CIDR",
    time_limit_s=180,
)

# --------------------------------------------------------------------------- Dockerfile


class _Stack(TypedDict):
    base: tuple[str, ...]
    latest: str
    deps: str
    install: str
    cmd: tuple[str, ...]
    port: tuple[int, ...]
    runtime: str


_STACKS: tuple[_Stack, ...] = (
    {
        "base": ("python:3.11-slim", "python:3.12-slim", "python:3.13-slim"),
        "latest": "python:latest",
        "deps": "requirements.txt",
        "install": "pip install --no-cache-dir -r requirements.txt",
        "cmd": ('["python", "-m", "app"]', '["gunicorn", "app.wsgi:application"]'),
        "port": (8000, 5000),
        "runtime": "Python",
    },
    {
        "base": ("node:18-alpine", "node:20-alpine", "node:22-alpine"),
        "latest": "node:latest",
        "deps": "package.json package-lock.json",
        "install": "npm ci --omit=dev",
        "cmd": ('["node", "server.js"]', '["npm", "start"]'),
        "port": (3000, 8080),
        "runtime": "Node.js",
    },
    {
        "base": ("golang:1.22", "golang:1.23", "golang:1.24"),
        "latest": "golang:latest",
        "deps": "go.mod go.sum",
        "install": "go mod download",
        "cmd": ('["/app/server"]', '["/app/api"]'),
        "port": (8080, 9090),
        "runtime": "Go",
    },
)
_WORKDIRS = ("/app", "/srv/app", "/opt/service", "/usr/src/app")
_SECRETS = ("DB_PASSWORD", "API_TOKEN", "AWS_SECRET_ACCESS_KEY", "JWT_SECRET")


def _gen_dockerfile(rng: random.Random) -> Variant:
    st = rng.choice(_STACKS)
    base = rng.choice(st["base"])
    wd = rng.choice(_WORKDIRS)
    kind = rng.choice(("cache", "cache", "secret", "latest"))
    cmd = rng.choice(st["cmd"])
    lines: list[str] = []
    if rng.random() < 0.4:
        lines.append("# syntax=docker/dockerfile:1")
    from_idx = len(lines)
    lines.append(f"FROM {st['latest'] if kind == 'latest' else base}")
    lines.append(f"WORKDIR {wd}")
    if rng.random() < 0.5:
        lines.append(f"ENV TZ={rng.choice(('UTC', 'Europe/Moscow'))}")
    secret_idx = -1
    if kind == "secret":
        secret_idx = len(lines)
        token = "".join(rng.choice("abcdef0123456789") for _ in range(12))
        lines.append(f"ENV {rng.choice(_SECRETS)}={token}")
    cache_idx = -1
    if kind == "cache":
        cache_idx = len(lines)
        lines.append("COPY . .")
        lines.append(f"RUN {st['install']}")
    else:
        lines.append(f"COPY {st['deps']} ./")
        lines.append(f"RUN {st['install']}")
        lines.append("COPY . .")
    if "golang" in base:
        lines.append(f"RUN go build -o {cmd[2:-2]} ./cmd/server")
    if rng.random() < 0.6:
        lines.append(f"EXPOSE {rng.choice(st['port'])}")
    lines.append(f"CMD {cmd}")

    if kind == "cache":
        bug, problem = (
            cache_idx,
            (
                "После любого изменения исходного кода зависимости устанавливаются заново: "
                "кэш слоёв не срабатывает."
            ),
        )
    elif kind == "secret":
        bug, problem = secret_idx, "Любой, кто скачает образ, увидит секрет."
    else:
        bug, problem = (
            from_idx,
            (
                "Сборка того же коммита через месяц неожиданно получила другую мажорную версию "
                f"{st['runtime']}, и приложение сломалось."
            ),
        )
    return Variant(
        prompt=f"{problem} В какой строке Dockerfile причина? Укажите номер строки.",
        key=bug + 1,
        code="\n".join(lines),
        extra={"language": "dockerfile", "line_count": len(lines)},
        explanation=f"Строка {bug + 1}: {lines[bug]}",
    )


DOCKERFILE = ItemTemplate(
    id="devops.dockerfile_layers",
    specialization="devops",
    topic="containers",
    target_grade="middle",
    format=ItemFormat.FIND_BUG_LINE,
    generator=_gen_dockerfile,
    a=1.3,
    b=0.2,
    title="Слои и кэш Dockerfile",
    time_limit_s=150,
)

TEMPLATES = [CIDR, DOCKERFILE]

"""Раздел 7 документации: библиотеки и компоненты с версиями → docs/solution/07_libraries.md.

Откуда берутся версии:
- бэкенд и мок реестра ФСП — опись пакетов, реально установленных в контейнерах
  (`pip_inventory.py` через `docker exec`), объявленные ограничения — из `backend/pyproject.toml`
  и `services/fsp-registry-mock/requirements.txt`;
- фронтенд — `frontend/package.json` (объявлено) и `frontend/package-lock.json` (установлено,
  с лицензиями);
- образы Docker — `docker-compose.yml`, `infra/stand/compose.yml`, `infra/stand/deploy.sh`
  и `FROM` в Dockerfile; точная версия — из метаданных локального образа, если он скачан.

Запуск из корня репозитория при поднятом dev-стеке (`docker compose up`):
    python docs/solution/tools/gen_libraries.py
Без Docker: `--backend-json` / `--mock-json` — заранее снятая опись
(`docker exec -i <контейнер> python - <файл зависимостей> < pip_inventory.py > out.json`).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import tomllib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = Path(__file__).resolve().parent

PERMISSIVE = re.compile(
    r"^(MIT|MIT-0|MIT-CMU|ISC|0BSD|BSD|BSD-2-Clause|BSD-3-Clause|Apache-2\.0|Unlicense|CC0-1\.0|"
    r"Python-2\.0|PSF-2\.0|Zlib|BlueOak-1\.0\.0|MPL-2\.0|CC-BY-4\.0|"
    r"MIT License|BSD License|Apache Software License)$"
)

# Зачем нужна прямая зависимость (коротко, для эксперта)
PURPOSE = {
    # backend
    "fastapi": "веб-фреймворк API, OpenAPI/Swagger",
    "uvicorn": "ASGI-сервер",
    "sqlalchemy": "ORM, асинхронный доступ к PostgreSQL",
    "asyncpg": "драйвер PostgreSQL",
    "alembic": "миграции схемы БД",
    "pydantic": "схемы запросов и ответов, валидация",
    "pydantic-settings": "настройки из переменных окружения",
    "email-validator": "проверка адресов почты",
    "python-multipart": "загрузка файлов (PDF-резюме)",
    "httpx": "HTTP-клиент: Keycloak, реестр ФСП, LLM",
    "pyjwt": "JWT сессий и проверка ID-токенов Keycloak (JWKS)",
    "pdfplumber": "разбор PDF-резюме",
    "reportlab": "генерация PDF-профиля кандидата",
    "numpy": "движок адаптивного теста (IRT, EAP, калибровка)",
    "pytest": "автотесты",
    "ruff": "линтер и форматтер",
    "mypy": "проверка типов",
    # frontend
    "react": "UI",
    "react-dom": "UI (рендер в браузере)",
    "react-router": "маршруты кабинетов",
    "@tanstack/react-query": "запросы к API и кэш",
    "recharts": "графики (валидация, дашборды)",
    "lucide-react": "иконки",
    "clsx": "склейка CSS-классов",
    "tailwind-merge": "склейка классов Tailwind",
    "@fontsource/inter": "шрифт Inter (брендбук ФСП), без CDN",
    "@fontsource/jetbrains-mono": "шрифт JetBrains Mono (брендбук ФСП), без CDN",
    "vite": "сборка и dev-сервер",
    "@vitejs/plugin-react": "React для Vite",
    "typescript": "типизация",
    "tailwindcss": "стили",
    "@tailwindcss/vite": "Tailwind для Vite",
    "msw": "моки API в браузере (прототип без бэкенда)",
    "openapi-typescript": "TS-типы из OpenAPI",
    "vitest": "автотесты фронтенда",
    "jsdom": "DOM для тестов",
    "@testing-library/react": "тесты компонентов",
    "@testing-library/dom": "тесты компонентов",
    "@testing-library/jest-dom": "проверки DOM в тестах",
    "@testing-library/user-event": "клики и ввод в тестах",
    "eslint": "линтер",
    "@eslint/js": "линтер",
    "typescript-eslint": "линтер TypeScript",
    "eslint-plugin-react-hooks": "линтер хуков React",
    "eslint-plugin-react-refresh": "линтер Fast Refresh",
    "globals": "линтер (глобальные имена)",
    "@types/node": "типы Node.js",
    "@types/react": "типы React",
    "@types/react-dom": "типы React DOM",
}

IMAGE_INFO = {
    "postgres": ("PostgreSQL License", "СУБД"),
    "quay.io/keycloak/keycloak": ("Apache-2.0", "ФСП ID: OIDC-провайдер, realm fsp"),
    "axllent/mailpit": ("MIT", "почта в разработке и на демо-стенде"),
    "caddy": ("Apache-2.0", "HTTPS (Let's Encrypt), обратный прокси и статика фронта на стенде"),
    "python": ("PSF-2.0", "база образов backend и мока реестра"),
    "node": ("MIT", "dev-сервер фронта и сборка статики"),
    "ghcr.io/ggml-org/llama.cpp": (
        "MIT",
        "локальная LLM: сервер llama.cpp с моделью Qwen2.5-1.5B-Instruct (Apache-2.0)",
    ),
}
VERSION_KEYS = (
    "org.opencontainers.image.version",
    "PG_VERSION",
    "PYTHON_VERSION",
    "NODE_VERSION",
    "CADDY_VERSION",
)
VERSION_COMMANDS = {"axllent/mailpit": ["/mailpit", "version"]}
# Базовый образ не скачан отдельно — версию видно в собранном на нём образе dev-стека
BUILT_ON = {"python:3.12-slim": "fsp-talent-backend", "node:22-alpine": "fsp-talent-frontend"}


def canon(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def req_name(spec: str) -> str:
    return canon(re.split(r"[\[<>=!~ ;]", spec, maxsplit=1)[0])


def run(cmd: list[str], stdin: bytes | None = None) -> str | None:
    try:
        out = subprocess.run(cmd, input=stdin, capture_output=True, timeout=60, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.decode("utf-8", "replace")


def inventory(container: str, deps_file: str, json_path: Path | None) -> dict | None:
    if json_path:
        return json.loads(json_path.read_text(encoding="utf-8"))
    script = (TOOLS / "pip_inventory.py").read_bytes()
    out = run(["docker", "exec", "-i", container, "python", "-", deps_file], stdin=script)
    return json.loads(out) if out else None


def lic_ok(lic: str) -> bool:
    parts = re.split(r"\s+(?:OR|AND)\s+|,\s*|;\s*|\s*/\s*", lic.strip("() "))
    return all(PERMISSIVE.match(p.strip("() ")) for p in parts if p.strip())


def python_section(
    title: str, inv: dict | None, declared: list[str], dev: list[str] | None = None
) -> list[str]:
    lines = [f"### {title}", ""]
    decl = {req_name(s): s for s in declared}
    if inv is None:
        lines += [
            "Контейнер не запущен — установленные версии не сняты (показаны объявленные).",
            "",
            "| Пакет | Объявлено | Зачем |",
            "|---|---|---|",
        ]
        for name, spec in decl.items():
            lines.append(f"| {name} | `{spec}` | {PURPOSE.get(name, '')} |")
        return [*lines, ""]
    pk = inv["packages"]
    lines += [
        f"Python {inv['python']} (в образе). Прямых зависимостей: "
        f"{sum(p['direct'] for p in pk)}, всего с транзитивными: {len(pk)}.",
        "",
        "| Пакет | Объявлено | Установлено | Лицензия | Зачем |",
        "|---|---|---|---|---|",
    ]
    for p in sorted((p for p in pk if p["direct"]), key=lambda p: canon(p["name"])):
        n = canon(p["name"])
        lines.append(
            f"| {p['name']} | `{decl.get(n, p['requirement'] or '')}` | {p['version']} | "
            f"{p['license']} | {PURPOSE.get(n, '')} |"
        )
    if dev:
        for spec in dev:
            n = req_name(spec)
            lines.append(f"| {n} | `{spec}` | только в dev-окружении | — | {PURPOSE.get(n, '')} |")
    trans = sorted((p for p in pk if not p["direct"]), key=lambda p: canon(p["name"]))
    if trans:
        lines += [
            "",
            "Транзитивные: "
            + ", ".join(f"{p['name']} {p['version']} ({p['license']})" for p in trans)
            + ".",
        ]
    if inv.get("missing"):
        lines += ["", f"**Не установлены в образе:** {', '.join(inv['missing'])}."]
    return [*lines, ""]


def frontend_section() -> tuple[list[str], list[str]]:
    pkg = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
    packages = lock["packages"]
    lines = ["### Фронтенд (`frontend/package.json`, версии из `package-lock.json`)", ""]
    for group, title in (
        ("dependencies", "Попадают в сборку"),
        ("devDependencies", "Для разработки и сборки"),
    ):
        lines += [
            f"**{title}:**",
            "",
            "| Пакет | Объявлено | Установлено | Лицензия | Зачем |",
            "|---|---|---|---|---|",
        ]
        for name, spec in pkg.get(group, {}).items():
            info = packages.get(f"node_modules/{name}", {})
            lines.append(
                f"| {name} | `{spec}` | {info.get('version', '—')} | {info.get('license', '—')} | "
                f"{PURPOSE.get(name, '')} |"
            )
        lines.append("")
    runtime = Counter()
    devtime = Counter()
    odd: list[str] = []
    for key, info in packages.items():
        if not key:
            continue
        lic = str(info.get("license", "—"))
        (devtime if info.get("dev") else runtime)[lic] += 1
        if not lic_ok(lic):
            odd.append(f"{key.removeprefix('node_modules/')} {info.get('version', '')} ({lic})")
    total_rt, total_dev = sum(runtime.values()), sum(devtime.values())
    lines += [
        f"Всего пакетов в lock-файле: {total_rt + total_dev} "
        f"(в сборку — {total_rt}, только для разработки — {total_dev}).",
        "",
        "| Лицензия | В сборку | Для разработки |",
        "|---|---|---|",
    ]
    for lic in sorted(set(runtime) | set(devtime), key=lambda x: (-(runtime[x] + devtime[x]), x)):
        lines.append(f"| {lic} | {runtime.get(lic, 0)} | {devtime.get(lic, 0)} |")
    lines.append("")
    return lines, odd


def images() -> list[tuple[str, str]]:
    """(образ, где используется)."""
    found: dict[str, set[str]] = {}
    sources = {
        "docker-compose.yml": ROOT / "docker-compose.yml",
        "infra/stand/compose.yml": ROOT / "infra/stand/compose.yml",
    }
    for label, path in sources.items():
        if path.exists():
            for m in re.finditer(r"^\s*image:\s*([^\s#]+)", path.read_text(encoding="utf-8"), re.M):
                found.setdefault(m.group(1), set()).add(label)
    for path in [
        ROOT / "backend/Dockerfile",
        ROOT / "frontend/Dockerfile",
        *ROOT.glob("services/*/Dockerfile"),
    ]:
        if path.exists():
            for m in re.finditer(r"^FROM\s+(\S+)", path.read_text(encoding="utf-8"), re.M):
                found.setdefault(m.group(1), set()).add(path.relative_to(ROOT).as_posix())
    deploy = ROOT / "infra/stand/deploy.sh"
    if deploy.exists():
        for m in re.finditer(r"\b(node:[\w.-]+)", deploy.read_text(encoding="utf-8")):
            found.setdefault(m.group(1), set()).add("infra/stand/deploy.sh")
    return [(img, ", ".join(sorted(where))) for img, where in sorted(found.items())]


def exact_version(image: str) -> str | None:
    fmt = "{{json .Config.Env}}|{{json .Config.Labels}}"
    out = run(["docker", "image", "inspect", image, "--format", fmt])
    if out:
        env_json, labels_json = out.strip().split("|", 1)
        env = dict(e.split("=", 1) for e in (json.loads(env_json) or []) if "=" in e)
        labels = json.loads(labels_json) or {}
        for key in VERSION_KEYS:
            if labels.get(key):
                return labels[key]
            if env.get(key):
                return env[key]
    repo = image.rsplit(":", 1)[0]
    cmd = VERSION_COMMANDS.get(repo)
    if cmd and out:
        res = run(["docker", "run", "--rm", "--entrypoint", cmd[0], image, *cmd[1:]])
        if res:
            m = re.search(r"v?(\d+\.\d+\.\d+)", res)
            return m.group(1) if m else None
    return None


def images_section() -> list[str]:
    lines = [
        "## Образы Docker",
        "",
        "| Образ (тег) | Точная версия | Лицензия | Роль | Где используется |",
        "|---|---|---|---|---|",
    ]
    for img, where in images():
        repo = img.rsplit(":", 1)[0]
        lic, role = IMAGE_INFO.get(repo, ("—", ""))
        version = exact_version(img)
        if version is None and img in BUILT_ON:
            built = exact_version(BUILT_ON[img])
            version = f"{built} (по образу `{BUILT_ON[img]}`)" if built else None
        version = version or "образ не скачан локально"
        lines.append(f"| `{img}` | {version} | {lic} | {role} | {where} |")
    lines += [
        "",
        "Собственные образы: `backend` (python:3.12-slim + зависимости бэкенда), "
        "`fsp-registry-mock` (python:3.12-slim), `frontend` (node:22-alpine, только для dev). "
        "На стенде фронт собирается в статику одноразовым контейнером `node:22-alpine` "
        "и раздаётся Caddy.",
        "",
    ]
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--backend-container", default="fsp-talent-backend-1")
    ap.add_argument("--mock-container", default="fsp-talent-fsp-registry-mock-1")
    ap.add_argument("--backend-json", type=Path)
    ap.add_argument("--mock-json", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "docs/solution/07_libraries.md")
    args = ap.parse_args(argv)

    pyproject = tomllib.loads((ROOT / "backend/pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    mock_reqs = [
        line.strip()
        for line in (ROOT / "services/fsp-registry-mock/requirements.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.startswith("#")
    ]
    backend_inv = inventory(
        args.backend_container, "/app/backend/pyproject.toml", args.backend_json
    )
    mock_inv = inventory(args.mock_container, "/srv/requirements.txt", args.mock_json)
    front_lines, odd = frontend_section()

    lines = [
        "# 7. Библиотеки и компоненты с версиями",
        "",
        "<!-- Файл сгенерирован: python docs/solution/tools/gen_libraries.py. "
        "Не править руками. -->",
        "",
        f"Снято {dt.date.today():%d.%m.%Y} с локального dev-стека: версии Python-пакетов — "
        "из установленных в контейнерах, версии npm — из `package-lock.json`, образы — "
        "из compose-файлов и Dockerfile. Лицензия проекта — MIT (`LICENSE`).",
        "",
        "**Лицензии.** Все компоненты — открытые: MIT, BSD, Apache-2.0, ISC, PSF и аналогичные "
        "разрешительные. MPL-2.0 (certifi — корневые сертификаты; lightningcss и caniuse-lite — "
        "только при сборке CSS) — слабый копилефт на уровне файла, на наш код не распространяется; "
        "шрифты Inter и JetBrains Mono — SIL OFL-1.1. Проприетарных и закрытых компонентов нет. "
        "LLM — открытая модель Qwen2.5-1.5B-Instruct (Apache-2.0, GGUF Q4_K_M) в llama.cpp (MIT) "
        "на нашем же сервере; внешний LLM-провайдер не нужен.",
        "",
        "## Платформа",
        "",
        "| Компонент | Версия |",
        "|---|---|",
        f"| Python (бэкенд, мок реестра) | {backend_inv['python'] if backend_inv else '3.12'} "
        f"(в `pyproject.toml`: `{project['requires-python']}`) |",
        "| Node.js (dev-сервер и сборка фронта) | "
        f"{exact_version(BUILT_ON['node:22-alpine']) or '22'} "
        "(образ `node:22-alpine`) |",
        f"| PostgreSQL | {exact_version('postgres:16-alpine') or '16'} |",
        f"| Keycloak (ФСП ID) | {exact_version('quay.io/keycloak/keycloak:25.0') or '25.0'} |",
        "",
        "## Библиотеки",
        "",
    ]
    lines += python_section(
        "Бэкенд (`backend/pyproject.toml`)",
        backend_inv,
        project["dependencies"],
        project.get("optional-dependencies", {}).get("dev"),
    )
    lines += python_section(
        "Мок реестра ФСП (`services/fsp-registry-mock/requirements.txt`)", mock_inv, mock_reqs
    )
    lines += front_lines
    if odd:
        lines += [
            "Лицензии вне списка MIT/BSD/Apache/ISC/PSF (проверены вручную, все открытые): "
            + "; ".join(odd)
            + ".",
            "",
        ]
    lines += images_section()
    args.out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"записано: {args.out}")
    if backend_inv is None or mock_inv is None:
        print(
            "предупреждение: контейнеры не запущены, версии Python-пакетов не сняты",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Таблица эндпоинтов API по ролям для документации (docs/solution/api_endpoints.md).

Источники:
- `docs/api/openapi.json` — список методов, назначение (summary), коды ответов;
- код роутеров `backend/app/**` (разбор AST, без импорта приложения) — какая роль нужна:
  зависимости `CandidateUser`, `RecruiterUser`, `AdminUser`, `CandidateOrRecruiter`, `AnyUser`
  из `app/core/security.py`.

Запуск из корня репозитория (только стандартная библиотека Python 3.11+):
    python docs/solution/tools/gen_api_table.py            # перезаписать api_endpoints.md
    python docs/solution/tools/gen_api_table.py --check    # код 1, если файл устарел
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}

# Зависимость в сигнатуре обработчика → роли
DEPENDENCY_ROLES: dict[str, tuple[str, ...]] = {
    "CandidateUser": ("candidate",),
    "RecruiterUser": ("recruiter",),
    "AdminUser": ("admin",),
    "CandidateOrRecruiter": ("candidate", "recruiter"),
    "AnyUser": ("any",),
}
ROLE_LABELS = {
    "candidate": "соискатель",
    "recruiter": "рекрутер",
    "admin": "админ",
    "any": "любой вошедший",
    "public": "без входа",
    "registry": "реестр ФСП (HMAC-подпись)",
}
ROLE_ORDER = ["public", "registry", "any", "candidate", "recruiter", "admin"]

TAG_TITLES = {
    "system": "Служебное",
    "auth": "Регистрация, вход, ФСП ID",
    "users": "Согласия 152-ФЗ",
    "catalog": "Справочники",
    "candidates": "Кабинет соискателя и банк кандидатов",
    "companies": "Компания рекрутера",
    "testing": "Опрос, адаптивный тест, грейд",
    "fsp": "Достижения ФСП",
    "matching": "Потребности и подборка",
    "invitations": "Приглашения и выход на контакт",
    "vacancies": "Вакансии и отклики",
    "tasks": "Регулярные задания",
    "admin": "Кабинет администратора, жалобы",
    "eval": "Валидация и метрики",
}


def _str_kw(call: ast.Call, name: str) -> str | None:
    for kw in call.keywords:
        if (
            kw.arg == name
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, str)
        ):
            return kw.value.value
    return None


def _roles_from_require_role(node: ast.AST) -> tuple[str, ...]:
    """`Depends(require_role(Role.admin, ...))` в dependencies=[...] декоратора."""
    roles: list[str] = []
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Name)
            and sub.func.id == "require_role"
        ):
            for arg in sub.args:
                if isinstance(arg, ast.Attribute):
                    roles.append(arg.attr)
    return tuple(roles)


def _annotation_names(fn: ast.AsyncFunctionDef | ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    args = fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs
    for arg in args:
        if arg.annotation is not None:
            for sub in ast.walk(arg.annotation):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
    return names


def roles_from_code(app_dir: Path) -> dict[tuple[str, str], tuple[str, ...]]:
    """(МЕТОД, /api/путь) → роли по коду роутеров."""
    result: dict[tuple[str, str], tuple[str, ...]] = {}
    for path in sorted(app_dir.rglob("*.py")):
        if "engine" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        prefixes: dict[str, str] = {}
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "APIRouter"
            ):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        prefixes[target.id] = _str_kw(node.value, "prefix") or ""
        if not prefixes:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr in HTTP_METHODS
                    and isinstance(dec.func.value, ast.Name)
                    and dec.func.value.id in prefixes
                    and dec.args
                    and isinstance(dec.args[0], ast.Constant)
                ):
                    continue
                full = "/api" + prefixes[dec.func.value.id] + str(dec.args[0].value)
                roles: list[str] = []
                for name in _annotation_names(node):
                    roles.extend(DEPENDENCY_ROLES.get(name, ()))
                for kw in dec.keywords:
                    if kw.arg == "dependencies":
                        roles.extend(_roles_from_require_role(kw.value))
                result[(dec.func.attr.upper(), full)] = tuple(dict.fromkeys(roles))
    return result


def who(op: dict, roles: tuple[str, ...] | None) -> tuple[str, ...]:
    params = {
        p.get("name", "").lower() for p in op.get("parameters", []) if p.get("in") == "header"
    }
    if "x-fsp-signature" in params:
        return ("registry",)
    if roles:
        return roles
    if op.get("security"):
        return ("any",)
    return ("public",)


def md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def error_catalog(spec: dict) -> list[str]:
    """Коды ошибок из примеров ответов: (HTTP-статус, code) → сообщение и число методов."""
    found: dict[tuple[str, str], tuple[str, int]] = {}
    for ops in spec["paths"].values():
        for method, op in ops.items():
            if method not in HTTP_METHODS:
                continue
            for status, resp in op.get("responses", {}).items():
                if status.startswith("2"):
                    continue
                content = resp.get("content", {}).get("application/json", {})
                examples = list((content.get("examples") or {}).values())
                if "example" in content:
                    examples.append({"value": content["example"]})
                for ex in examples:
                    value = ex.get("value") or {}
                    code = value.get("code")
                    if not code:
                        continue
                    msg, n = found.get((status, code), (value.get("message", ""), 0))
                    found[(status, code)] = (msg, n + 1)
    lines = [
        "## Коды ошибок",
        "",
        'Тело любой ошибки: `{"code": "...", "message": "...", "details": {...}}`. '
        "`code` — машинный код (англ.), `message` — текст для пользователя (рус.), `details` — "
        "подробности (поля с ошибками, id объекта, дата, когда действие станет доступно).",
        "",
        "| HTTP | code | Пример сообщения | Методов |",
        "|---|---|---|---|",
    ]
    for (status, code), (msg, n) in sorted(found.items()):
        lines.append(f"| {status} | `{code}` | {md_escape(msg)} | {n} |")
    lines.append("")
    return lines


def build(openapi_path: Path, app_dir: Path) -> tuple[str, list[str]]:
    spec = json.loads(openapi_path.read_text(encoding="utf-8"))
    code_roles = roles_from_code(app_dir)
    warnings: list[str] = []
    groups: dict[str, list[tuple[str, str, tuple[str, ...], str, str]]] = defaultdict(list)
    per_role: Counter[str] = Counter()
    total = 0
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            if method not in HTTP_METHODS:
                continue
            total += 1
            key = (method.upper(), path)
            if key not in code_roles:
                warnings.append(f"нет в коде роутеров: {method.upper()} {path}")
            roles = who(op, code_roles.get(key))
            for r in roles:
                per_role[r] += 1
            codes = ", ".join(sorted(op.get("responses", {})))
            tag = (op.get("tags") or ["other"])[0]
            groups[tag].append(
                (method.upper(), path, roles, md_escape(op.get("summary", "")), codes)
            )
    for key in code_roles:
        method, path = key
        if path not in spec["paths"] or method.lower() not in spec["paths"][path]:
            warnings.append(f"нет в openapi.json: {method} {path} (перевыгрузите схему)")

    info = spec.get("info", {})
    lines = [
        "# Приложение к разделу 6. Эндпоинты API по ролям",
        "",
        "<!-- Файл сгенерирован: python docs/solution/tools/gen_api_table.py. "
        "Не править руками. -->",
        "",
        f"Источник — `docs/api/openapi.json` ({info.get('title', '')} {info.get('version', '')}, "
        f"OpenAPI {spec.get('openapi', '')}); роль — по зависимостям в коде роутеров "
        "`backend/app/**/router.py`. Подробные схемы запросов и ответов, примеры и описания "
        "кодов ошибок — в Swagger `/api/docs`.",
        "",
        f"Всего методов: **{total}**.",
        "",
        "| Кто вызывает | Методов |",
        "|---|---|",
    ]
    for r in ROLE_ORDER:
        if per_role.get(r):
            lines.append(f"| {ROLE_LABELS[r]} | {per_role[r]} |")
    lines += [
        "",
        "Метод, доступный двум ролям, учтён в обеих строках. "
        "«Без входа» — публичные методы (регистрация, вход, справочники, health). "
        "«Любой вошедший» — нужен JWT, роль не важна. Метод с двумя ролями отдаёт каждой свою "
        "проекцию данных (например, приглашения: кандидат — полученные, "
        "рекрутер — своей компании).",
        "",
    ]
    order = list(TAG_TITLES) + sorted(set(groups) - set(TAG_TITLES))
    for tag in order:
        rows = groups.get(tag)
        if not rows:
            continue
        lines += [
            f"## {TAG_TITLES.get(tag, tag)} (`{tag}`)",
            "",
            "| Метод | Путь | Кто | Что делает | Коды ответов |",
            "|---|---|---|---|---|",
        ]
        for method, path, roles, summary, codes in rows:
            role_text = ", ".join(ROLE_LABELS[r] for r in roles)
            lines.append(f"| {method} | `{path}` | {role_text} | {summary} | {codes} |")
        lines.append("")
    lines += error_catalog(spec)
    return "\n".join(lines), warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--openapi", type=Path, default=ROOT / "docs/api/openapi.json")
    parser.add_argument("--app-dir", type=Path, default=ROOT / "backend/app")
    parser.add_argument("--out", type=Path, default=ROOT / "docs/solution/api_endpoints.md")
    parser.add_argument("--check", action="store_true", help="только проверить актуальность")
    args = parser.parse_args(argv)

    text, warnings = build(args.openapi, args.app_dir)
    for w in warnings:
        print(f"предупреждение: {w}", file=sys.stderr)
    if args.check:
        current = args.out.read_text(encoding="utf-8") if args.out.exists() else ""
        if current != text:
            print(f"{args.out} устарел — запустите без --check", file=sys.stderr)
            return 1
        print("api_endpoints.md актуален")
        return 0
    args.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"записано: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

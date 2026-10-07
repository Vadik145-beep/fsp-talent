"""Опись установленных Python-пакетов: версия, лицензия, прямая или транзитивная зависимость.

Запускается ВНУТРИ контейнера (там стоят ровно те версии, что уходят на стенд), печатает JSON:
    docker exec -i fsp-talent-backend-1 python - /app/backend/pyproject.toml < pip_inventory.py
    docker exec -i fsp-talent-fsp-registry-mock-1 python - /srv/requirements.txt < pip_inventory.py

Аргумент — файл с прямыми зависимостями: pyproject.toml ([project].dependencies) или
requirements.txt. В опись попадает замыкание прямых зависимостей (с учётом extras и маркеров
окружения). Обычно вызывается из gen_libraries.py, руками запускать не нужно.
"""

from __future__ import annotations

import importlib.metadata as md
import json
import platform
import re
import sys

try:  # packaging есть внутри pip — им проверяем маркеры окружения
    from pip._vendor.packaging.requirements import Requirement
except ImportError:  # pragma: no cover
    from packaging.requirements import Requirement  # type: ignore[no-redef]


def canon(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def direct_requirements(path: str) -> list[str]:
    if path.endswith(".toml"):
        import tomllib

        with open(path, "rb") as fh:
            return list(tomllib.load(fh)["project"]["dependencies"])
    reqs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if line and not line.startswith("-"):
                reqs.append(line)
    return reqs


def license_of(dist: md.Distribution) -> str:
    meta = dist.metadata
    expr = meta.get("License-Expression")
    if expr:
        return expr.strip()
    classifiers = [
        c.split("::")[-1].strip()
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    lic = (meta.get("License") or "").strip()
    if lic and len(lic) <= 40 and "\n" not in lic and lic.upper() != "UNKNOWN":
        return lic
    if classifiers:
        return "; ".join(dict.fromkeys(classifiers))
    return lic.splitlines()[0][:80] if lic else "—"


def main() -> None:
    dists = {canon(d.metadata["Name"]): d for d in md.distributions()}
    direct = [Requirement(r) for r in direct_requirements(sys.argv[1])]
    direct_names = {canon(r.name): str(r) for r in direct}

    # обход замыкания: (пакет, набор extras)
    seen: dict[str, set[str]] = {}
    stack: list[tuple[str, set[str]]] = [(canon(r.name), set(r.extras)) for r in direct]
    while stack:
        name, extras = stack.pop()
        if name not in dists:
            continue
        before = seen.get(name)
        if before is not None and extras <= before:
            continue
        seen[name] = (before or set()) | extras
        for raw in dists[name].requires or []:
            req = Requirement(raw)
            envs = [{"extra": e} for e in seen[name]] or [{"extra": ""}]
            if req.marker is None or any(req.marker.evaluate(env) for env in envs):
                stack.append((canon(req.name), set(req.extras)))

    packages = []
    for name in sorted(seen):
        dist = dists[name]
        packages.append(
            {
                "name": dist.metadata["Name"],
                "version": dist.version,
                "license": license_of(dist),
                "summary": (dist.metadata.get("Summary") or "").strip(),
                "direct": name in direct_names,
                "requirement": direct_names.get(name),
            }
        )
    missing = [spec for name, spec in direct_names.items() if name not in dists]
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "packages": packages,
                "missing": missing,
            },
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    main()

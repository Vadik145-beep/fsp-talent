"""Общее для скриптов валидации: пути, seed, подключение пакета бэкенда."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DATA_DIR = REPO_ROOT / "data" / "validation"
DOCS_DIR = REPO_ROOT / "docs" / "validation"
IMG_DIR = DOCS_DIR / "img"

SEED = 20261011
N_CANDIDATES = 1200
N_NEEDS = 100

SPECS = ["backend", "frontend", "mobile", "data_ml", "qa", "devops"]
SPEC_LABELS = {
    "backend": "Backend",
    "frontend": "Frontend",
    "mobile": "Mobile",
    "data_ml": "Data Science / ML",
    "qa": "QA",
    "devops": "DevOps",
}
GRADES = ["intern", "junior", "middle", "senior"]
GRADE_LABELS = {"intern": "Стажёр", "junior": "Junior", "middle": "Middle", "senior": "Senior"}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def r3(x: float) -> float:
    return round(float(x), 3)


def r4(x: float) -> float:
    return round(float(x), 4)

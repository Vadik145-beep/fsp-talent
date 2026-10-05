"""Загрузка синтетического реестра из JSON и расчёт сводки по участнику."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "participants.json"
LEVEL_ORDER = {"regional": 1, "national": 2, "international": 3}


@dataclass
class Registry:
    disciplines: list[dict]
    levels: list[dict]
    # fsp_id -> {"profile": <Participant dict>, "achievements": [<Achievement dict>]}
    participants: dict[str, dict]


def _is_prize(result: dict) -> bool:
    return result["kind"] == "diploma" or (result["kind"] == "place" and result["place"] <= 3)


def summarize(achievements: list[dict]) -> dict:
    levels = [a["level"]["code"] for a in achievements]
    disciplines = list(dict.fromkeys(a["discipline"]["code"] for a in achievements))
    return {
        "achievements_count": len(achievements),
        "rating_points_total": sum(a["rating_points"] for a in achievements),
        "disciplines": disciplines,
        "best_level": max(levels, key=LEVEL_ORDER.__getitem__) if levels else None,
        "prizes_count": sum(1 for a in achievements if _is_prize(a["result"])),
        "last_achievement_date": max((a["date"] for a in achievements), default=None),
    }


def load_registry(path: str | Path | None = None) -> Registry:
    path = Path(path or os.environ.get("FSP_MOCK_DATA_PATH") or DEFAULT_PATH)
    raw = json.loads(path.read_text(encoding="utf-8"))
    updated_at = raw["meta"]["updated_at"]
    participants: dict[str, dict] = {}
    for p in raw["participants"]:
        achievements = p["achievements"]
        profile = {k: v for k, v in p.items() if k != "achievements"}
        profile["has_history"] = bool(achievements)
        profile["summary"] = summarize(achievements)
        profile["updated_at"] = updated_at
        participants[p["fsp_id"]] = {"profile": profile, "achievements": achievements}
    return Registry(disciplines=raw["disciplines"], levels=raw["levels"], participants=participants)

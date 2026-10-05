"""Проверки самих данных: детерминированность генератора и правдоподобие."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "participants.json"


def _generator():
    spec = importlib.util.spec_from_file_location(
        "generate_participants", ROOT / "tools" / "generate_participants.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_committed_json_matches_generator():
    """Закоммиченный JSON совпадает с тем, что даёт генератор (никто не правил руками)."""
    assert DATA.read_text(encoding="utf-8") == _generator().render()


def test_data_is_plausible():
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    assert raw["meta"]["synthetic"] is True
    people = raw["participants"]
    assert [p["fsp_id"] for p in people] == [f"FSP-{n:06d}" for n in range(1, 41)]
    assert len({p["full_name"] for p in people}) == 40
    counts = [len(p["achievements"]) for p in people]
    assert all(c >= 1 for c in counts[:30]) and all(c == 0 for c in counts[30:])
    for p in people:
        for a in p["achievements"]:
            assert a["date"] > p["registered_at"]
            assert a["date"] <= "2026-10-01"
            if a["result"]["kind"] == "place":
                assert 1 <= a["result"]["place"] <= a["competition"]["participants_total"]
            assert a["rating_points"] > 0

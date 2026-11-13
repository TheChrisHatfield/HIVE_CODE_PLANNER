from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _tournament():
    path = Path(__file__).resolve().parents[1] / "scripts" / "sandbox_rank_tournament.py"
    spec = importlib.util.spec_from_file_location("sandbox_rank_tournament", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sandbox_rank_tournament"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_guard_signal_ignores_guard_in_filename() -> None:
    t = _tournament()
    row = {
        "scenario": (
            "hard-negative: no static defect; signals dead_setting "
            "(scripts/auto_hivectm_guard_e2e.py)"
        )
    }
    assert t.guard_signal(row) == 0.0


def test_guard_signal_counts_guard_clause_word() -> None:
    t = _tournament()
    assert t.guard_signal({"scenario": "swallowed return behind a guard clause"}) == 1.0
    assert t.guard_signal({"scenario": "unguarded except"}) == 0.0

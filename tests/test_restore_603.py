from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAN_LOOP = ROOT / "scripts" / "gan-loop"
SCRIPTS = ROOT / "scripts"
for path in (str(GAN_LOOP), str(SCRIPTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

ZEROS = {
    "recent_fix_commits": 0,
    "thin_test": 0,
    "wiring_hop": 0,
    "dead_setting": 0,
    "reverted": 0,
    "split_stores": 0,
}


def _load():
    spec = importlib.util.spec_from_file_location("restore_603", GAN_LOOP / "_restore_603.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_import_does_not_write_mixed():
    import sandbox_rank_gan as gan

    before = gan.MIXED.read_bytes() if gan.MIXED.exists() else None
    _load()
    after = gan.MIXED.read_bytes() if gan.MIXED.exists() else None
    assert after == before


def test_locked_parts_drops_gan_prefix():
    restore = _load()
    rows = [
        {"file": "repo/a.py", "outcome": "review-failed", "signals": ZEROS, "scenario": "bug"},
        {"file": "gan/weak.py", "outcome": "empty", "signals": ZEROS, "scenario": "hard-negative:gan"},
        {"file": "repo/b.py", "outcome": "empty", "signals": ZEROS, "scenario": "blank"},
    ]
    base, bugs, empties = restore.locked_parts(rows)
    assert [row["file"] for row in base] == ["repo/a.py", "repo/b.py"]
    assert bugs == [rows[0]]
    assert empties == [rows[2]]


def test_composition_splits_on_scenario_not_dict_equality():
    restore = _load()
    thin = dict(ZEROS)
    thin["thin_test"] = 1
    empties = [
        {"file": "same.py", "outcome": "empty", "signals": thin, "scenario": "hard-negative: x"},
        {"file": "same.py", "outcome": "empty", "signals": thin, "scenario": "blank"},
        {"file": "no_signals.py", "outcome": "empty", "scenario": "blank"},
    ]
    hard_n, single, blanks_n, blank_zero = restore.composition(empties)
    assert (hard_n, single, blanks_n, blank_zero) == (1, 1, 2, 0)

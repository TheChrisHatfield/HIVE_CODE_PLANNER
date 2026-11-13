from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GAN_LOOP = ROOT / "scripts" / "gan-loop"
SCRIPTS = ROOT / "scripts"
for path in (str(GAN_LOOP), str(SCRIPTS)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _load():
    spec = importlib.util.spec_from_file_location("add_weak", GAN_LOOP / "_add_weak.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _signals(**on: int) -> dict:
    keys = (
        "recent_fix_commits",
        "thin_test",
        "wiring_hop",
        "dead_setting",
        "reverted",
        "split_stores",
    )
    return {key: float(on.get(key, 0)) for key in keys}


def _row(name: str, lit: list[str], *, accepted: bool, fitted: float, **on: int) -> dict:
    return {
        "name": name,
        "lit": lit,
        "accepted": accepted,
        "findings": [],
        "fitted": fitted,
        "hand": fitted,
        "signals": _signals(**on),
    }


def test_import_does_not_write_mixed():
    import sandbox_rank_gan as gan

    before = gan.MIXED.read_bytes() if gan.MIXED.exists() else None
    _load()
    after = gan.MIXED.read_bytes() if gan.MIXED.exists() else None
    assert after == before


def test_unaccepted_match_is_not_weak_ok():
    add_weak = _load()
    scored = _row(
        "sauna_timer.py",
        ["thin_test", "dead_setting"],
        accepted=False,
        fitted=2.0,
        thin_test=1,
        dead_setting=1,
    )
    assert add_weak.weak_ok(scored, add_weak.EXPECT["sauna_timer.py"]) is False


def test_wiring_hop_below_floor_still_ok_when_accepted():
    add_weak = _load()
    scored = _row(
        "test_radio_probe.py",
        ["wiring_hop"],
        accepted=True,
        fitted=0.5,
        wiring_hop=1,
    )
    assert add_weak.weak_ok(scored, add_weak.EXPECT["test_radio_probe.py"]) is True


def test_accepted_to_rows_drop_raises_instead_of_mislabeling():
    add_weak = _load()
    picked = [
        _row("sauna_timer.py", ["thin_test", "dead_setting"], accepted=False, fitted=2.0, thin_test=1, dead_setting=1),
        _row("film_roll.py", ["thin_test", "dead_setting"], accepted=True, fitted=2.0, thin_test=1, dead_setting=1),
    ]
    with pytest.raises(SystemExit, match="dropped 1 weak picks"):
        add_weak.label_weak_rows(picked)

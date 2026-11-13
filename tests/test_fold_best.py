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
    spec = importlib.util.spec_from_file_location("fold_best", GAN_LOOP / "_fold_best.py")
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


def _row(*, accepted: bool, fitted: float = 4.168, findings=None, lit=None) -> dict:
    return {
        "name": "thin_wire.py",
        "lit": lit if lit is not None else ["thin_test", "wiring_hop"],
        "accepted": accepted,
        "findings": [] if findings is None else findings,
        "fitted": fitted,
        "signals": _signals(thin_test=1, wiring_hop=1),
    }


def test_import_does_not_write_mixed():
    import sandbox_rank_gan as gan

    before = gan.MIXED.read_bytes() if gan.MIXED.exists() else None
    _load()
    after = gan.MIXED.read_bytes() if gan.MIXED.exists() else None
    assert after == before


def test_unaccepted_thin_wiring_is_not_a_best_pick():
    fold = _load()
    assert fold.is_best_pick(_row(accepted=False)) is False
    assert fold.is_best_pick(_row(accepted=True)) is True


def test_accepted_to_rows_drop_raises_instead_of_mislabeling():
    fold = _load()
    picked = [_row(accepted=False), _row(accepted=True)]
    picked[1]["name"] = "ok.py"
    with pytest.raises(SystemExit, match="dropped 1 best picks"):
        fold.label_best_rows(picked)

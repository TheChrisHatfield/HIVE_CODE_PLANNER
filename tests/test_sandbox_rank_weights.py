"""Holdout file keys must match rows_outside_fit (slash and first-folder fold)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sandbox_rank_weights.py"


def _mod():
    spec = importlib.util.spec_from_file_location("sandbox_rank_weights_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unused_holdout_drops_backslash_and_first_folder_aliases() -> None:
    unused_holdout_rows = _mod().unused_holdout_rows
    train = ("repo/src/a.py", [1.0, 0.0, 0.0, 0.0, 0.0, 0.0], 1)
    hold_slash = ("repo\\src\\a.py", [0.0, 1.0, 0.0, 0.0, 0.0, 0.0], 0)
    hold_tail = ("src/a.py", [0.0, 1.0, 0.0, 0.0, 0.0, 0.0], 0)
    other = ("src/b.py", [0.0, 1.0, 0.0, 0.0, 0.0, 0.0], 0)
    kept, seen, zeros = unused_holdout_rows([train, hold_slash, hold_tail, other], cut=1)
    assert zeros == 0
    assert seen == 2
    assert [row[0] for row in kept] == ["src/b.py"]

from __future__ import annotations

import importlib.util
from pathlib import Path


def _gd():
    path = Path(__file__).resolve().parents[1] / "scripts" / "sandbox_rank_gd.py"
    spec = importlib.util.spec_from_file_location("sandbox_rank_gd_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_file_count_collapses_case_and_slashes() -> None:
    gd = _gd()
    rows = [
        ("Src\\App.py", [1.0, 0.0, 0.0, 0.0, 0.0, 0.0], 1),
        ("src/app.py", [0.0, 1.0, 0.0, 0.0, 0.0, 0.0], 0),
    ]
    groups = gd.by_file(rows)
    assert len(groups) == 1
    assert gd.file_count(rows) == 1
    assert gd.file_count(groups[next(iter(groups))]) == 1

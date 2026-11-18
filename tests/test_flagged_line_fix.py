"""Line-level fix counts: map current lines through git hunks (no live git)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gan-loop" / "_flagged_line_fix.py"


def _mod():
    spec = importlib.util.spec_from_file_location("flagged_line_fix_under_test", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deletion_hunk_maps_the_line_after_the_hole_to_the_old_file() -> None:
    """@@ -2,2 +2,0 @@ deleted two lines; new line 2 was old line 4 (a,d,e vs a,b,c,d,e)."""
    sweep = _mod()
    hit, parent = sweep._step({1, 2, 3}, [(2, 2, 2, 0)])
    assert hit is False
    assert parent == {1, 4, 5}


def test_insert_hunk_drops_added_lines_and_maps_the_rest() -> None:
    """@@ -1,0 +1,2 @@ inserted two lines; new line 3 was old line 1."""
    sweep = _mod()
    hit, parent = sweep._step({1, 2, 3}, [(1, 0, 1, 2)])
    assert hit is True
    assert parent == {1}


def test_fix_count_walks_an_insert_then_a_deletion() -> None:
    sweep = _mod()
    # Newest first: insert xy, then delete bc (same as git log).
    commits = [
        (True, [(1, 0, 1, 2)]),
        (True, [(2, 2, 2, 0)]),
    ]
    # Current line 4 is d; after reversing the insert it is line 2; after the
    # deletion it is old line 4. Neither hunk rewrites d itself.
    assert sweep.flagged_line_fix_count(commits, {4}) == 0
    # Current line 1 is the inserted x; the insert commit is a hit.
    assert sweep.flagged_line_fix_count(commits, {1}) == 1

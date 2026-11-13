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

spec = importlib.util.spec_from_file_location(
    "fold_families", GAN_LOOP / "_fold_families.py"
)
fold = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fold)


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


def _row(name: str, lit: list[str], *, accepted: bool, findings=None, **on: int) -> dict:
    return {
        "name": name,
        "lit": lit,
        "accepted": accepted,
        "findings": [] if findings is None else findings,
        "signals": _signals(**on),
    }


def test_unparsed_thin_proposal_is_rejected_not_zipped():
    scored = [
        _row("broken.py", ["thin_test"], accepted=False, thin_test=1),
        _row("thin_a.py", ["thin_test"], accepted=True, thin_test=1),
        _row("thin_b.py", ["thin_test"], accepted=True, thin_test=1),
    ]
    buckets, rejected = fold.fill_family_buckets(scored)
    assert [row["name"] for row in buckets["thin"]] == ["thin_a.py", "thin_b.py"]
    assert rejected[0]["name"] == "broken.py"
    picked = [row for group in buckets.values() for row in group]
    labeled = fold.apply_family_labels(picked)
    assert [row["file"] for row in labeled] == ["gan/thin_a.py", "gan/thin_b.py"]
    assert all(row["scenario"] == "hard-negative:gan-family:thin" for row in labeled)


def test_mix_over_global_cap_is_rejected():
    scored = [
        _row(
            "mix_a.py",
            ["thin_test", "dead_setting"],
            accepted=True,
            thin_test=1,
            dead_setting=1,
        ),
        _row(
            "mix_b.py",
            ["thin_test", "split_stores"],
            accepted=True,
            thin_test=1,
            split_stores=1,
        ),
        _row(
            "mix_c.py",
            ["wiring_hop", "dead_setting"],
            accepted=True,
            wiring_hop=1,
            dead_setting=1,
        ),
    ]
    buckets, rejected = fold.fill_family_buckets(scored)
    picked = [row for group in buckets.values() for row in group]
    assert len(picked) == 2
    assert rejected[-1]["name"] == "mix_c.py"
    labeled = fold.apply_family_labels(picked)
    assert labeled[0]["scenario"] == "hard-negative:gan-family:mix-thin-dead"
    assert labeled[1]["scenario"] == "hard-negative:gan-family:mix-thin-split"


def test_accepted_to_rows_drop_raises_instead_of_mislabeling():
    picked = [
        _row("broken.py", ["thin_test"], accepted=False, thin_test=1),
        _row("thin_a.py", ["thin_test"], accepted=True, thin_test=1),
    ]
    with pytest.raises(SystemExit, match="dropped 1 family picks"):
        fold.apply_family_labels(picked)

"""Cursor sessionStart hook — print active feature and Spec Kit paths."""
from __future__ import annotations

import sys
from pathlib import Path

_hooks_dir = Path(__file__).resolve().parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from _bootstrap import bootstrap_hive_planner

bootstrap_hive_planner()

from hive_planner.config import RepoPaths, resolve_root
from hive_planner.spec_drift import check_spec_handoff, parse_active_feature


def main() -> int:
    if not sys.stdin.isatty():
        _ = sys.stdin.read()
    root, _ = resolve_root(None)
    paths = RepoPaths(root=root)
    feature = parse_active_feature(paths)
    if not feature:
        print("Hive: no active feature in AGENTS.md")
        return 0
    handoff = check_spec_handoff(paths, feature)
    print(f"Hive active feature: {feature}")
    for label in (
        f"docs/specs/{feature}/spec.md",
        f"docs/specs/{feature}/plan.md",
        f"docs/specs/{feature}/tasks.md",
        f"docs/delta/20_micro/{feature}.md",
    ):
        status = "ok" if label not in handoff.missing else "MISSING"
        print(f"  [{status}] {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

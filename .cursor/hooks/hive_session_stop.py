"""Cursor stop hook — run spec-drift-check and agents-lint (non-blocking warnings)."""
from __future__ import annotations

import sys
from pathlib import Path

_hooks_dir = Path(__file__).resolve().parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from _bootstrap import bootstrap_hive_planner

bootstrap_hive_planner()

from hive_planner.agents_memory import lint_agents_md
from hive_planner.config import RepoPaths, resolve_root
from hive_planner.spec_drift import check_memory_spec_drift


def main() -> int:
    if not sys.stdin.isatty():
        _ = sys.stdin.read()
    root, _ = resolve_root(None)
    paths = RepoPaths(root=root)
    drift = check_memory_spec_drift(paths, include_agents_facts=True)
    lint = lint_agents_md(paths)
    if not drift.ok:
        print("Hive spec-drift-check: review before handoff", file=sys.stderr)
        for item in drift.drift_items:
            print(f"  drift: {item}", file=sys.stderr)
        for action in drift.spec_actions:
            print(f"  action: {action}", file=sys.stderr)
    if not lint.ok:
        print("Hive agents-lint: errors in AGENTS.md", file=sys.stderr)
        for issue in lint.issues:
            if issue.severity == "error":
                print(f"  {issue.message}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

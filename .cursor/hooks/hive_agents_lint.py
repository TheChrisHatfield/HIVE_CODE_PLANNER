"""Cursor afterFileEdit hook — lint AGENTS.md when edited."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_hooks_dir = Path(__file__).resolve().parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from _bootstrap import bootstrap_hive_planner

bootstrap_hive_planner()

from hive_planner.agents_memory import lint_agents_md
from hive_planner.config import RepoPaths, resolve_root


def main() -> int:
    if sys.stdin.isatty():
        return 0
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    file_path = payload.get("file_path") or payload.get("path") or ""
    if "AGENTS.md" not in str(file_path):
        return 0
    root, _ = resolve_root(None)
    paths = RepoPaths(root=root)
    lint = lint_agents_md(paths)
    if not lint.ok:
        print("Hive agents-lint failed after AGENTS.md edit", file=sys.stderr)
        for issue in lint.issues:
            if issue.severity == "error":
                print(f"  {issue.message}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

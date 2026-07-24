"""Cursor sessionStart hook — inject active feature and Spec Kit paths.

Cursor 3.x requires JSON on stdout (`additional_context` / `env`).
Plain-text stdout is rejected with a JSON parse error.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    try:
        if not sys.stdin.isatty():
            _ = sys.stdin.read()

        _hooks_dir = Path(__file__).resolve().parent
        if str(_hooks_dir) not in sys.path:
            sys.path.insert(0, str(_hooks_dir))

        from _bootstrap import bootstrap_hive_planner

        bootstrap_hive_planner()

        from hive_planner.config import RepoPaths, resolve_root
        from hive_planner.spec_drift import check_spec_handoff, parse_active_feature

        root, _ = resolve_root(None)
        paths = RepoPaths(root=root)
        feature = parse_active_feature(paths)
        if not feature:
            print(json.dumps({"additional_context": "Hive: no active feature in AGENTS.md"}))
            return 0
        handoff = check_spec_handoff(paths, feature)
        lines = [f"Hive active feature: {feature}"]
        for label in (
            f"docs/specs/{feature}/spec.md",
            f"docs/specs/{feature}/plan.md",
            f"docs/specs/{feature}/tasks.md",
            f"docs/delta/20_micro/{feature}.md",
        ):
            status = "ok" if label not in handoff.missing else "MISSING"
            lines.append(f"  [{status}] {label}")
        print(json.dumps({"additional_context": "\n".join(lines)}))
        return 0
    except Exception as exc:  # noqa: BLE001 — Cursor hooks must fail-open with JSON
        print(f"[hive_session_start] failed: {exc}", file=sys.stderr)
        print(json.dumps({"additional_context": f"Hive sessionStart hook error: {exc}"}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

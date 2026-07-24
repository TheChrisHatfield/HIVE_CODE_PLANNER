"""Cursor workspaceOpen hook — register Hive project-local plugins.

Cursor 3.x does not auto-load `.cursor/plugins/*`. Return absolute paths via
`pluginPaths` so hive-continual-learning hooks/skills/agents load for this workspace.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    try:
        if not sys.stdin.isatty():
            _ = sys.stdin.read()

        project_dir = os.environ.get("CURSOR_PROJECT_DIR")
        if project_dir:
            root = Path(project_dir)
        else:
            root = Path(__file__).resolve().parents[2]

        plugin = root / ".cursor" / "plugins" / "hive-continual-learning"
        paths: list[str] = []
        if (plugin / ".cursor-plugin" / "plugin.json").is_file():
            paths.append(str(plugin.resolve()))

        print(json.dumps({"pluginPaths": paths}))
        return 0
    except Exception as exc:  # noqa: BLE001 — Cursor hooks must fail-open with JSON
        print(f"[hive_workspace_open] failed: {exc}", file=sys.stderr)
        print(json.dumps({"pluginPaths": []}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

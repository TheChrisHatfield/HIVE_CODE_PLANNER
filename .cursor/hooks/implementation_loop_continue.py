"""Stop hook: ping the agent when CodeSpec checker failed or stalled.

Stdout is always JSON (`{}` or `{"followup_message": ...}`).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

DEFAULT_PAUSE = 9


def main() -> int:
    try:
        if not sys.stdin.isatty():
            _ = sys.stdin.read()
        hooks_dir = Path(__file__).resolve().parent
        if str(hooks_dir) not in sys.path:
            sys.path.insert(0, str(hooks_dir))
        from _bootstrap import bootstrap_hive_planner

        bootstrap_hive_planner()
        from hive_planner.config import resolve_root
        from hive_planner.implementation_loop import (
            codespec_followup_message,
            codespec_should_followup,
        )

        root, _ = resolve_root(None)
        if not codespec_should_followup(root):
            print(json.dumps({}))
            return 0
        pause = DEFAULT_PAUSE
        cont = root / ".hive" / "implementation-loop" / "continue.json"
        if cont.is_file():
            try:
                raw = json.loads(cont.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and raw.get("pause_seconds") is not None:
                    pause = max(0, int(raw["pause_seconds"]))
            except (OSError, ValueError, TypeError):
                pause = DEFAULT_PAUSE
        if pause:
            time.sleep(pause)
        print(json.dumps({"followup_message": codespec_followup_message(root)}))
        return 0
    except Exception as exc:  # noqa: BLE001 — Cursor hooks must fail-open
        print(f"[implementation_loop_continue] failed: {exc}", file=sys.stderr)
        print(json.dumps({}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

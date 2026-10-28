"""Stop hook: wait the bug-hunt pause, then start the next inference pass.

Stdlib only. install_bug_hunt copies this file to `.cursor/hooks/bug_hunt_continue.py`.
Stdout is always JSON (`{}` or `{"followup_message": ...}`).
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

CONTINUE_REL = Path(".hive") / "bug-hunt" / "continue.json"
DEFAULT_PAUSE_SECONDS = 10
# time.sleep overflows past about 292 years, so a pause beyond this is a typo.
MAX_SLEEP_SECONDS = 9_223_372_036
FOLLOWUP_MESSAGE = (
    "The bug hunt is still running. This is the next inference pass. "
    "Read .cursor/commands/bug-hunt.md and do one iteration, then end the turn. "
    "Do not ask whether to continue. "
    "At the end, write .hive/bug-hunt/continue.json using the pause, ceiling, "
    "committed count, and consecutive-empty count named in that script. "
    "Set active true unless a stop condition is met. If a stop condition is met, set active false."
)
_ABORT_STATUSES = {"aborted", "cancelled", "canceled", "error"}


def _is_active(value: object) -> bool:
    if value is True:
        return True
    if isinstance(value, int) and not isinstance(value, bool) and value == 1:
        return True
    if isinstance(value, float) and value == 1.0:
        return True
    if isinstance(value, str) and value.strip().lower() in {"true", "yes", "1"}:
        return True
    return False


def _coerce_pause(raw: object) -> int | None:
    """Whole numbers count, including numeric strings and 10.0. Anything else does not."""
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int):
        return raw if 0 <= raw <= MAX_SLEEP_SECONDS else None
    if isinstance(raw, float):
        if raw.is_integer() and 0 <= raw <= MAX_SLEEP_SECONDS:
            return int(raw)
        return None
    if isinstance(raw, str):
        text = raw.strip()
        try:
            value = int(text)
        except ValueError:
            try:
                number = float(text)
            except ValueError:
                return None
            if number.is_integer() and 0 <= number <= MAX_SLEEP_SECONDS:
                return int(number)
            return None
        return value if 0 <= value <= MAX_SLEEP_SECONDS else None
    return None


_PAUSE_IN_SCRIPT = re.compile(r"This run's pause is (\d+) seconds")


def pause_from_script(root: Path) -> int | None:
    """Pause written into the installed script, when the continue file omits it."""
    for rel in (Path(".cursor") / "commands" / "bug-hunt.md", Path("scripts") / "bug-hunt.md"):
        path = Path(root) / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        match = _PAUSE_IN_SCRIPT.search(text)
        if match:
            return int(match.group(1))
    return None


def plan_continue(state: object) -> tuple[int, dict]:
    """Return the wait and the hook payload. An inactive file does not restart the hunt."""
    if not isinstance(state, dict) or not _is_active(state.get("active")):
        return 0, {}
    pause = _coerce_pause(state.get("pause_seconds", DEFAULT_PAUSE_SECONDS))
    if pause is None:
        return 0, {}
    return pause, {"followup_message": FOLLOWUP_MESSAGE}


def _read_state(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def find_hunt_root(start: Path | None = None) -> Path:
    """Repo that holds the continue file. Do not cross into a parent project."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / CONTINUE_REL).is_file():
            return candidate
        if (candidate / ".git").exists() or (candidate / ".cursor" / "hooks.json").is_file():
            return candidate
    return current


def consume_continue(root: Path) -> None:
    """Clear a pending restart so a later stop does not start another pass."""
    path = Path(root) / CONTINUE_REL
    state = _read_state(path)
    if not isinstance(state, dict) or not _is_active(state.get("active")):
        return
    state["active"] = False
    _write_state(path, state)


def apply_continue(root: Path, *, sleep) -> dict:
    """Consume one continue token, wait its pause, and return the next-pass payload."""
    path = Path(root) / CONTINUE_REL
    state = _read_state(path)
    if not isinstance(state, dict) or not _is_active(state.get("active")):
        return {}
    if "pause_seconds" not in state:
        script_pause = pause_from_script(root)
        if script_pause is not None:
            state["pause_seconds"] = script_pause
    if _coerce_pause(state.get("pause_seconds", DEFAULT_PAUSE_SECONDS)) is None:
        script_pause = pause_from_script(root)
        if script_pause is not None:
            state["pause_seconds"] = script_pause
    # The agent should clear the token when a stop condition is met. A crash can
    # leave active true after the last iteration, so re-check the stop conditions
    # that the state file itself can prove before waiting for another pass.
    ceiling = state.get("ceiling")
    committed = state.get("committed", 0)
    consecutive_empty = state.get("consecutive_empty", 0)
    try:
        ceiling_met = ceiling is not None and int(committed) >= int(ceiling)
    except (TypeError, ValueError):
        ceiling_met = False
    try:
        empties_met = int(consecutive_empty) >= 2
    except (TypeError, ValueError):
        empties_met = False
    if ceiling_met or empties_met or _is_active(state.get("stop")):
        state["active"] = False
        _write_state(path, state)
        return {}
    pause, payload = plan_continue(state)
    if not payload:
        state["active"] = False
        _write_state(path, state)
        return {}
    if pause > 0:
        sleep(pause)
    state["active"] = False
    _write_state(path, state)
    return payload


def _status(raw: str) -> str:
    if not raw.strip():
        return ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    return str(parsed.get("status") or "").strip().lower()


def main() -> int:
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
        if _status(raw) in _ABORT_STATUSES:
            consume_continue(find_hunt_root())
            print(json.dumps({}), flush=True)
            return 0
        payload = apply_continue(find_hunt_root(), sleep=time.sleep)
        print(json.dumps(payload), flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001 — Cursor hooks must fail open with JSON
        print(f"[bug_hunt_continue] failed: {exc}", file=sys.stderr)
        print(json.dumps({}), flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

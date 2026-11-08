"""Stop hook: wait the bug-hunt pause, then start the next inference pass.

Stdlib only. install_bug_hunt copies this file to `.cursor/hooks/bug_hunt_continue.py`.
Stdout is always JSON (`{}` or `{"followup_message": ...}`).
"""

from __future__ import annotations

import ctypes
import json
import os
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
            text = _read_state_text(path)
        except (OSError, UnicodeError):
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


def _read_state_text(path: Path) -> str:
    """Read continue.json saved as UTF-8 (with or without BOM) or UTF-16."""
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-16")


def _read_state(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        parsed = json.loads(_read_state_text(path))
    except (OSError, UnicodeError, json.JSONDecodeError):
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
    lock = path.with_name(path.name + ".lock")
    if not path.is_file() or not _acquire_lock(lock):
        return
    try:
        state = _read_state(path)
        if not isinstance(state, dict):
            return
        if not _is_active(state.get("active")) and "resume_pid" not in state:
            return
        state["active"] = False
        state.pop("resume_pid", None)
        state.pop("resume_deadline", None)
        _write_state(path, state)
    finally:
        _release_lock(lock)


def _whole_count(raw: object) -> int | None:
    """A non-negative whole number. Booleans and fractions are not counts."""
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int):
        return raw if raw >= 0 else None
    if isinstance(raw, float):
        if raw.is_integer() and raw >= 0:
            return int(raw)
        return None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            value = int(text)
        except ValueError:
            try:
                number = float(text)
            except ValueError:
                return None
            if not number.is_integer():
                return None
            value = int(number)
        return value if value >= 0 else None
    return None


_LOCK_STALE_SECONDS = 30
_RESUME_GRACE_SECONDS = 30


def _pid_alive(pid: int) -> bool:
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel.OpenProcess(0x1000, False, pid)
        if handle:
            kernel.CloseHandle(handle)
            return True
        return ctypes.get_last_error() == 5
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _lock_abandoned(lock: Path) -> bool:
    """A lock whose owner is gone can be taken. A live owner keeps it."""
    try:
        raw = lock.read_bytes().strip()
    except OSError:
        return False
    try:
        pid = int(raw)
    except ValueError:
        try:
            age = time.time() - lock.stat().st_mtime
        except OSError:
            return False
        return age >= _LOCK_STALE_SECONDS
    return not _pid_alive(pid)


def _acquire_lock(lock: Path) -> bool:
    """Exclusive claim. Steal only a lock whose owner is already gone."""
    lock.parent.mkdir(parents=True, exist_ok=True)
    me = str(os.getpid()).encode()
    for _ in range(3):
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if not _lock_abandoned(lock):
                return False
            stolen = lock.with_name(f"{lock.name}.steal-{os.getpid()}")
            try:
                os.replace(lock, stolen)
            except OSError:
                return False
            try:
                stolen.unlink()
            except OSError:
                pass
            continue
        try:
            os.write(fd, me)
        finally:
            os.close(fd)
        try:
            current = lock.read_bytes()
        except OSError:
            return False
        if current != me:
            return False
        return True
    return False


def _release_lock(lock: Path) -> None:
    try:
        if lock.is_file() and lock.read_bytes() != str(os.getpid()).encode():
            return
        lock.unlink()
    except OSError:
        return


def _stop_met(state: dict) -> bool:
    committed_n = _whole_count(state.get("committed", 0))
    ceiling_n = _whole_count(state.get("ceiling"))
    empties_n = _whole_count(state.get("consecutive_empty", 0))
    ceiling_met = ceiling_n is not None and committed_n is not None and committed_n >= ceiling_n
    empties_met = empties_n is not None and empties_n >= 2
    return ceiling_met or empties_met or _is_active(state.get("stop"))


def _resume_abandoned(state: dict) -> bool:
    pid = state.get("resume_pid")
    if isinstance(pid, bool) or not isinstance(pid, int):
        return False
    deadline = state.get("resume_deadline")
    if isinstance(deadline, (int, float)) and not isinstance(deadline, bool) and time.time() > float(deadline):
        return True
    return not _pid_alive(pid)


def _fill_pause(root: Path, state: dict) -> None:
    if "pause_seconds" not in state or _coerce_pause(state.get("pause_seconds")) is None:
        script_pause = pause_from_script(root)
        if script_pause is not None:
            state["pause_seconds"] = script_pause


def apply_continue(root: Path, *, sleep) -> dict:
    """Consume one continue token, wait its pause, and return the next-pass payload.

    The token is marked in-progress before the wait so a second hook does not
    start another pass. If this process dies during the wait, the next hook
    sees the dead owner and continues. After the wait, a stop or a newer token
    written in the meantime is left in place and does not get a followup.
    """
    path = Path(root) / CONTINUE_REL
    lock = path.with_name(path.name + ".lock")
    if not path.is_file() or not _acquire_lock(lock):
        return {}
    pause = 0
    payload: dict = {}
    try:
        state = _read_state(path)
        if not isinstance(state, dict):
            return {}
        abandoned = _resume_abandoned(state)
        if not _is_active(state.get("active")) and not abandoned:
            return {}
        _fill_pause(root, state)
        if _stop_met(state):
            state["active"] = False
            state.pop("resume_pid", None)
            state.pop("resume_deadline", None)
            _write_state(path, state)
            return {}
        planned = dict(state)
        planned["active"] = True
        pause, payload = plan_continue(planned)
        if not payload:
            state["active"] = False
            state.pop("resume_pid", None)
            state.pop("resume_deadline", None)
            _write_state(path, state)
            return {}
        if abandoned:
            pause = 0
        state["active"] = False
        state["resume_pid"] = os.getpid()
        state["resume_deadline"] = time.time() + pause + _RESUME_GRACE_SECONDS
        _write_state(path, state)
    finally:
        _release_lock(lock)
    if not payload:
        return {}
    if pause > 0:
        sleep(pause)
    if not _acquire_lock(lock):
        return {}
    try:
        state = _read_state(path)
        if not isinstance(state, dict) or state.get("resume_pid") != os.getpid():
            return {}
        if _stop_met(state):
            state["active"] = False
            state.pop("resume_pid", None)
            state.pop("resume_deadline", None)
            _write_state(path, state)
            return {}
        state.pop("resume_pid", None)
        state.pop("resume_deadline", None)
        state["active"] = False
        _write_state(path, state)
    finally:
        _release_lock(lock)
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

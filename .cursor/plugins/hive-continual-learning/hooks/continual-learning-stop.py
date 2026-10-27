"""Cursor stop hook for Hive continual-learning (Python runtime).

Cursor 3.x plugin hooks run with cwd = workspace root. Upstream used Bun;
this repo targets Windows + Python 3.11 without requiring Bun.

Stdout must always be valid JSON (`{}`). A due memory check opens a desktop
popup and does not submit a chat prompt.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

STATE_PATH = Path(".cursor/hooks/state/continual-learning.json")
DEFAULT_MIN_TURNS = 10
DEFAULT_MIN_MINUTES = 120
TRIAL_DEFAULT_MIN_TURNS = 3
TRIAL_DEFAULT_MIN_MINUTES = 15
TRIAL_DEFAULT_DURATION_MINUTES = 24 * 60

NOTICE_TITLE = "Hive Planner"
NOTICE_BODY = (
    "Automatic memory check. You did not type this. "
    "Hive left your chat on the task you were doing."
)


def _parse_positive_int(value: str | None, fallback: int) -> int:
    if not value:
        return fallback
    try:
        parsed = int(value, 10)
    except ValueError:
        return fallback
    return parsed if parsed > 0 else fallback


def _parse_boolean(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_env(primary: str, legacy: str) -> str | None:
    return os.environ.get(primary) or os.environ.get(legacy)


def _load_state() -> dict:
    fallback = {
        "version": 1,
        "lastRunAtMs": 0,
        "turnsSinceLastRun": 0,
        "lastTranscriptMtimeMs": None,
        "lastProcessedGenerationId": None,
        "trialStartedAtMs": None,
    }
    if not STATE_PATH.exists():
        return fallback
    try:
        parsed = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict) or parsed.get("version") != 1:
            return fallback
        return {
            "version": 1,
            "lastRunAtMs": parsed["lastRunAtMs"]
            if isinstance(parsed.get("lastRunAtMs"), (int, float))
            else 0,
            "turnsSinceLastRun": parsed["turnsSinceLastRun"]
            if isinstance(parsed.get("turnsSinceLastRun"), (int, float))
            and parsed["turnsSinceLastRun"] >= 0
            else 0,
            "lastTranscriptMtimeMs": parsed["lastTranscriptMtimeMs"]
            if isinstance(parsed.get("lastTranscriptMtimeMs"), (int, float))
            else None,
            "lastProcessedGenerationId": parsed["lastProcessedGenerationId"]
            if isinstance(parsed.get("lastProcessedGenerationId"), str)
            else None,
            "trialStartedAtMs": parsed["trialStartedAtMs"]
            if isinstance(parsed.get("trialStartedAtMs"), (int, float))
            else None,
        }
    except (OSError, json.JSONDecodeError, TypeError):
        return fallback


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _transcript_mtime_ms(transcript_path: str | None) -> float | None:
    if not transcript_path:
        return None
    try:
        return Path(transcript_path).stat().st_mtime * 1000.0
    except OSError:
        return None


def _should_count_turn(payload: dict) -> bool:
    return payload.get("status") == "completed" and payload.get("loop_count") == 0


def _notice_stayed_open(proc: subprocess.Popen[bytes]) -> bool:
    """True only while the popup process is still running."""
    try:
        code = proc.wait(timeout=0.6)
    except subprocess.TimeoutExpired:
        return True
    print(f"[continual-learning-stop] notify exited {code}", file=sys.stderr)
    return False


def _show_user_notice() -> bool:
    """Popup over the desktop. False when the window never stays up."""
    script = Path(__file__).with_name("hive_notify.py")
    if not script.is_file():
        print(f"[continual-learning-stop] notify script missing: {script}", file=sys.stderr)
        return False
    cmd = [
        sys.executable,
        str(script),
        "--title",
        NOTICE_TITLE,
        "--body",
        NOTICE_BODY,
    ]
    env = os.environ.copy()
    dry = env.get("HIVE_NOTIFY_DRY_RUN") == "1"
    try:
        if dry:
            completed = subprocess.run(cmd, check=False, env=env, capture_output=True, text=True)
            return completed.returncode == 0
        kwargs: dict = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
            "env": env,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.CREATE_NO_WINDOW
            )
        else:
            kwargs["start_new_session"] = True
        proc = subprocess.Popen(cmd, **kwargs)
    except OSError as exc:
        print(f"[continual-learning-stop] notify failed: {exc}", file=sys.stderr)
        return False
    return _notice_stayed_open(proc)


def main() -> int:
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else "{}"
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}

        state = _load_state()
        generation_id = payload.get("generation_id")
        if generation_id and generation_id == state.get("lastProcessedGenerationId"):
            print(json.dumps({}))
            return 0
        state["lastProcessedGenerationId"] = (
            generation_id if isinstance(generation_id, str) else None
        )

        counted_turn = _should_count_turn(payload)
        turns_since_last_run = int(state["turnsSinceLastRun"]) + (1 if counted_turn else 0)
        now = int(__import__("time").time() * 1000)

        trial_enabled = _parse_boolean(
            _read_env("CONTINUAL_LEARNING_TRIAL_MODE", "CONTINUOUS_LEARNING_TRIAL_MODE")
        )
        if trial_enabled and counted_turn and state.get("trialStartedAtMs") is None:
            state["trialStartedAtMs"] = now

        trial_duration_minutes = _parse_positive_int(
            _read_env(
                "CONTINUAL_LEARNING_TRIAL_DURATION_MINUTES",
                "CONTINUOUS_LEARNING_TRIAL_DURATION_MINUTES",
            ),
            TRIAL_DEFAULT_DURATION_MINUTES,
        )
        trial_min_turns = _parse_positive_int(
            _read_env(
                "CONTINUAL_LEARNING_TRIAL_MIN_TURNS",
                "CONTINUOUS_LEARNING_TRIAL_MIN_TURNS",
            ),
            TRIAL_DEFAULT_MIN_TURNS,
        )
        trial_min_minutes = _parse_positive_int(
            _read_env(
                "CONTINUAL_LEARNING_TRIAL_MIN_MINUTES",
                "CONTINUOUS_LEARNING_TRIAL_MIN_MINUTES",
            ),
            TRIAL_DEFAULT_MIN_MINUTES,
        )
        in_trial_window = (
            trial_enabled
            and state.get("trialStartedAtMs") is not None
            and now - int(state["trialStartedAtMs"]) < trial_duration_minutes * 60_000
        )

        min_turns = _parse_positive_int(
            _read_env("CONTINUAL_LEARNING_MIN_TURNS", "CONTINUOUS_LEARNING_MIN_TURNS"),
            DEFAULT_MIN_TURNS,
        )
        min_minutes = _parse_positive_int(
            _read_env("CONTINUAL_LEARNING_MIN_MINUTES", "CONTINUOUS_LEARNING_MIN_MINUTES"),
            DEFAULT_MIN_MINUTES,
        )
        effective_min_turns = trial_min_turns if in_trial_window else min_turns
        effective_min_minutes = trial_min_minutes if in_trial_window else min_minutes

        last_run = int(state.get("lastRunAtMs") or 0)
        minutes_since_last_run = (
            (now - last_run) // 60000 if last_run > 0 else float("inf")
        )
        transcript_mtime_ms = _transcript_mtime_ms(payload.get("transcript_path"))
        last_mtime = state.get("lastTranscriptMtimeMs")
        has_transcript_advanced = transcript_mtime_ms is not None and (
            last_mtime is None or transcript_mtime_ms > last_mtime
        )

        should_trigger = (
            counted_turn
            and turns_since_last_run >= effective_min_turns
            and minutes_since_last_run >= effective_min_minutes
            and has_transcript_advanced
        )

        if should_trigger:
            if _show_user_notice():
                state["lastRunAtMs"] = now
                state["turnsSinceLastRun"] = 0
                state["lastTranscriptMtimeMs"] = transcript_mtime_ms
            else:
                state["turnsSinceLastRun"] = turns_since_last_run
            _save_state(state)
            print(json.dumps({}))
            return 0

        state["turnsSinceLastRun"] = turns_since_last_run
        _save_state(state)
        print(json.dumps({}))
        return 0
    except Exception as exc:  # noqa: BLE001 — fail-open for Cursor hooks
        print(f"[continual-learning-stop] failed: {exc}", file=sys.stderr)
        print(json.dumps({}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

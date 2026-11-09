"""Shared helpers for Voice_Bot runner tests (T004-T011).

Every runner in these tests talks to a real child process (tests/fixtures/acp_turn_server.py)
over stdio JSON-RPC. Only the executable is swapped; framing, routing, the runner, and the
state machine are production code.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Callable

from hive_planner.config import RepoPaths
from hive_planner.voice_acp import AcpClient
from hive_planner.voice_task import VoiceTaskRunner

TURN_SERVER = Path(__file__).parent / "fixtures" / "acp_turn_server.py"


def make_repo(tmp_path: Path) -> RepoPaths:
    (tmp_path / "AGENTS.md").write_text(
        "## Active feature\n\n- **Voice_Bot** — listed lane.\n", encoding="utf-8"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    return RepoPaths(root=tmp_path)


def make_runner(paths: RepoPaths, *, timeout: float = 20.0, **kwargs: Any) -> VoiceTaskRunner:
    def factory(handler: Callable[[str, Any], Any]) -> AcpClient:
        return AcpClient(
            [sys.executable, str(TURN_SERVER)],
            cwd=str(paths.root),
            server_request_handler=handler,
        )

    return VoiceTaskRunner(
        paths,
        "Voice_Bot",
        client_factory=factory,
        request_timeout=timeout,
        **kwargs,
    )


def wait_for(predicate: Callable[[], bool], timeout: float = 15.0, step: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return False


def _state_of(runner: VoiceTaskRunner, task_id: str) -> str:
    # Read under the runner lock: a state is only visible once its finish step (evidence,
    # speech, save) has completed, because the worker holds the lock for that whole step.
    with runner._lock:
        return runner.state.coding_tasks[task_id].state


def wait_task_terminal(runner: VoiceTaskRunner, task_id: str, timeout: float = 15.0) -> str:
    """Wait until the task reaches a terminal state, then return that state."""
    terminal = ("completed", "failed", "cancelled")
    if not wait_for(lambda: _state_of(runner, task_id) in terminal, timeout=timeout):
        raise AssertionError(f"task {task_id} stuck in {_state_of(runner, task_id)}")
    return _state_of(runner, task_id)


def wait_task_state(runner: VoiceTaskRunner, task_id: str, state: str, timeout: float = 15.0) -> None:
    if not wait_for(lambda: _state_of(runner, task_id) == state, timeout=timeout):
        raise AssertionError(f"task {task_id} never reached {state}; now {_state_of(runner, task_id)}")

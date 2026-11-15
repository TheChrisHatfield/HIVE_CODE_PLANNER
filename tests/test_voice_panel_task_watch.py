"""T042 slice 5e: the launcher greeting follows the last typed task (controller + panel)."""

from __future__ import annotations

import threading
import time
import tkinter as tk
from pathlib import Path

import pytest

from hive_planner.launcher import voice_panel, voice_panel_controller as vpc
from hive_planner.launcher.voice_panel import GREETING, LISTENING_GREETING, VoicePanel
from hive_planner.launcher.voice_panel_controller import VoicePanelController


class _Post:
    """Fake POST: /v1/submit returns a task with its context snapshot id."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, route: str, body: dict) -> tuple[int, dict]:
        self.calls.append((route, body))
        return 200, self.payload


def _live(ctrl: VoicePanelController, monkeypatch) -> None:
    monkeypatch.setattr(ctrl, "bridge_running", lambda: True)


def _states(monkeypatch, ctrl: VoicePanelController, states: list[dict]) -> list[dict]:
    """Fake GET /v1/task. Returns the states in order, then repeats the last one. Records query args."""
    seen: list[dict] = []
    queue = list(states)

    def fake_get(route: str, extra=None):
        seen.append({"route": route, **(extra or {})})
        view = queue.pop(0) if len(queue) > 1 else queue[0]
        return 200, view

    monkeypatch.setattr(ctrl, "_get_from_bridge", fake_get)
    return seen


def _wait_for(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not reached in time")


@pytest.fixture()
def fast_poll(monkeypatch):
    monkeypatch.setattr(vpc, "TASK_POLL_S", 0.01)


def test_typed_submit_shows_working_label_then_clears_on_completion(tmp_path: Path, monkeypatch, fast_poll) -> None:
    post = _Post({"status": "running", "task_id": "t-1", "context_snapshot_id": "ctx-1", "state": "running"})
    ctrl = VoicePanelController(lambda: tmp_path, post=post)
    _live(ctrl, monkeypatch)
    seen = _states(monkeypatch, ctrl, [{"state": "running"}, {"state": "completed"}])

    assert ctrl.submit_typed("explain the parser").ok is True

    _wait_for(lambda: ctrl.task_text() is None)
    assert seen[0] == {"route": "/v1/task", "task_id": "t-1", "context_snapshot_id": "ctx-1"}


def test_submit_sets_working_label_before_first_poll_returns(tmp_path: Path, monkeypatch, fast_poll) -> None:
    gate = threading.Event()
    post = _Post({"status": "running", "task_id": "t-9", "context_snapshot_id": "ctx-9"})
    ctrl = VoicePanelController(lambda: tmp_path, post=post)
    _live(ctrl, monkeypatch)

    def blocked_get(route: str, extra=None):
        gate.wait(3.0)
        return 200, {"state": "completed"}

    monkeypatch.setattr(ctrl, "_get_from_bridge", blocked_get)
    ctrl.submit_typed("slow task")
    assert ctrl.task_text() == vpc.TASK_LABEL_WORKING  # poll is still blocked, so label is the submit label
    gate.set()
    _wait_for(lambda: ctrl.task_text() is None)


def test_awaiting_approval_shows_approval_label(tmp_path: Path, monkeypatch, fast_poll) -> None:
    post = _Post({"status": "running", "task_id": "t-2", "context_snapshot_id": "ctx-2"})
    ctrl = VoicePanelController(lambda: tmp_path, post=post)
    _live(ctrl, monkeypatch)
    _states(monkeypatch, ctrl, [{"state": "awaiting_approval"}])

    ctrl.submit_typed("edit the file")
    _wait_for(lambda: ctrl.task_text() == vpc.TASK_LABEL_APPROVAL)
    ctrl._stop_task_watch()


@pytest.mark.parametrize("terminal", ["completed", "failed", "cancelled"])
def test_terminal_state_stops_watch(tmp_path: Path, monkeypatch, fast_poll, terminal: str) -> None:
    post = _Post({"status": "running", "task_id": "t-3", "context_snapshot_id": "ctx-3"})
    ctrl = VoicePanelController(lambda: tmp_path, post=post)
    _live(ctrl, monkeypatch)
    seen = _states(monkeypatch, ctrl, [{"state": "running"}, {"state": terminal}])

    ctrl.submit_typed("do it")
    _wait_for(lambda: ctrl.task_text() is None)
    polls = len(seen)
    time.sleep(0.05)
    assert len(seen) == polls  # no more polling after a terminal state


def test_bridge_error_clears_label(tmp_path: Path, monkeypatch, fast_poll) -> None:
    post = _Post({"status": "running", "task_id": "t-4", "context_snapshot_id": "ctx-4"})
    ctrl = VoicePanelController(lambda: tmp_path, post=post)
    _live(ctrl, monkeypatch)
    monkeypatch.setattr(ctrl, "_get_from_bridge", lambda route, extra=None: (0, {"error": "bridge_unreachable"}))

    ctrl.submit_typed("do it")
    _wait_for(lambda: ctrl.task_text() is None)


def test_submit_without_context_snapshot_starts_no_watch(tmp_path: Path, monkeypatch) -> None:
    post = _Post({"status": "running", "task_id": "t-5"})
    ctrl = VoicePanelController(lambda: tmp_path, post=post)
    _live(ctrl, monkeypatch)
    seen = _states(monkeypatch, ctrl, [{"state": "running"}])

    ctrl.submit_typed("do it")
    assert ctrl.task_text() is None
    assert seen == []


def test_queued_submit_starts_no_watch(tmp_path: Path, monkeypatch) -> None:
    post = _Post({"status": "queued", "queue_id": "q-1", "state": "queued", "spoken": "Queued."})
    ctrl = VoicePanelController(lambda: tmp_path, post=post)
    _live(ctrl, monkeypatch)
    seen = _states(monkeypatch, ctrl, [{"state": "running"}])

    ctrl.submit_typed("do it")
    assert ctrl.task_text() is None
    assert seen == []


def test_end_call_clears_label_and_stops_polling(tmp_path: Path, monkeypatch, fast_poll) -> None:
    post = _Post({"status": "running", "task_id": "t-6", "context_snapshot_id": "ctx-6"})
    ctrl = VoicePanelController(lambda: tmp_path, post=post)
    _live(ctrl, monkeypatch)
    seen = _states(monkeypatch, ctrl, [{"state": "running"}])
    monkeypatch.setattr(ctrl, "_post_fn", post)

    ctrl.submit_typed("do it")
    assert ctrl.task_text() == vpc.TASK_LABEL_WORKING
    ctrl.on_end()
    assert ctrl.task_text() is None
    polls = len(seen)
    time.sleep(0.05)
    assert len(seen) <= polls + 1  # at most one in-flight poll after hang-up


def test_new_submit_replaces_previous_watch(tmp_path: Path, monkeypatch, fast_poll) -> None:
    post = _Post({"status": "running", "task_id": "t-7", "context_snapshot_id": "ctx-7"})
    ctrl = VoicePanelController(lambda: tmp_path, post=post)
    _live(ctrl, monkeypatch)
    _states(monkeypatch, ctrl, [{"state": "running"}])

    ctrl.submit_typed("first")
    first_stop = ctrl._task_stop
    post.payload = {"status": "running", "task_id": "t-8", "context_snapshot_id": "ctx-8"}
    ctrl.submit_typed("second")
    assert first_stop is not None and first_stop.is_set()
    assert ctrl._task_ref == ("t-8", "ctx-8")
    ctrl._stop_task_watch()


# --- panel: the greeting slot follows the label -----------------------------

@pytest.fixture()
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available for Tk")
    r.withdraw()
    yield r
    r.destroy()


def _labels(panel: VoicePanel) -> list[str]:
    out: list[str] = []

    def walk(w: tk.Misc) -> None:
        for child in w.winfo_children():
            if isinstance(child, tk.Label):
                out.append(str(child.cget("text")))
            walk(child)

    walk(panel)
    return out


def test_panel_greeting_follows_task_label_then_restores(root) -> None:
    state: dict[str, str | None] = {"text": None}
    panel = VoicePanel(root, task_text=lambda: state["text"])
    panel._animate()
    assert GREETING in _labels(panel)

    state["text"] = vpc.TASK_LABEL_WORKING
    panel._animate()
    assert vpc.TASK_LABEL_WORKING in _labels(panel)
    assert GREETING not in _labels(panel)

    state["text"] = None
    panel._animate()
    assert GREETING in _labels(panel)
    panel.destroy()
    root.update()


def test_listening_wins_over_task_label(root) -> None:
    panel = VoicePanel(root, task_text=lambda: vpc.TASK_LABEL_WORKING)
    panel._toggle_listening()
    panel._animate()
    assert LISTENING_GREETING in _labels(panel)
    assert vpc.TASK_LABEL_WORKING not in _labels(panel)
    panel.destroy()
    root.update()


def test_refusal_message_is_not_overwritten_while_label_is_unchanged(root) -> None:
    panel = VoicePanel(root, task_text=lambda: vpc.TASK_LABEL_WORKING)
    panel._animate()
    panel.show_message("Mic off: test refusal")
    panel._animate()
    assert "Mic off: test refusal" in _labels(panel)
    panel.destroy()
    root.update()


def test_app_passes_task_label_getter_to_panel() -> None:
    import inspect

    from hive_planner.launcher import app as launcher_app

    source = inspect.getsource(launcher_app.HivePlannerApp)
    assert "task_text=self.voice_controller.task_text" in source
    assert voice_panel.VoicePanel is launcher_app.VoicePanel

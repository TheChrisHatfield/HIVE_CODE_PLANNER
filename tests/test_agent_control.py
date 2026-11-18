from __future__ import annotations

import os
from pathlib import Path

from hive_planner.launcher.agent_control import (
    ACTIONS,
    AgentControlServer,
    call_live_launcher,
    dispatch_app_action,
    temp_control_path,
)


class _Panel:
    def __init__(self) -> None:
        self.listening = False
        self.calls: list[bool] = []
        self.ended = 0

    def apply_mic(self, start: bool) -> str | None:
        self.calls.append(bool(start))
        self.listening = bool(start)
        return None

    def _end_call(self) -> None:
        self.ended += 1
        self.listening = False


class _Ctrl:
    def mic_connecting(self) -> bool:
        return False

    def notice_feed(self) -> tuple[int, str | None, bool]:
        return (0, None, False)

    def submit_typed(self, text: str):
        return type("R", (), {"ok": True, "message": text})()


class _App:
    def __init__(self) -> None:
        self.root = None
        self.voice_panel = _Panel()
        self.voice_controller = _Ctrl()
        self.config = type("Cfg", (), {"active_project": ""})()
        self.home_runs: list[str] = []

    def _home_action_command(self, action_id: str):
        if action_id != "ci_check":
            return None

        def _run() -> None:
            self.home_runs.append(action_id)

        return _run


def test_talk_uses_panel_apply_mic() -> None:
    app = _App()
    payload = dispatch_app_action(app, "voice.talk", {})
    assert payload["ok"] is True
    assert payload["speak_now"] is True
    assert "Speak now" in str(payload["cue"])
    assert app.voice_panel.calls == [True]


def test_unknown_action_is_refused() -> None:
    payload = dispatch_app_action(_App(), "shell.run", {})
    assert payload["ok"] is False
    assert payload["error"] == "agent_action_unknown"


def test_home_ci_check_runs_handler() -> None:
    app = _App()
    payload = dispatch_app_action(app, "launcher.home", {"action_id": "ci_check"})
    assert payload["ok"] is True
    assert app.home_runs == ["ci_check"]


def test_http_plane_round_trip(tmp_path: Path, monkeypatch) -> None:
    sidecar = tmp_path / "agent-control.json"
    monkeypatch.setenv("HIVE_AGENT_CONTROL_FILE", str(sidecar))
    app = _App()
    server = AgentControlServer(tmp_path, lambda action, args: dispatch_app_action(app, action, args))
    server.start()
    try:
        live = call_live_launcher(tmp_path, live=True)
        assert live["ok"] is True
        talked = call_live_launcher(tmp_path, action="voice.talk", arguments={})
        assert talked["ok"] is True
        assert talked["speak_now"] is True
        catalog = call_live_launcher(tmp_path, catalog=True)
        ids = {row["id"] for row in catalog["actions"]}
        assert ids == set(ACTIONS)
    finally:
        server.stop()


def test_two_hive_roots_use_different_temp_sidecars(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("HIVE_AGENT_CONTROL_FILE", raising=False)
    monkeypatch.setattr(
        "hive_planner.launcher.agent_control.tempfile.gettempdir",
        lambda: str(tmp_path / "tmp"),
    )
    left = tmp_path / "checkout"
    right = tmp_path / "portable"
    left.mkdir()
    right.mkdir()
    assert temp_control_path(left) != temp_control_path(right)
    from hive_planner.launcher.agent_control import write_control_docs

    write_control_docs(left, {"pid": os.getpid(), "port": 1, "token": "a", "hive_root": str(left.resolve())})
    write_control_docs(right, {"pid": os.getpid(), "port": 2, "token": "b", "hive_root": str(right.resolve())})
    assert temp_control_path(left).read_text(encoding="utf-8") != temp_control_path(right).read_text(encoding="utf-8")


def test_discover_accepts_portable_gui_under_checkout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("HIVE_AGENT_CONTROL_FILE", raising=False)
    monkeypatch.setattr("hive_planner.launcher.agent_control.pid_alive", lambda _pid: True)
    monkeypatch.setattr(
        "hive_planner.launcher.agent_control.tempfile.gettempdir",
        lambda: str(tmp_path / "tmp"),
    )
    checkout = tmp_path / "repo"
    portable = checkout / "dist" / "HivePlannerPortable"
    portable.mkdir(parents=True)
    from hive_planner.launcher.agent_control import discover_control, write_control_docs

    write_control_docs(
        portable,
        {
            "pid": os.getpid(),
            "port": 9,
            "token": "t",
            "hive_root": str(portable.resolve()),
        },
    )
    doc = discover_control(checkout)
    assert doc is not None
    assert doc.get("ambiguous") is not True
    assert Path(doc["hive_root"]).resolve() == portable.resolve()


def test_call_without_gui_is_launcher_not_running(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HIVE_AGENT_CONTROL_FILE", str(tmp_path / "missing.json"))
    payload = call_live_launcher(tmp_path, live=True)
    assert payload["ok"] is False
    assert payload["error"] == "launcher_not_running"

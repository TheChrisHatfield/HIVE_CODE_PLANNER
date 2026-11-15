"""Tests for the launcher Voice panel controller (T042 slice 5a). No mic, no real socket."""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

MOSHI_URL_DEFAULT = "ws://127.0.0.1:8998/api/chat"

import pytest

from hive_planner.launcher import voice_panel_controller as vpc
from hive_planner.launcher.voice_panel_controller import VoicePanelController
from hive_planner.voice_stt import STT_PIN_PROVIDER


def _write_config(root: Path, **fields) -> None:
    path = root / ".hive" / "voice-bot"
    path.mkdir(parents=True, exist_ok=True)
    (path / "config.json").write_text(json.dumps(fields), encoding="utf-8")


class _Recorder:
    def __init__(self, status: int = 200, payload: dict | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.status = status
        self.payload = payload or {}

    def __call__(self, route: str, body: dict) -> tuple[int, dict]:
        self.calls.append((route, body))
        return self.status, self.payload


def _controller(root: Path | None, post=None) -> VoicePanelController:
    return VoicePanelController(lambda: root, post=post)


def test_mic_start_refused_without_project() -> None:
    ctrl = _controller(None)
    message = ctrl.on_mic(True)
    assert message and "project" in message.lower()


def test_mic_start_refused_when_stt_not_configured(tmp_path: Path) -> None:
    # voice_layer typed: this test covers the Whisper/WAV route. The Moshi route is tested below.
    _write_config(tmp_path, voice_layer="typed")
    ctrl = _controller(tmp_path)
    message = ctrl.on_mic(True)
    assert message is not None
    assert vpc.CODE_STT_NOT_CONFIGURED in message
    assert ctrl.mic_active is False


def test_mic_start_refused_until_capture_wired(tmp_path: Path) -> None:
    _write_config(tmp_path, stt_provider=STT_PIN_PROVIDER, voice_layer="typed")
    ctrl = _controller(tmp_path)
    message = ctrl.on_mic(True)
    assert message is not None
    assert vpc.CODE_MIC_CAPTURE_NOT_WIRED in message
    assert ctrl.mic_active is False


def test_mic_stop_always_accepted(tmp_path: Path) -> None:
    ctrl = _controller(tmp_path)
    assert ctrl.on_mic(False) is None


def test_end_call_without_bridge_does_not_post(tmp_path: Path) -> None:
    rec = _Recorder()
    ctrl = _controller(tmp_path, post=rec)
    result = ctrl.on_end()
    assert result.ok is False
    assert result.code == vpc.CODE_BRIDGE_NOT_RUNNING
    assert rec.calls == []


def test_end_call_with_bridge_posts_call_end(tmp_path: Path, monkeypatch) -> None:
    rec = _Recorder(status=200, payload={"session": "ended"})
    ctrl = _controller(tmp_path, post=rec)
    monkeypatch.setattr(ctrl, "bridge_running", lambda: True)
    result = ctrl.on_end()
    assert result.ok is True
    assert result.code == vpc.CODE_CALL_ENDED
    assert [route for route, _ in rec.calls] == ["/v1/call/end"]
    assert rec.calls[0][1]["workspace"] == str(tmp_path.resolve())


def test_end_call_interrupts_playback_first_when_audio_enabled(tmp_path: Path, monkeypatch) -> None:
    _write_config(tmp_path, audio_enabled=True)
    rec = _Recorder(status=200)
    ctrl = _controller(tmp_path, post=rec)
    monkeypatch.setattr(ctrl, "bridge_running", lambda: True)
    ctrl.on_mic(False)
    result = ctrl.on_end()
    assert result.ok is True
    assert [route for route, _ in rec.calls] == ["/v1/playback/interrupt", "/v1/call/end"]


def test_end_call_skips_playback_interrupt_when_audio_off(tmp_path: Path, monkeypatch) -> None:
    rec = _Recorder(status=200)
    ctrl = _controller(tmp_path, post=rec)
    monkeypatch.setattr(ctrl, "bridge_running", lambda: True)
    ctrl.on_end()
    assert [route for route, _ in rec.calls] == ["/v1/call/end"]


def test_end_call_surfaces_bridge_refusal_code(tmp_path: Path, monkeypatch) -> None:
    rec = _Recorder(status=409, payload={"error": "no_active_task", "message": "nothing to end"})
    ctrl = _controller(tmp_path, post=rec)
    monkeypatch.setattr(ctrl, "bridge_running", lambda: True)
    result = ctrl.on_end()
    assert result.ok is False
    assert result.code == "no_active_task"
    assert result.message == "nothing to end"


def test_post_without_endpoint_file_reports_unreachable(tmp_path: Path, monkeypatch) -> None:
    ctrl = _controller(tmp_path)
    monkeypatch.setattr(ctrl, "bridge_running", lambda: True)
    result = ctrl.on_end()
    assert result.ok is False
    assert result.code == vpc.CODE_BRIDGE_UNREACHABLE


def test_status_reads_speech_config(tmp_path: Path) -> None:
    _write_config(tmp_path, audio_enabled=True, stt_provider=STT_PIN_PROVIDER)
    status = _controller(tmp_path).status()
    assert status["stt_provider"] == STT_PIN_PROVIDER
    assert status["audio_enabled"] is True
    assert status["bridge_running"] is False


def test_status_defaults_to_s0_when_config_missing(tmp_path: Path) -> None:
    status = _controller(tmp_path).status()
    assert status["stt_provider"] is None
    assert status["audio_enabled"] is False


def test_status_reports_broken_config_instead_of_silent_defaults(tmp_path: Path) -> None:
    _write_config(tmp_path, audio_enabled=True, not_a_real_key=1)
    status = _controller(tmp_path).status()
    assert status["config_error"] is not None
    assert "not_a_real_key" in status["config_error"]
    assert status["audio_enabled"] is False
    assert "Config error" in _controller(tmp_path).menu_text()


def test_status_has_no_config_error_when_valid(tmp_path: Path) -> None:
    _write_config(tmp_path, audio_enabled=True)
    assert _controller(tmp_path).status()["config_error"] is None


def test_menu_text_names_stt_and_bridge(tmp_path: Path) -> None:
    text = _controller(tmp_path).menu_text()
    assert "stt_provider" in text
    assert "not running" in text


def test_back_target_is_main_shell() -> None:
    assert _controller(None).back_target() == "main_shell"


@pytest.mark.parametrize("start", [True, False])
def test_on_mic_without_project_never_raises(start: bool) -> None:
    _controller(None).on_mic(start)


# --- T042 slice 5b: side button typed submit (injected post, no socket) -------


def _live(ctrl: VoicePanelController, monkeypatch, live: bool = True) -> None:
    monkeypatch.setattr(ctrl, "bridge_running", lambda: live)


def test_submit_typed_refused_without_project() -> None:
    rec = _Recorder()
    result = VoicePanelController(lambda: None, post=rec).submit_typed("fix the test")
    assert result.ok is False
    assert result.code == vpc.CODE_NO_PROJECT
    assert rec.calls == []


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_submit_typed_refuses_empty_instruction(tmp_path: Path, monkeypatch, text: str) -> None:
    rec = _Recorder()
    ctrl = _controller(tmp_path, post=rec)
    _live(ctrl, monkeypatch)
    result = ctrl.submit_typed(text)
    assert result.ok is False
    assert result.code == vpc.CODE_EMPTY_INSTRUCTION
    assert rec.calls == []


def test_submit_typed_refused_when_bridge_not_running(tmp_path: Path, monkeypatch) -> None:
    rec = _Recorder()
    ctrl = _controller(tmp_path, post=rec)
    _live(ctrl, monkeypatch, live=False)
    result = ctrl.submit_typed("fix the test")
    assert result.ok is False
    assert result.code == vpc.CODE_BRIDGE_NOT_RUNNING
    assert "Nothing was sent" in result.message
    assert rec.calls == []
    assert ctrl.last_instruction is None


def test_submit_typed_posts_submit_body_and_returns_task(tmp_path: Path, monkeypatch) -> None:
    rec = _Recorder(status=200, payload={"status": "running", "task_id": "t-1", "state": "running"})
    ctrl = _controller(tmp_path, post=rec)
    _live(ctrl, monkeypatch)
    result = ctrl.submit_typed("  explain the parser  ")
    assert result.ok is True
    assert result.code == vpc.CODE_SUBMITTED
    assert result.task_id == "t-1"
    assert "t-1" in result.message
    assert [route for route, _ in rec.calls] == ["/v1/submit"]
    body = rec.calls[0][1]
    assert body["workspace"] == str(tmp_path.resolve())
    assert body["instruction"] == "explain the parser"
    assert body["mode"] == "ask"
    assert str(uuid.UUID(body["client_request_id"])) == body["client_request_id"]
    assert ctrl.last_instruction == "explain the parser"


def test_submit_typed_uses_fresh_client_request_id_each_time(tmp_path: Path, monkeypatch) -> None:
    rec = _Recorder(status=200, payload={"status": "running", "task_id": "t"})
    ctrl = _controller(tmp_path, post=rec)
    _live(ctrl, monkeypatch)
    ctrl.submit_typed("one")
    ctrl.submit_typed("two")
    ids = [body["client_request_id"] for _, body in rec.calls]
    assert len(set(ids)) == 2


def test_submit_typed_queued_is_success_without_task_id(tmp_path: Path, monkeypatch) -> None:
    rec = _Recorder(status=200, payload={"status": "queued", "task_id": None, "spoken": "Queued behind the active task."})
    ctrl = _controller(tmp_path, post=rec)
    _live(ctrl, monkeypatch)
    result = ctrl.submit_typed("next thing")
    assert result.ok is True
    assert result.task_id is None
    assert result.message == "Queued behind the active task."


def test_submit_typed_surfaces_bridge_refusal_json(tmp_path: Path, monkeypatch) -> None:
    rec = _Recorder(status=400, payload={"error": "agent_mode_disabled", "message": "agent mode is disabled"})
    ctrl = _controller(tmp_path, post=rec)
    _live(ctrl, monkeypatch)
    result = ctrl.submit_typed("edit the file")
    assert result.ok is False
    assert result.code == "agent_mode_disabled"
    assert result.message == "agent mode is disabled"
    assert ctrl.last_instruction is None


def test_submit_typed_surfaces_queue_full_429(tmp_path: Path, monkeypatch) -> None:
    rec = _Recorder(status=429, payload={"error": "queue_full", "message": "queue is full"})
    ctrl = _controller(tmp_path, post=rec)
    _live(ctrl, monkeypatch)
    result = ctrl.submit_typed("one more")
    assert result.ok is False
    assert result.code == "queue_full"


def test_submit_typed_unreachable_is_not_success(tmp_path: Path, monkeypatch) -> None:
    rec = _Recorder(status=0, payload={"error": vpc.CODE_BRIDGE_UNREACHABLE, "message": "refused"})
    ctrl = _controller(tmp_path, post=rec)
    _live(ctrl, monkeypatch)
    result = ctrl.submit_typed("hello")
    assert result.ok is False
    assert result.code == vpc.CODE_BRIDGE_UNREACHABLE
    assert ctrl.last_instruction is None


def test_submit_typed_without_endpoint_file_reports_unreachable(tmp_path: Path, monkeypatch) -> None:
    ctrl = _controller(tmp_path)
    _live(ctrl, monkeypatch)
    result = ctrl.submit_typed("hello")
    assert result.ok is False
    assert result.code == vpc.CODE_BRIDGE_UNREACHABLE


# --- T042b: input_device controller hop (2026-11-14) ---------------------

from hive_planner.config import RepoPaths  # noqa: E402
from hive_planner.voice_bot import load_voice_bot_config  # noqa: E402


def test_set_input_device_saves_and_reloads(tmp_path: Path) -> None:
    ctrl = _controller(tmp_path)
    result = ctrl.set_input_device("Microphone (USB Audio)")
    assert result.ok is True
    assert result.input_device == "Microphone (USB Audio)"
    saved = load_voice_bot_config(RepoPaths(root=tmp_path.resolve()))
    assert saved.input_device == "Microphone (USB Audio)"


def test_set_input_device_blank_saves_null(tmp_path: Path) -> None:
    _write_config(tmp_path, input_device="Old Mic")
    ctrl = _controller(tmp_path)
    result = ctrl.set_input_device("   ")
    assert result.ok is True
    assert result.input_device is None
    saved = load_voice_bot_config(RepoPaths(root=tmp_path.resolve()))
    assert saved.input_device is None


def test_set_input_device_refused_without_project() -> None:
    ctrl = _controller(None)
    result = ctrl.set_input_device("Mic")
    assert result.ok is False
    assert result.code == vpc.CODE_NO_PROJECT


def test_set_input_device_refuses_broken_config_and_leaves_file(tmp_path: Path) -> None:
    path = tmp_path / ".hive" / "voice-bot"
    path.mkdir(parents=True)
    broken = "{not json"
    (path / "config.json").write_text(broken, encoding="utf-8")
    ctrl = _controller(tmp_path)
    result = ctrl.set_input_device("Mic")
    assert result.ok is False
    assert result.code == vpc.CODE_CONFIG_INVALID
    assert (path / "config.json").read_text(encoding="utf-8") == broken


# --- T042 slice 5c: menu bridge start/stop (injected spawn, no real process) ---


class _Closable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeProc:
    def __init__(self, exit_code: int | None = None) -> None:
        self.exit_code = exit_code
        self.stdin = _Closable()
        self.killed = False
        self.waited = False

    def poll(self) -> int | None:
        return self.exit_code

    def wait(self, timeout: float | None = None) -> int:
        self.waited = True
        return self.exit_code if self.exit_code is not None else 0

    def kill(self) -> None:
        self.killed = True


class _Spawner:
    def __init__(self, proc: _FakeProc | None = None) -> None:
        self.proc = proc or _FakeProc()
        self.calls: list[tuple[list[str], str | None]] = []

    def __call__(self, argv, cwd=None):
        self.calls.append((list(argv), cwd))
        return self.proc


def _ctrl_with_spawn(root: Path | None, spawn, post=None) -> VoicePanelController:
    return VoicePanelController(lambda: root, post=post, spawn=spawn)


def _live_sequence(ctrl: VoicePanelController, monkeypatch, values: list[bool]) -> None:
    """bridge_running() returns the values in order, then repeats the last one."""
    seq = list(values)

    def fake() -> bool:
        return seq.pop(0) if len(seq) > 1 else seq[0]

    monkeypatch.setattr(ctrl, "bridge_running", fake)


def test_start_bridge_refused_without_project() -> None:
    spawn = _Spawner()
    result = _ctrl_with_spawn(None, spawn).start_bridge()
    assert result.ok is False
    assert result.code == vpc.CODE_NO_PROJECT
    assert spawn.calls == []


def test_start_bridge_spawns_bridge_cli_for_project(tmp_path: Path, monkeypatch) -> None:
    spawn = _Spawner()
    ctrl = _ctrl_with_spawn(tmp_path, spawn)
    _live_sequence(ctrl, monkeypatch, [False, True])
    result = ctrl.start_bridge()
    assert result.ok is True
    assert result.code == vpc.CODE_BRIDGE_STARTED
    argv, cwd = spawn.calls[0]
    assert argv[1:3] == ["-m", "hive_planner"]
    assert argv[3:5] == ["--root", str(tmp_path.resolve())]
    assert argv[-2:] == ["voice-bot", "bridge"]
    assert cwd == str(tmp_path.resolve())


def test_start_bridge_refused_when_bridge_already_live(tmp_path: Path, monkeypatch) -> None:
    spawn = _Spawner()
    ctrl = _ctrl_with_spawn(tmp_path, spawn)
    _live_sequence(ctrl, monkeypatch, [False, True, True])
    assert ctrl.start_bridge().ok is True
    assert len(spawn.calls) == 1  # first start spawned
    second = ctrl.start_bridge()
    assert second.ok is False
    assert second.code == vpc.CODE_BRIDGE_ALREADY_RUNNING
    assert len(spawn.calls) == 1  # no second spawn


def test_start_bridge_reports_failure_when_process_exits_early(tmp_path: Path, monkeypatch) -> None:
    spawn = _Spawner(_FakeProc(exit_code=3))
    ctrl = _ctrl_with_spawn(tmp_path, spawn)
    monkeypatch.setattr(ctrl, "bridge_running", lambda: False)
    result = ctrl.start_bridge()
    assert result.ok is False
    assert result.code == vpc.CODE_BRIDGE_START_FAILED
    assert "3" in result.message


def test_stop_bridge_closes_owned_process_stdin_and_waits(tmp_path: Path, monkeypatch) -> None:
    proc = _FakeProc()
    spawn = _Spawner(proc)
    ctrl = _ctrl_with_spawn(tmp_path, spawn)
    _live_sequence(ctrl, monkeypatch, [False, True])
    assert ctrl.start_bridge().ok is True
    result = ctrl.stop_bridge()
    assert result.ok is True
    assert result.code == vpc.CODE_BRIDGE_STOPPED
    assert proc.stdin.closed is True
    assert proc.waited is True
    assert proc.killed is False


def test_stop_bridge_refused_when_nothing_running(tmp_path: Path, monkeypatch) -> None:
    ctrl = _ctrl_with_spawn(tmp_path, _Spawner())
    monkeypatch.setattr(ctrl, "bridge_running", lambda: False)
    result = ctrl.stop_bridge()
    assert result.ok is False
    assert result.code == vpc.CODE_BRIDGE_NOT_RUNNING


def test_stop_bridge_refused_when_bridge_not_started_by_launcher(tmp_path: Path, monkeypatch) -> None:
    ctrl = _ctrl_with_spawn(tmp_path, _Spawner())
    monkeypatch.setattr(ctrl, "bridge_running", lambda: True)
    result = ctrl.stop_bridge()
    assert result.ok is False
    assert result.code == vpc.CODE_BRIDGE_NOT_OWNED


def test_menu_text_no_longer_says_slice_5c_placeholder(tmp_path: Path) -> None:
    assert "slice 5c" not in _controller(tmp_path).menu_text()


# --- T042 slice 5d: mic record -> workspace WAV -> /v1/submit/spoken (injected recorder, no mic) ---


class _FakeRecorder:
    def __init__(self, audio: bytes = b"RIFF-fake-wav") -> None:
        self.audio = audio
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> bytes:
        self.stopped = True
        return self.audio


def test_mic_record_writes_workspace_wav_and_posts_spoken(tmp_path: Path, monkeypatch) -> None:
    _write_config(tmp_path, stt_provider=STT_PIN_PROVIDER, voice_layer="typed")
    rec = _Recorder(status=200, payload={"status": "running", "task_id": "t-9"})
    recorder = _FakeRecorder(audio=b"RIFF-fake-wav")
    ctrl = VoicePanelController(lambda: tmp_path, post=rec, recorder=recorder)
    _live(ctrl, monkeypatch)
    assert ctrl.on_mic(True) is None
    assert recorder.started is True
    assert ctrl.mic_active is True
    assert ctrl.on_mic(False) is None
    assert recorder.stopped is True
    assert ctrl.mic_active is False
    assert [route for route, _ in rec.calls] == ["/v1/submit/spoken"]
    body = rec.calls[0][1]
    assert body["workspace"] == str(tmp_path.resolve())
    assert body["mode"] == "ask"
    assert str(uuid.UUID(body["client_request_id"])) == body["client_request_id"]
    wav_rel = Path(body["wav_path"])
    assert not wav_rel.is_absolute()
    wav_file = (tmp_path / wav_rel).resolve()
    assert wav_file.is_relative_to(tmp_path.resolve())
    assert wav_file.read_bytes() == b"RIFF-fake-wav"

# --- T056 wiring (2026-11-14): mic button runs one duplex Moshi call (voice_layer moshi) ---


class _FakeIO:
    """Stands in for SoundDeviceIO: records open/close, feeds silence, drops playback."""

    def __init__(self) -> None:
        self.opened = False
        self.closed = False

    def open(self) -> None:
        self.opened = True

    def read(self, timeout: float):
        import time as _t

        _t.sleep(min(timeout, 0.02))
        return None

    def play(self, pcm) -> None:
        return None

    def close(self) -> None:
        self.closed = True


def _moshi_ctrl(root: Path, *, talk_fn, gate_code: str | None = None, recorder=None, post=None):
    return VoicePanelController(
        lambda: root,
        post=post or _Recorder(),
        recorder=recorder,
        talk_fn=talk_fn,
        io_factory=lambda device: _FakeIO(),
        listen_gate=lambda cfg: gate_code,
    )


def test_moshi_mic_start_refused_when_listen_gate_fails(tmp_path: Path) -> None:
    calls: list[str] = []
    recorder = _FakeRecorder()
    ctrl = _moshi_ctrl(
        tmp_path, talk_fn=lambda *a, **k: calls.append("talk") or {}, gate_code="moshi_unreachable", recorder=recorder
    )
    # The gate runs on the worker thread (it may start the server), so the refusal arrives as a notice.
    assert ctrl.on_mic(True) is None
    # The start notice (no stt_provider) may come first; the refusal must be among the notices.
    assert any(
        n.startswith("Mic off: Moshi is not reachable (moshi_unreachable)") for n in _wait_notices(ctrl)
    )
    assert ctrl.mic_active is False
    assert calls == [] and recorder.started is False


def test_moshi_mic_start_does_not_need_stt_and_runs_call_until_stop(tmp_path: Path) -> None:
    seen: dict = {}
    started = threading.Event()

    def fake_talk(url, io, *, stop, **_kw):
        seen["url"] = url
        seen["io"] = io
        started.set()
        stop.wait(5.0)
        return {"error": "", "sent_frames": 3}

    recorder = _FakeRecorder()
    ctrl = _moshi_ctrl(tmp_path, talk_fn=fake_talk, recorder=recorder)
    assert ctrl.on_mic(True) is None  # no stt_provider set: Moshi is the audio path
    assert started.wait(2.0)
    assert ctrl.mic_active is True
    assert seen["url"] == MOSHI_URL_DEFAULT
    assert recorder.started is False, "the WAV recorder must not run in Moshi mode"
    assert ctrl.on_mic(False) is None
    assert ctrl.mic_active is False
    assert recorder.stopped is False, "no WAV is recorded or sent in Moshi mode"


def _hold_talk(url, io, *, stop, **_kw):
    stop.wait(5.0)
    return {"error": "", "sent_frames": 0}


def test_moshi_call_without_stt_says_spoken_tasks_are_off_at_start(tmp_path: Path) -> None:
    ctrl = _moshi_ctrl(tmp_path, talk_fn=_hold_talk, recorder=_FakeRecorder())
    assert ctrl.on_mic(True) is None
    assert any(vpc.CODE_STT_NOT_CONFIGURED in n and "Voice approvals still work" in n for n in ctrl.call_notices)
    assert ctrl.on_mic(False) is None


def test_moshi_call_with_stt_pinned_has_no_spoken_tasks_off_notice(tmp_path: Path) -> None:
    _write_config(tmp_path, stt_provider=STT_PIN_PROVIDER, voice_layer="moshi")
    ctrl = _moshi_ctrl(tmp_path, talk_fn=_hold_talk, recorder=_FakeRecorder())
    assert ctrl.on_mic(True) is None
    assert not any(vpc.CODE_STT_NOT_CONFIGURED in n for n in ctrl.call_notices)
    assert ctrl.on_mic(False) is None


def test_moshi_mic_stop_posts_nothing_to_bridge(tmp_path: Path) -> None:
    rec = _Recorder()
    ctrl = _moshi_ctrl(tmp_path, talk_fn=lambda url, io, *, stop, **_kw: (stop.wait(5.0), {"error": ""})[1], post=rec)
    assert ctrl.on_mic(True) is None
    assert ctrl.on_mic(False) is None
    assert rec.calls == []


def test_moshi_call_error_is_shown_on_stop(tmp_path: Path) -> None:
    def fake_talk(url, io, *, stop, **_kw):
        return {"error": "moshi_unreachable"}

    ctrl = _moshi_ctrl(tmp_path, talk_fn=fake_talk)
    assert ctrl.on_mic(True) is None
    message = ctrl.on_mic(False)
    assert message is not None and "moshi_unreachable" in message


def test_end_call_stops_moshi_call_even_without_bridge(tmp_path: Path) -> None:
    stopped = threading.Event()

    def fake_talk(url, io, *, stop, **_kw):
        stop.wait(5.0)
        stopped.set()
        return {"error": ""}

    ctrl = _moshi_ctrl(tmp_path, talk_fn=fake_talk)
    assert ctrl.on_mic(True) is None
    result = ctrl.on_end()
    assert stopped.is_set(), "hang-up must end the Moshi call"
    assert result.code == vpc.CODE_BRIDGE_NOT_RUNNING
    assert ctrl.mic_active is False


def test_moshi_call_runs_real_talk_over_loopback_echo_server(tmp_path: Path) -> None:
    """Integration: the controller's default talk path opens a real Moshi websocket (loopback stub)."""
    from websockets.sync.server import serve

    from hive_planner.voice_moshi import KIND_HANDSHAKE

    handshakes: list[int] = []

    def handler(ws):
        handshakes.append(1)
        ws.send(bytes([KIND_HANDSHAKE]))
        for _msg in ws:
            pass

    server = serve(handler, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"ws://127.0.0.1:{server.socket.getsockname()[1]}/api/chat"
    try:
        _write_config(tmp_path, moshi_url=url)
        fake_io = _FakeIO()
        ctrl = VoicePanelController(lambda: tmp_path, post=_Recorder(), io_factory=lambda device: fake_io)
        assert ctrl.on_mic(True) is None
        # Wait for the call to open the devices (gate, then talk); stopping earlier is covered
        # by test_stop_during_listen_gate_never_opens_the_call.
        deadline = time.monotonic() + 5.0
        while not fake_io.opened and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ctrl.on_mic(False) is None
        assert handshakes, "the call must reach the Moshi server (gate + call handshakes)"
        assert fake_io.opened and fake_io.closed, "mic and speaker opened and closed by the call"
        assert ctrl._talk_thread is None
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_moshi_call_text_replies_to_pending_approval(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}
    started = threading.Event()

    def fake_talk(url, io, *, stop, on_text=None, **_kw):
        captured["on_text"] = on_text
        started.set()
        stop.wait(5.0)
        return {"error": ""}

    post = _Recorder(status=200, payload={"status": "approved"})
    ctrl = _moshi_ctrl(tmp_path, talk_fn=fake_talk, post=post)
    monkeypatch.setattr(ctrl, "bridge_running", lambda: True)
    monkeypatch.setattr(
        ctrl,
        "_get_from_bridge",
        lambda route: (200, {
            "pending": True, "task_id": "t-m", "request_id": "r-m",
            "kind": "write_or_command", "action": "edit src/app.py",
        }),
    )
    assert ctrl.on_mic(True) is None
    assert started.wait(2.0)
    assert captured["on_text"] is not None
    assert captured["on_text"]("approve edit src/app.py") is True
    assert [route for route, _ in post.calls] == ["/v1/reply"]
    body = post.calls[0][1]
    assert body["task_id"] == "t-m" and body["request_id"] == "r-m"
    assert body["text"] == "approve edit src/app.py"
    assert "wav_path" not in body and "client_request_id" not in body
    assert ctrl.on_mic(False) is None


def test_moshi_call_text_is_not_a_new_task_when_nothing_pending(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}
    started = threading.Event()

    def fake_talk(url, io, *, stop, on_text=None, **_kw):
        captured["on_text"] = on_text
        started.set()
        stop.wait(5.0)
        return {"error": ""}

    post = _Recorder()
    ctrl = _moshi_ctrl(tmp_path, talk_fn=fake_talk, post=post)
    monkeypatch.setattr(ctrl, "bridge_running", lambda: True)
    monkeypatch.setattr(ctrl, "_get_from_bridge", lambda route: (200, {"pending": False}))
    assert ctrl.on_mic(True) is None
    assert started.wait(2.0)
    assert captured["on_text"]("open the auth file") is False
    assert post.calls == []
    assert ctrl.on_mic(False) is None


def test_moshi_call_joins_streamed_text_until_the_approval_matches(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}
    started = threading.Event()

    def fake_talk(url, io, *, stop, on_text=None, **_kw):
        captured["on_text"] = on_text
        started.set()
        stop.wait(5.0)
        return {"error": ""}

    post = _Recorder(status=200, payload={"status": "reprompt"})
    ctrl = _moshi_ctrl(tmp_path, talk_fn=fake_talk, post=post)
    monkeypatch.setattr(ctrl, "bridge_running", lambda: True)
    monkeypatch.setattr(
        ctrl,
        "_get_from_bridge",
        lambda route: (200, {
            "pending": True, "task_id": "t-m", "request_id": "r-m",
            "action": "edit src/app.py",
        }),
    )
    assert ctrl.on_mic(True) is None
    assert started.wait(2.0)
    assert captured["on_text"]("approve") is True
    post.payload = {"status": "approved"}
    assert captured["on_text"]("edit src/app.py") is True
    assert [route for route, _ in post.calls] == ["/v1/reply", "/v1/reply"]
    assert post.calls[0][1]["text"] == "approve"
    assert post.calls[1][1]["text"] == "approve edit src/app.py"
    assert ctrl._moshi_approval_buf == ""
    assert ctrl.on_mic(False) is None


def test_moshi_unmatched_approval_text_does_not_submit(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}
    started = threading.Event()

    def fake_talk(url, io, *, stop, on_text=None, **_kw):
        captured["on_text"] = on_text
        started.set()
        stop.wait(5.0)
        return {"error": ""}

    post = _Recorder(status=200, payload={"status": "reprompt", "spoken": "Say approve or deny edit src/app.py."})
    ctrl = _moshi_ctrl(tmp_path, talk_fn=fake_talk, post=post)
    monkeypatch.setattr(ctrl, "bridge_running", lambda: True)
    monkeypatch.setattr(
        ctrl,
        "_get_from_bridge",
        lambda route: (200, {
            "pending": True, "task_id": "t-m", "request_id": "r-m",
            "action": "edit src/app.py",
        }),
    )
    assert ctrl.on_mic(True) is None
    assert started.wait(2.0)
    assert captured["on_text"]("yeah go ahead") is True
    assert [route for route, _ in post.calls] == ["/v1/reply"]
    assert ctrl.on_mic(False) is None


def test_status_reports_voice_layer(tmp_path: Path) -> None:
    assert _controller(tmp_path).status()["voice_layer"] == "moshi"
    _write_config(tmp_path, voice_layer="typed")
    assert _controller(tmp_path).status()["voice_layer"] == "typed"


# --- T056 speech-to-task: an utterance becomes a task through the spoken submit route -----------


def _utterance_ctrl(tmp_path: Path, monkeypatch, post):
    ctrl = _moshi_ctrl(tmp_path, talk_fn=lambda *a, **k: {}, post=post)
    monkeypatch.setattr(ctrl, "bridge_running", lambda: True)
    monkeypatch.setattr(ctrl, "_get_from_bridge", lambda route: (200, {"pending": False}))
    return ctrl


def _wait_notices(ctrl: VoicePanelController, count: int = 1, timeout: float = 3.0) -> list[str]:
    import time as _time

    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        with ctrl._notice_lock:
            if len(ctrl.call_notices) >= count:
                return list(ctrl.call_notices)
        _time.sleep(0.01)
    return list(ctrl.call_notices)


def test_moshi_utterance_is_sent_to_spoken_submit_as_a_task(tmp_path: Path, monkeypatch) -> None:
    import numpy as np

    post = _Recorder(status=200, payload={"task_id": "task_1"})
    ctrl = _utterance_ctrl(tmp_path, monkeypatch, post)
    ctrl._on_moshi_utterance(np.full(2400, 0.2, dtype=np.float32), 24_000)
    notices = _wait_notices(ctrl)
    assert notices == ["Heard you. Sent to the bridge."]
    assert [route for route, _ in post.calls] == ["/v1/submit/spoken"]
    body = post.calls[0][1]
    assert body["mode"] == "ask"
    assert body["moshi_live_call"] is True, "a live-call utterance must skip the bridge listen gate (R37)"
    assert Path(body["wav_path"]).parts[:3] == (".hive", "voice-bot", "recordings")
    assert (tmp_path / body["wav_path"]).is_file(), "the utterance is saved in the workspace before submit"


def test_moshi_utterance_refusal_is_recorded_not_dropped(tmp_path: Path, monkeypatch) -> None:
    import numpy as np

    post = _Recorder(status=409, payload={"error": "stt_not_configured", "message": "Speech input is off."})
    ctrl = _utterance_ctrl(tmp_path, monkeypatch, post)
    ctrl._on_moshi_utterance(np.full(2400, 0.2, dtype=np.float32), 24_000)
    notices = _wait_notices(ctrl)
    assert notices == ["Speech input is off."]



# --- review fixes (2026-11-15): stop during gate, dropped call state, pending poll memo ----------


def test_stop_during_listen_gate_never_opens_the_call(tmp_path: Path) -> None:
    """Stop pressed while the gate is still waiting (cold server start) must not open the devices."""
    gate_started = threading.Event()
    release_gate = threading.Event()
    calls: list[str] = []

    def slow_gate(cfg):
        gate_started.set()
        release_gate.wait(5.0)
        return None

    ctrl = VoicePanelController(
        lambda: tmp_path,
        post=_Recorder(),
        talk_fn=lambda *a, **k: calls.append("talk") or {},
        io_factory=lambda device: _FakeIO(),
        listen_gate=slow_gate,
    )
    assert ctrl.on_mic(True) is None
    assert gate_started.wait(2.0)
    # Stop returns without waiting for the gate; then the gate finishes.
    ctrl._talk_stop.set()
    release_gate.set()
    ctrl._talk_thread.join(timeout=3.0)
    assert calls == [], "a call stopped during the gate must not open the audio devices"


def test_dropped_call_clears_listening_and_reports_the_error(tmp_path: Path) -> None:
    """A call that ends on its own (socket drop) must not keep the panel on 'listening'."""

    def dropping_talk(url, io, *, stop, **_kw):
        return {"error": "moshi_connection_lost"}

    ctrl = _moshi_ctrl(tmp_path, talk_fn=dropping_talk)
    assert ctrl.on_mic(True) is None
    notices = _wait_notices(ctrl)
    assert ctrl.mic_active is False
    assert any("moshi_connection_lost" in note for note in notices)


def test_pending_approval_poll_is_memoised_across_text_frames(tmp_path: Path, monkeypatch) -> None:
    """Moshi text arrives per token; the bridge poll must not run once per frame."""
    polls: list[str] = []
    post = _Recorder(status=200, payload={"status": "reprompt"})
    ctrl = _moshi_ctrl(tmp_path, talk_fn=lambda *a, **k: {}, post=post)
    monkeypatch.setattr(ctrl, "bridge_running", lambda: True)

    def fake_get(route):
        polls.append(route)
        return 200, {"pending": True, "task_id": "task_1", "request_id": "req_1"}

    monkeypatch.setattr(ctrl, "_get_from_bridge", fake_get)
    for fragment in ("approve", "the", "edit"):
        assert ctrl._on_moshi_text(fragment) is True
    assert polls == ["/v1/approval"], "one poll covers a burst of text frames"
    assert len(post.calls) == 3

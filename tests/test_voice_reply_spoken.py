"""Spoken approval replies: WAV -> transcript -> the pending approval only (R6, T008 voice path).

Runner and bridge tests use a real VoiceTaskRunner over the ACP turn server and a real loopback
bridge. The STT adapter is a fake, so no faster-whisper model is loaded. The panel test injects
the bridge calls, so it needs no socket.
"""

from __future__ import annotations

import dataclasses
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

import hive_planner.voice_task as voice_task
from hive_planner.launcher.voice_panel_controller import VoicePanelController
from hive_planner.voice_bridge import VoiceBridge
from hive_planner.voice_moshi import KIND_TEXT, MoshiConversation
from hive_planner.voice_task import DelegationError, VoiceTaskRunner
from voice_turn_support import make_repo, make_runner, wait_task_state, wait_task_terminal


class _FakeWhisper:
    """Returns whatever the test set in `TRANSCRIPT`. Records every file it was asked to read."""

    TRANSCRIPT = "approve edit src/app.py"
    FILES: list[Path] = []

    def __init__(self, model_dir: Any) -> None:
        self.model_dir = model_dir

    def transcribe(self, audio: bytes) -> str:
        return self.TRANSCRIPT

    def transcribe_file(self, wav_path: Path) -> str:
        assert wav_path.is_file()
        self.FILES.append(wav_path)
        return self.TRANSCRIPT


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo, monkeypatch):
    _FakeWhisper.FILES = []
    _FakeWhisper.TRANSCRIPT = "approve edit src/app.py"
    monkeypatch.setattr(voice_task, "resolve_pinned_model_dir", lambda: repo.root)
    monkeypatch.setattr(voice_task, "FasterWhisperAdapter", _FakeWhisper)
    r = make_runner(repo)
    # voice_layer typed: this test covers the STT reply route, not the Moshi listen gate (T053).
    r.config = dataclasses.replace(r.config, stt_provider="faster-whisper", voice_layer="typed")
    yield r
    r.close()


@pytest.fixture
def bridge(runner: VoiceTaskRunner):
    b = VoiceBridge(runner)
    b.start()
    yield b
    b.close()


def _call(bridge: VoiceBridge, method: str, path: str, *, token: str | None, body: Any = None) -> tuple[int, dict]:
    url = f"http://127.0.0.1:{bridge.port}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    if token is not None:
        req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _pending(runner: VoiceTaskRunner, task_id: str) -> dict:
    wait_task_state(runner, task_id, "awaiting_approval")
    return runner.state.coding_tasks[task_id].approval


def _spoken_body(repo, task_id: str, request_id: str, wav: str = "reply.wav") -> dict:
    (repo.root / wav).write_bytes(b"RIFF-fake")
    return {"workspace": str(repo.root), "task_id": task_id, "request_id": request_id, "wav_path": wav}


# --- runner: reply_spoken ------------------------------------------------------------------


def test_runner_spoken_approval_resolves_the_pending_request(repo, runner):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="rs-1")
    pending = _pending(runner, out["task_id"])
    (repo.root / "reply.wav").write_bytes(b"RIFF-fake")

    reply = runner.reply_spoken(
        request_id=pending["request_id"], task_id=out["task_id"], wav_path="reply.wav",
    )
    assert reply["status"] == "approved"
    assert reply["transcript"] == "approve edit src/app.py"
    assert _FakeWhisper.FILES == [(repo.root / "reply.wav").resolve()]
    assert wait_task_terminal(runner, out["task_id"]) == "completed"
    assert '"outcome": "selected"' in runner.state.coding_tasks[out["task_id"]].evidence.written_result


def test_runner_spoken_reply_never_becomes_a_follow_up(repo, runner):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="rs-2")
    pending = _pending(runner, out["task_id"])
    _FakeWhisper.TRANSCRIPT = "approve something else"
    (repo.root / "reply.wav").write_bytes(b"RIFF-fake")

    reply = runner.reply_spoken(request_id=pending["request_id"], task_id=out["task_id"], wav_path="reply.wav")
    assert reply["status"] != "approved"
    assert runner.state.queue == []  # R6: an approval reply routes to the approval, never the queue
    assert runner.state.coding_tasks[out["task_id"]].state == "awaiting_approval"
    runner.reply_approval("deny edit src/app.py", request_id=pending["request_id"])
    wait_task_terminal(runner, out["task_id"])


def test_moshi_text_resolves_pending_approval_without_stt_or_wav(repo, runner):
    """Default Moshi call path: 0x02 text -> reply_approval. No WAV, no stt_provider."""
    runner.config = dataclasses.replace(runner.config, stt_provider=None, voice_layer="moshi")
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="ms-1")
    pending = _pending(runner, out["task_id"])

    class _Sess:
        closed = False

        def send_audio(self, _opus):
            raise AssertionError("approval text must not send audio")

    def on_text(text: str) -> bool:
        view = runner.pending_approval_view()
        if not view.get("pending"):
            return False
        runner.reply_approval(text, request_id=view["request_id"], task_id=view["task_id"])
        return True

    conv = MoshiConversation(_Sess(), on_text=on_text)
    conv.handle_frame(KIND_TEXT, b"approve edit src/app.py")
    assert wait_task_terminal(runner, out["task_id"]) == "completed"
    assert runner.state.queue == []
    assert pending["request_id"] == runner.state.coding_tasks[out["task_id"]].approval["request_id"]


def test_moshi_unmatched_text_does_not_become_a_follow_up(repo, runner):
    runner.config = dataclasses.replace(runner.config, stt_provider=None, voice_layer="moshi")
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="ms-2")
    pending = _pending(runner, out["task_id"])

    class _Sess:
        closed = False

        def send_audio(self, _opus):
            raise AssertionError("approval text must not send audio")

    def on_text(text: str) -> bool:
        view = runner.pending_approval_view()
        if not view.get("pending"):
            return False
        runner.reply_approval(text, request_id=view["request_id"], task_id=view["task_id"])
        return True

    conv = MoshiConversation(_Sess(), on_text=on_text)
    conv.handle_frame(KIND_TEXT, b"yeah go ahead")
    assert runner.state.queue == []
    assert runner.state.coding_tasks[out["task_id"]].state == "awaiting_approval"
    runner.reply_approval("deny edit src/app.py", request_id=pending["request_id"])
    wait_task_terminal(runner, out["task_id"])


def test_runner_spoken_reply_refuses_without_stt_and_keeps_the_approval(repo, runner):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="rs-3")
    pending = _pending(runner, out["task_id"])
    runner.config = dataclasses.replace(runner.config, stt_provider=None)
    (repo.root / "reply.wav").write_bytes(b"RIFF-fake")

    with pytest.raises(DelegationError) as exc:
        runner.reply_spoken(request_id=pending["request_id"], task_id=out["task_id"], wav_path="reply.wav")
    assert exc.value.code == "stt_not_configured"
    assert runner.state.coding_tasks[out["task_id"]].state == "awaiting_approval"
    runner.reply_approval("deny edit src/app.py", request_id=pending["request_id"])
    wait_task_terminal(runner, out["task_id"])


# --- bridge: POST /v1/reply/spoken ---------------------------------------------------------


def test_spoken_reply_route_approves_over_loopback(repo, runner, bridge):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="br-1")
    pending = _pending(runner, out["task_id"])

    status, body = _call(bridge, "POST", "/v1/reply/spoken", token=bridge.token,
                         body=_spoken_body(repo, out["task_id"], pending["request_id"]))
    assert status == 200, body
    assert body["status"] == "approved"
    assert body["transcript"] == "approve edit src/app.py"
    assert wait_task_terminal(runner, out["task_id"]) == "completed"


def test_spoken_reply_route_refuses_without_token_and_changes_nothing(repo, runner, bridge):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="br-2")
    pending = _pending(runner, out["task_id"])

    status, _ = _call(bridge, "POST", "/v1/reply/spoken", token="wrong",
                      body=_spoken_body(repo, out["task_id"], pending["request_id"]))
    assert status == 401
    assert _FakeWhisper.FILES == []  # refused before any transcription
    assert runner.state.coding_tasks[out["task_id"]].state == "awaiting_approval"
    runner.reply_approval("deny edit src/app.py", request_id=pending["request_id"])
    wait_task_terminal(runner, out["task_id"])


def test_spoken_reply_route_stale_request_is_409_and_executes_nothing(repo, runner, bridge):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="br-3")
    pending = _pending(runner, out["task_id"])

    status, body = _call(bridge, "POST", "/v1/reply/spoken", token=bridge.token,
                         body=_spoken_body(repo, out["task_id"], "req-not-the-pending-one"))
    assert status == 409
    assert body["status"] == "stale_approval"
    assert runner.state.coding_tasks[out["task_id"]].state == "awaiting_approval"
    runner.reply_approval("deny edit src/app.py", request_id=pending["request_id"])
    wait_task_terminal(runner, out["task_id"])


def test_spoken_reply_route_missing_wav_is_refused(repo, runner, bridge):
    out = runner.submit("NEEDS_APPROVAL:edit src/app.py", client_request_id="br-4")
    pending = _pending(runner, out["task_id"])
    body = {"workspace": str(repo.root), "task_id": out["task_id"], "request_id": pending["request_id"]}

    status, payload = _call(bridge, "POST", "/v1/reply/spoken", token=bridge.token, body=body)
    assert status == 400 and payload["error"] == "missing_wav_path"
    runner.reply_approval("deny edit src/app.py", request_id=pending["request_id"])
    wait_task_terminal(runner, out["task_id"])


# --- panel: a recording goes to the reply route while an approval is pending ---------------


class _Post:
    def __init__(self, status: int = 200, payload: dict | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.status = status
        self.payload = payload or {"status": "approved"}

    def __call__(self, route: str, body: dict) -> tuple[int, dict]:
        self.calls.append((route, body))
        return self.status, self.payload


class _Recorder:
    def start(self) -> None:
        pass

    def stop(self) -> bytes:
        return b"RIFF-fake-wav"


def _panel(tmp_path: Path, monkeypatch, *, pending: dict | None, post: _Post) -> VoicePanelController:
    cfg_dir = tmp_path / ".hive" / "voice-bot"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.json").write_text(
        json.dumps({"stt_provider": "faster-whisper", "voice_layer": "typed"}), encoding="utf-8",
    )
    ctrl = VoicePanelController(lambda: tmp_path, post=post, recorder=_Recorder())
    monkeypatch.setattr(ctrl, "bridge_running", lambda: True)
    monkeypatch.setattr(ctrl, "_get_from_bridge", lambda route: (200, dict(pending or {"pending": False})))
    return ctrl


def test_panel_routes_recording_to_reply_when_approval_pending(tmp_path, monkeypatch):
    post = _Post()
    ctrl = _panel(tmp_path, monkeypatch, pending={
        "pending": True, "task_id": "t-7", "request_id": "r-7", "kind": "write_or_command",
        "action": "edit src/app.py",
    }, post=post)
    assert ctrl.on_mic(True) is None
    assert ctrl.on_mic(False) is None

    assert [route for route, _ in post.calls] == ["/v1/reply/spoken"]
    body = post.calls[0][1]
    assert body["task_id"] == "t-7" and body["request_id"] == "r-7"
    assert "client_request_id" not in body  # not a new instruction
    assert (tmp_path / body["wav_path"]).read_bytes() == b"RIFF-fake-wav"


def test_panel_routes_recording_to_submit_when_nothing_pending(tmp_path, monkeypatch):
    post = _Post(payload={"status": "running", "task_id": "t-9"})
    ctrl = _panel(tmp_path, monkeypatch, pending=None, post=post)
    assert ctrl.on_mic(True) is None
    assert ctrl.on_mic(False) is None
    assert [route for route, _ in post.calls] == ["/v1/submit/spoken"]


def test_panel_shows_a_refused_approval_reply(tmp_path, monkeypatch):
    post = _Post(status=409, payload={"status": "stale_approval", "message": "that approval is no longer pending"})
    ctrl = _panel(tmp_path, monkeypatch, pending={
        "pending": True, "task_id": "t-8", "request_id": "r-8",
    }, post=post)
    ctrl.on_mic(True)
    message = ctrl.on_mic(False)
    assert message == "that approval is no longer pending"

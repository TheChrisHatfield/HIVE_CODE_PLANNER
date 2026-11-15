"""T051-T054 / R36-R37: Moshi adapter tests.

These tests use a real in-process websocket server on loopback (not a mock object), so the
handshake and frame parsing run through the same `websockets` client code as production.
Fixture results never write G7 `pass`; only `voice-bot moshi-probe --record` may do that.
"""

from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

import pytest
from websockets.sync.server import serve

import hive_planner.voice_bot as vb
import hive_planner.voice_moshi as vm
from hive_planner.voice_bot import (
    STT_PIN_PROVIDER,
    TypedInstructionAdapter,
    VoiceBotConfig,
    VoiceBotError,
    speech_adapter,
    voice_bot_config_path,
)
from hive_planner.voice_moshi import (
    KIND_AUDIO,
    KIND_HANDSHAKE,
    KIND_TEXT,
    MOSHI_SPOKEN,
    MoshiVoiceAdapter,
    moshi_listen_gate,
    moshi_live_probe,
    open_session,
)


def _closed_port() -> int:
    """A loopback port with nothing listening on it (bound, read, then released)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def moshi_server():
    """Loopback websocket server that behaves like a Moshi server for the fixture tests.

    On connect it sends the `0x00` handshake. For every `0x01` mic frame it replies with one
    `0x01` audio frame and one `0x02` text frame. Yields the ws:// URL.
    """

    def handler(ws):
        ws.send(bytes([KIND_HANDSHAKE]))
        for msg in ws:
            if isinstance(msg, bytes) and msg[:1] == bytes([KIND_AUDIO]):
                ws.send(bytes([KIND_AUDIO]) + b"opus-out")
                ws.send(bytes([KIND_TEXT]) + "hi there".encode("utf-8"))

    server = serve(handler, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.socket.getsockname()[1]
    try:
        yield f"ws://127.0.0.1:{port}/api/chat"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture
def silent_server():
    """Loopback server that accepts the socket but never sends the handshake."""

    def handler(ws):
        for _msg in ws:
            pass

    server = serve(handler, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.socket.getsockname()[1]
    try:
        yield f"ws://127.0.0.1:{port}/api/chat"
    finally:
        server.shutdown()
        thread.join(timeout=5)


# --- T051: config and adapter selection -------------------------------------------------


def test_voice_layer_defaults_to_moshi_and_url_defaults_to_operator_port():
    cfg = VoiceBotConfig()
    assert cfg.voice_layer == "moshi"
    assert cfg.moshi_url == "ws://127.0.0.1:8998/api/chat"


def test_voice_layer_rejects_unknown_value():
    with pytest.raises(VoiceBotError, match="voice_layer"):
        VoiceBotConfig(voice_layer="whisper")


def test_moshi_url_must_be_websocket():
    with pytest.raises(VoiceBotError, match="moshi_url"):
        VoiceBotConfig(moshi_url="http://127.0.0.1:8998/api/chat")


def test_voice_layer_flag_changes_the_adapter_chosen():
    moshi_cfg = VoiceBotConfig(voice_layer="moshi", moshi_url="ws://127.0.0.1:9/api/chat")
    typed_cfg = VoiceBotConfig(voice_layer="typed")

    moshi_adapter = speech_adapter(moshi_cfg)
    typed_adapter = speech_adapter(typed_cfg)

    assert isinstance(moshi_adapter, MoshiVoiceAdapter)
    assert moshi_adapter.url == "ws://127.0.0.1:9/api/chat"
    assert isinstance(typed_adapter, TypedInstructionAdapter)
    assert not isinstance(typed_adapter, MoshiVoiceAdapter)


def test_voice_layer_and_url_load_from_repo_config(tmp_path: Path):
    from voice_turn_support import make_repo

    paths = make_repo(tmp_path)
    url = "ws://127.0.0.1:9999/api/chat"
    path = voice_bot_config_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"voice_layer": "typed", "moshi_url": url}), encoding="utf-8")

    loaded = vb.load_voice_bot_config(paths)
    assert loaded.voice_layer == "typed"
    assert loaded.moshi_url == url
    assert not isinstance(speech_adapter(loaded), MoshiVoiceAdapter)


# --- T052: websocket adapter over a real loopback server --------------------------------


def test_handshake_then_audio_round_trip(moshi_server):
    session = open_session(moshi_server, timeout=3.0)
    try:
        session.send_audio(b"mic-frame")
        frames = []
        for _ in range(2):
            frame = session.recv_frame(timeout=3.0)
            assert frame is not None
            frames.append(frame)
        kinds = [kind for kind, _ in frames]
        assert KIND_AUDIO in kinds
        assert KIND_TEXT in kinds
        text = next(payload for kind, payload in frames if kind == KIND_TEXT)
        assert text == b"hi there"
    finally:
        session.close()


def test_send_audio_prefixes_the_audio_kind_byte(moshi_server):
    sent: list[bytes] = []
    session = open_session(moshi_server, timeout=3.0)
    real_send = session._ws.send

    def spy(data):
        sent.append(data)
        return real_send(data)

    session._ws.send = spy  # type: ignore[method-assign]
    try:
        session.send_audio(b"abc")
        session.send_audio(b"")  # empty frames are dropped, not sent
    finally:
        session.close()
    assert sent == [bytes([KIND_AUDIO]) + b"abc"]


def test_missing_handshake_is_unreachable(silent_server, monkeypatch):
    # The server accepts the socket but sends no 0x00 handshake, so the open must fail.
    monkeypatch.setattr(vm, "CONNECT_TIMEOUT_S", 0.5)
    with pytest.raises(VoiceBotError, match="moshi_unreachable"):
        open_session(silent_server, timeout=0.5)


def test_closed_port_is_unreachable():
    url = f"ws://127.0.0.1:{_closed_port()}/api/chat"
    with pytest.raises(VoiceBotError, match="moshi_unreachable"):
        open_session(url, timeout=0.5)


def test_package_missing_is_unavailable(monkeypatch):
    monkeypatch.setattr(vm, "moshi_installed", lambda: False)
    with pytest.raises(VoiceBotError, match="moshi_unavailable"):
        open_session("ws://127.0.0.1:1/api/chat", timeout=0.5)


def test_live_probe_counts_round_trip_on_stub_but_writes_no_evidence(moshi_server, tmp_path, monkeypatch):
    # Probe logic against the loopback stub: the round trip is detected. This is fixture
    # output only; the register is not touched and G7 is not claimed.
    from voice_turn_support import make_repo

    paths = make_repo(tmp_path)
    register = vm.evidence_register_path(paths)
    register.parent.mkdir(parents=True, exist_ok=True)
    register.write_text("| G7 | x | x | x | **blocked** | 2026-11-14 | x |\n", encoding="utf-8")
    before = register.read_text(encoding="utf-8")

    result = moshi_live_probe(moshi_server, timeout=5.0, frames=3)

    # The probe stops at the first round-trip frame (audio or text), so exactly one is counted.
    assert result["handshake_ms"] is not None
    assert result["audio_frames"] + result["text_frames"] >= 1
    assert result["g7"] == "pass"
    assert register.read_text(encoding="utf-8") == before


def test_live_probe_unreachable_is_blocked_not_fail():
    url = f"ws://127.0.0.1:{_closed_port()}/api/chat"
    result = moshi_live_probe(url, timeout=0.5)
    assert result["g7"] == "blocked"
    assert result["reason"] == "moshi_unreachable"


# --- T053: unreachable and unavailable paths --------------------------------------------


def test_listen_gate_is_none_for_typed_layer_without_probing():
    assert moshi_listen_gate(VoiceBotConfig(voice_layer="typed", moshi_url="ws://127.0.0.1:1/x")) is None


def test_listen_gate_passes_when_handshake_arrives(moshi_server):
    assert moshi_listen_gate(VoiceBotConfig(voice_layer="moshi", moshi_url=moshi_server)) is None


def test_listen_gate_refuses_unreachable_server_when_autostart_off():
    cfg = VoiceBotConfig(
        voice_layer="moshi",
        moshi_url=f"ws://127.0.0.1:{_closed_port()}/api/chat",
        moshi_autostart=False,
    )
    assert moshi_listen_gate(cfg) == "moshi_unreachable"


def test_listen_gate_refuses_when_package_missing(monkeypatch):
    monkeypatch.setattr(vm, "moshi_installed", lambda: False)
    cfg = VoiceBotConfig(voice_layer="moshi", moshi_url="ws://127.0.0.1:1/x")
    assert moshi_listen_gate(cfg) == "moshi_unavailable"


def test_spoken_notice_text_is_stable_for_both_refusals():
    assert "not reachable" in MOSHI_SPOKEN["moshi_unreachable"]
    assert "not installed" in MOSHI_SPOKEN["moshi_unavailable"]


def _write_repo_config(paths, data: dict) -> None:
    path = voice_bot_config_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class _FailingStt:
    """Injected STT adapter. Must never be reached when the Moshi gate refuses."""

    def transcribe(self, _audio):  # pragma: no cover - asserted unreachable
        raise AssertionError("STT ran although the Moshi listen gate refused")

    def transcribe_file(self, _path):  # pragma: no cover - asserted unreachable
        raise AssertionError("STT ran although the Moshi listen gate refused")


def test_spoken_submit_refused_when_moshi_unreachable_creates_no_task(tmp_path: Path):
    from hive_planner.voice_task import DelegationError
    from voice_turn_support import make_repo, make_runner

    paths = make_repo(tmp_path)
    _write_repo_config(
        paths,
        {
            "voice_layer": "moshi",
            "moshi_url": f"ws://127.0.0.1:{_closed_port()}/api/chat",
            "moshi_autostart": False,
            "stt_provider": STT_PIN_PROVIDER,
        },
    )
    runner = make_runner(paths)
    try:
        with pytest.raises(DelegationError) as excinfo:
            runner.submit_spoken(
                audio=b"RIFF-not-real-wav",
                client_request_id="moshi-down",
                stt_adapter=_FailingStt(),
            )
        assert "moshi_unreachable" in str(excinfo.value)
        assert excinfo.value.spoken == MOSHI_SPOKEN["moshi_unreachable"]
        assert runner.state.coding_tasks == {}
    finally:
        runner.close()


class _CountingStt:
    """Injected STT adapter that returns an empty transcript, so a run that gets past the gate
    stops at `stt_failed` with no task. Counts calls to show whether transcription ran."""

    def __init__(self) -> None:
        self.calls = 0

    def transcribe(self, _audio):
        self.calls += 1
        return "   "

    def transcribe_file(self, _path):
        self.calls += 1
        return "   "


def test_live_call_utterance_skips_listen_gate_only_when_flagged(tmp_path: Path):
    # R37 (2026-11-15): a live panel call holds the Moshi slot, so its utterance must skip the probe.
    # Without the flag the same refusing gate still blocks the spoken turn before transcription.
    from hive_planner.voice_task import DelegationError
    from voice_turn_support import make_repo, make_runner

    paths = make_repo(tmp_path)
    _write_repo_config(
        paths,
        {
            "voice_layer": "moshi",
            "moshi_url": f"ws://127.0.0.1:{_closed_port()}/api/chat",
            "moshi_autostart": False,
            "stt_provider": STT_PIN_PROVIDER,
        },
    )
    runner = make_runner(paths)
    stt = _CountingStt()
    try:
        with pytest.raises(DelegationError) as gated:
            runner.submit_spoken(audio=b"RIFF", client_request_id="gated", stt_adapter=stt)
        assert gated.value.code == "moshi_unreachable"
        assert stt.calls == 0

        with pytest.raises(DelegationError) as live:
            runner.submit_spoken(
                audio=b"RIFF", client_request_id="live", stt_adapter=stt, moshi_live_call=True,
            )
        assert live.value.code == "stt_failed"  # the gate passed; transcription then rejected the empty text
        assert stt.calls == 1
        assert runner.state.coding_tasks == {}
    finally:
        runner.close()


def test_typed_submit_is_not_gated_by_moshi_outage(tmp_path: Path):
    # R36: the typed path is the fallback and stays open when Moshi is down.
    from voice_turn_support import make_repo, make_runner, wait_task_terminal

    paths = make_repo(tmp_path)
    _write_repo_config(
        paths,
        {"voice_layer": "moshi", "moshi_url": f"ws://127.0.0.1:{_closed_port()}/api/chat"},
    )
    runner = make_runner(paths)
    try:
        out = runner.submit("hello", client_request_id="typed-while-moshi-down")
        assert wait_task_terminal(runner, out["task_id"]) in ("completed", "failed")
        assert out["task_id"] in runner.state.coding_tasks
    finally:
        runner.close()


# --- T054: speak routing ----------------------------------------------------------------


def test_moshi_speak_delegates_to_speech_out_and_never_speaks_itself():
    calls: list[str] = []

    class _SpeechOut:
        def speak(self, text):
            calls.append(text)
            return {"played": False, "audio": False, "text": text, "path": "typed"}

    adapter = MoshiVoiceAdapter(speech_out=_SpeechOut(), url="ws://127.0.0.1:1/x")
    payload = adapter.speak("Tests were not run. Task completed.")

    assert calls == ["Tests were not run. Task completed."]
    assert payload["voice_layer"] == "moshi"
    assert payload["audio"] is False
    assert payload["played"] is False


def test_moshi_transcription_is_refused_until_wer_row_exists():
    adapter = MoshiVoiceAdapter(speech_out=TypedInstructionAdapter(), url="ws://127.0.0.1:1/x")
    with pytest.raises(VoiceBotError, match="stt_unavailable"):
        adapter.transcribe(b"audio")

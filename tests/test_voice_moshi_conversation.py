"""T056 / R36-R37: duplex Moshi conversation loop tests.

The server is a real loopback websocket that echoes the real Opus frames HIVE sends, so Opus
encode and decode run through `sphn` on both sides. This proves the loop wiring, not model
quality. Only `voice-bot moshi-probe --record` against a real Moshi server may set G7 pass.
Model text is recorded in the transcript and must never create a task.
"""

from __future__ import annotations

import socket
import threading
import time

import numpy as np
import pytest
from websockets.sync.server import serve

from hive_planner.voice_moshi import (
    KIND_AUDIO,
    KIND_HANDSHAKE,
    KIND_TEXT,
    MoshiConversation,
    SoundDeviceIO,
    open_session,
    run_conversation,
)
from hive_planner.voice_bot import VoiceBotError

SR = 24_000


def _sine(samples: int) -> np.ndarray:
    t = np.arange(samples, dtype=np.float32) / SR
    return (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def _serve(handler):
    server = serve(handler, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.socket.getsockname()[1]
    return server, thread, f"ws://127.0.0.1:{port}/api/chat"


@pytest.fixture
def echo_server():
    """Handshake, then echo each mic `0x01` frame back as model audio and send one text frame."""

    def handler(ws):
        ws.send(bytes([KIND_HANDSHAKE]))
        for msg in ws:
            if isinstance(msg, bytes) and msg[:1] == bytes([KIND_AUDIO]):
                ws.send(bytes([KIND_AUDIO]) + msg[1:])
                ws.send(bytes([KIND_TEXT]) + "heard you".encode("utf-8"))

    server, thread, url = _serve(handler)
    try:
        yield url
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_full_duplex_round_trip_sends_mic_and_plays_model_audio(echo_server):
    played: list[np.ndarray] = []
    stop = threading.Event()
    feeds = {"n": 0}

    def mic_read(timeout: float):
        feeds["n"] += 1
        if feeds["n"] > 400 or (played and feeds["n"] > 5):
            stop.set()
            return None
        time.sleep(0.02)
        return _sine(SR // 10)  # 100 ms blocks

    def speaker(pcm):
        played.append(np.asarray(pcm, dtype=np.float32))

    result = run_conversation(
        echo_server, mic_read=mic_read, speaker=speaker, stop=stop, timeout=3.0
    )

    assert result["error"] == ""
    assert result["sent_frames"] > 0, "mic audio must reach the server as 0x01 frames"
    assert played, "model audio must be decoded and handed to the speaker"
    assert sum(p.size for p in played) == result["audio_out_samples"]
    assert result["transcript"] and result["transcript"][0] == "heard you"
    assert result["speaker_errors"] == 0


def test_run_conversation_routes_model_text_to_on_text(echo_server):
    seen: list[str] = []
    stop = threading.Event()
    feeds = {"n": 0}

    def mic_read(timeout: float):
        feeds["n"] += 1
        if feeds["n"] > 400 or seen:
            stop.set()
            return None
        time.sleep(0.02)
        return _sine(SR // 10)

    result = run_conversation(
        echo_server,
        mic_read=mic_read,
        speaker=lambda pcm: None,
        stop=stop,
        timeout=3.0,
        on_text=lambda t: seen.append(t) or False,
    )
    assert result["error"] == ""
    assert "heard you" in seen


class _FakeSession:
    closed = False

    def send_audio(self, _opus):
        raise AssertionError("no mic audio was fed")


def test_model_text_is_transcript_only_not_evidence():
    conv = MoshiConversation(_FakeSession())
    assert conv.handle_frame(KIND_TEXT, "open the auth file".encode("utf-8")) is None
    assert conv.transcript == ["open the auth file"]
    assert conv.handle_frame(0x05, b"unknown kind") is None
    assert conv.transcript == ["open the auth file"], "unknown kinds are ignored, not recorded"


def test_model_text_invokes_on_text_and_does_not_create_a_task():
    seen: list[str] = []
    conv = MoshiConversation(_FakeSession(), on_text=lambda t: seen.append(t) or True)
    assert conv.handle_frame(KIND_TEXT, b"approve edit src/app.py") is None
    assert seen == ["approve edit src/app.py"]
    assert conv.transcript == ["approve edit src/app.py"]
    assert conv.tool_results == []


def test_on_text_true_skips_tool_broker_offer():
    class _Broker:
        pending = None
        offered: list[str] = []

        def offer(self, text: str):
            self.offered.append(text)
            return {"status": "refused", "reason": "no_tool_line"}

    broker = _Broker()
    conv = MoshiConversation(_FakeSession(), tool_broker=broker, on_text=lambda t: True)
    conv.handle_frame(KIND_TEXT, b'TOOL: submit_coding_task {"instruction": "x", "mode": "ask"}')
    assert broker.offered == []
    assert conv.tool_results == []
    assert conv.transcript[-1].startswith("TOOL:")


def test_stop_event_ends_a_silent_conversation_promptly():
    def handler(ws):
        ws.send(bytes([KIND_HANDSHAKE]))
        for _msg in ws:
            pass

    server, thread, url = _serve(handler)
    try:
        stop = threading.Event()
        threading.Timer(0.5, stop.set).start()
        started = time.monotonic()
        result = run_conversation(
            url,
            mic_read=lambda timeout: (time.sleep(0.05), _sine(SR // 10))[1],
            speaker=lambda _pcm: None,
            stop=stop,
            timeout=3.0,
        )
        assert time.monotonic() - started < 4.0
        assert result["error"] == ""
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_server_drop_mid_call_reports_unreachable_and_stops():
    def handler(ws):
        ws.send(bytes([KIND_HANDSHAKE]))
        ws.close()

    server, thread, url = _serve(handler)
    try:
        stop = threading.Event()
        started = time.monotonic()
        result = run_conversation(
            url,
            mic_read=lambda timeout: (time.sleep(0.05), _sine(SR // 10))[1],
            speaker=lambda _pcm: None,
            stop=stop,
            timeout=3.0,
        )
        assert time.monotonic() - started < 5.0, "a dropped socket must not hang the loop"
        assert result["error"] == "moshi_unreachable"
        assert stop.is_set()
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_handshake_missing_refuses_before_any_audio_is_sent():
    def handler(ws):
        for _msg in ws:
            pass

    server, thread, url = _serve(handler)
    try:
        with pytest.raises(VoiceBotError, match="moshi_unreachable"):
            run_conversation(
                url,
                mic_read=lambda timeout: None,
                speaker=lambda _pcm: None,
                stop=threading.Event(),
                timeout=2.0,
            )
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_closed_port_refuses_as_unreachable():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(VoiceBotError, match="moshi_unreachable"):
        open_session(f"ws://127.0.0.1:{port}/api/chat", timeout=1.0)


class _FakeStream:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        pass


class _FakeSoundDevice:
    def __init__(self):
        self.inputs: list[_FakeStream] = []
        self.outputs: list[_FakeStream] = []

    def InputStream(self, **kwargs):  # noqa: N802 - mirrors the sounddevice API name
        stream = _FakeStream(**kwargs)
        self.inputs.append(stream)
        return stream

    def OutputStream(self, **kwargs):  # noqa: N802
        stream = _FakeStream(**kwargs)
        self.outputs.append(stream)
        return stream


def test_sounddevice_io_routes_mic_blocks_and_drains_playback():
    fake = _FakeSoundDevice()
    io = SoundDeviceIO(sample_rate=SR, device="Test Mic", sounddevice=fake)
    io.open()
    assert fake.inputs[0].kwargs["device"] == "Test Mic"
    assert fake.inputs[0].kwargs["samplerate"] == SR

    in_cb = fake.inputs[0].kwargs["callback"]
    in_cb(np.ones((480, 1), dtype=np.float32), 480, None, None)
    block = io.read(timeout=0.5)
    assert block is not None and block.size == 480

    io.play(np.full(10, 0.5, dtype=np.float32))
    out_cb = fake.outputs[0].kwargs["callback"]
    outdata = np.zeros((16, 1), dtype=np.float32)
    out_cb(outdata, 16, None, None)
    assert np.allclose(outdata[:10, 0], 0.5)
    assert np.allclose(outdata[10:, 0], 0.0), "underrun pads with silence"
    io.close()


def test_talk_runs_the_loop_through_audio_io_end_to_end(echo_server):
    """Integration: fake audio devices feed mic blocks, the echo server answers, playback receives audio."""
    fake = _FakeSoundDevice()
    io = SoundDeviceIO(sample_rate=SR, sounddevice=fake)

    from hive_planner.voice_moshi import talk

    feeder_stop = threading.Event()

    def feed_mic_forever():
        in_cb = None
        while not feeder_stop.is_set():
            if fake.inputs and in_cb is None:
                in_cb = fake.inputs[0].kwargs["callback"]
            if in_cb is not None:
                in_cb(_sine(SR // 10).reshape(-1, 1), SR // 10, None, None)
            time.sleep(0.02)

    feeder = threading.Thread(target=feed_mic_forever, daemon=True)
    feeder.start()
    try:
        result = talk(echo_server, io, duration_s=2.5, timeout=3.0)
    finally:
        feeder_stop.set()
        feeder.join(timeout=2)

    assert result["error"] == ""
    assert result["sent_frames"] > 0
    assert result["audio_out_samples"] > 0, "model audio must reach the playback buffer"
    assert result["transcript"][:1] == ["heard you"]
    assert fake.inputs[0].started is False and fake.outputs[0].started is False, "devices closed"


def test_talk_with_dead_server_refuses_before_opening_audio_devices():
    from hive_planner.voice_moshi import talk

    fake = _FakeSoundDevice()
    io = SoundDeviceIO(sample_rate=SR, sounddevice=fake)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with pytest.raises(VoiceBotError, match="moshi_unreachable"):
        talk(f"ws://127.0.0.1:{port}/api/chat", io, duration_s=1.0, timeout=1.0)
    assert fake.inputs == [] and fake.outputs == [], "no mic or speaker opened without a handshake"


def test_sounddevice_io_refuses_when_audio_cannot_open():
    class _Broken(_FakeSoundDevice):
        def InputStream(self, **kwargs):  # noqa: N802
            raise OSError("no such device")

    io = SoundDeviceIO(sample_rate=SR, device="Missing", sounddevice=_Broken())
    with pytest.raises(VoiceBotError, match="moshi_audio_unavailable"):
        io.open()

# --- T056 speech-to-task: utterance capture (R36) -------------------------------------------

from hive_planner.voice_moshi import (  # noqa: E402 - appended block keeps the imports above intact
    ECHO_MUTE_S,
    UtteranceSegmenter,
    pcm_to_wav_bytes,
    run_conversation as _run_conversation,
)


def _tone(seconds: float) -> np.ndarray:
    return _sine(int(seconds * SR))


def _quiet(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SR), dtype=np.float32)


def test_segmenter_cuts_one_utterance_at_the_end_of_speech():
    seg = UtteranceSegmenter(SR)
    out = []
    for chunk in (_tone(0.6), _quiet(1.0)):
        out.extend(seg.push(chunk))
    assert len(out) == 1
    # Speech (0.6 s) plus the trailing quiet block that ended it. Quiet is kept whole, so length is
    # speech + one quiet chunk; it is bounded, not trimmed (harmless for transcription).
    assert 0.6 < out[0].size / SR <= 1.6 + 1e-6


def test_segmenter_drops_a_click_shorter_than_min_speech():
    seg = UtteranceSegmenter(SR)
    out = []
    for chunk in (_tone(0.1), _quiet(1.0)):
        out.extend(seg.push(chunk))
    assert out == []


def test_segmenter_cuts_a_run_longer_than_max():
    seg = UtteranceSegmenter(SR, max_s=1.0)
    out = []
    for _ in range(3):
        out.extend(seg.push(_tone(0.5)))
    assert len(out) >= 1, "a long monologue is cut at the cap"


def test_pcm_to_wav_bytes_round_trips_rate_and_length(tmp_path):
    import io
    import wave

    wav = pcm_to_wav_bytes(_tone(0.5), SR)
    with wave.open(io.BytesIO(wav), "rb") as reader:
        assert reader.getframerate() == SR
        assert reader.getnchannels() == 1
        assert reader.getsampwidth() == 2
        assert reader.getnframes() == int(0.5 * SR)


def test_model_text_never_creates_an_utterance():
    fired: list[int] = []
    conv = MoshiConversation(_FakeSession(), on_utterance=lambda pcm, sr: fired.append(sr))
    conv.handle_frame(KIND_TEXT, b"create a file named hello dot py")
    assert fired == []
    assert conv.utterances == 0


def test_mic_is_ignored_for_utterances_while_model_audio_plays():
    import time as _time

    fired: list[int] = []
    conv = MoshiConversation(_FakeSession(), on_utterance=lambda pcm, sr: fired.append(sr))
    conv._mute_until = _time.monotonic() + ECHO_MUTE_S + 5.0  # as if model audio just arrived
    conv._segment(_tone(0.6))
    conv._segment(_quiet(1.0))
    assert fired == [], "speaker bleed must not become a user task"


def test_loopback_speech_in_gives_one_utterance_per_spoken_phrase():
    def handler(ws):
        ws.send(bytes([KIND_HANDSHAKE]))
        for _msg in ws:
            pass

    server, thread, url = _serve(handler)
    utterances: list[tuple[int, int]] = []
    script = [_tone(1.0), _quiet(1.2), _tone(1.0), _quiet(1.2)]
    try:
        stop = threading.Event()

        def mic_read(timeout: float):
            if not script:
                stop.set()
                return None
            return script.pop(0)

        result = _run_conversation(
            url,
            mic_read=mic_read,
            speaker=lambda pcm: None,
            stop=stop,
            timeout=3.0,
            on_utterance=lambda pcm, sr: utterances.append((int(np.asarray(pcm).size), sr)),
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
    assert result["error"] == ""
    assert result["utterances"] == 2
    assert len(utterances) == 2
    assert all(sr == SR for _size, sr in utterances)


class _ScriptedIO:
    """Fake mic and speaker for `talk()`: mic blocks come from a script, model audio is recorded."""

    def __init__(self, script: list[np.ndarray]) -> None:
        self._script = list(script)
        self.played: list[np.ndarray] = []

    def open(self) -> None:
        return None

    def read(self, timeout: float):
        time.sleep(0.02)
        return self._script.pop(0) if self._script else None

    def play(self, pcm) -> None:
        self.played.append(np.asarray(pcm, dtype=np.float32))

    def close(self) -> None:
        return None


def test_cli_moshi_talk_counts_user_utterances(tmp_path, monkeypatch, capsys):
    """T056: `voice-bot moshi-talk` must pass `on_utterance`, so `utterances` counts real speech."""
    import json

    from hive_planner import voice_moshi
    from hive_planner.cli import main

    def handler(ws):
        ws.send(bytes([KIND_HANDSHAKE]))
        for _msg in ws:
            pass

    server, thread, url = _serve(handler)
    script = [_tone(1.0), _quiet(1.2), _tone(1.0), _quiet(1.2)]
    fake = _ScriptedIO(script)
    monkeypatch.setattr(voice_moshi, "SoundDeviceIO", lambda *a, **k: fake)
    (tmp_path / "START_HERE.md").write_text("# repo\n", encoding="utf-8")
    try:
        code = main(["--root", str(tmp_path), "voice-bot", "moshi-talk", "--url", url, "--duration", "3", "--timeout", "3"])
    finally:
        server.shutdown()
        thread.join(timeout=5)

    out = capsys.readouterr().out
    payload = json.loads(out[out.index("{") :])
    assert code == 0
    assert payload["error"] == ""
    assert payload["sent_frames"] > 0
    assert payload["utterances"] == 2, "two spoken phrases must count as two utterances, not 0"

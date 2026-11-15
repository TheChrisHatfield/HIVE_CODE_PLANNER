"""T049-T055 / R36-R37: Moshi primary voice layer adapter.

HIVE connects to a Moshi server over websocket. It never imports the model and never downloads
weights. For a loopback URL with `moshi_autostart`, the listen gate starts the server process
through voice_moshi_server (OD-1 revised 2026-11-14). Wire kinds are the first byte of
each binary frame: client sends `0x01` + Opus (mic audio); server sends `0x00` (handshake),
`0x01` + Opus (model audio), `0x02` + UTF-8 (model text). Only the handshake and audio/text
frames are read; any other kind is ignored, never executed (R23).

Moshi text is never evidence (R36). `speak()` delegates HIVE text to the speech-out adapter
(OD-2). Moshi transcription stays untrusted until a WER row exists, so `transcribe` is refused.
While one R6 approval is pending, `0x02` text may be routed to that request (`on_text` / tool-broker
`reply`). It is never a new task.
"""

from __future__ import annotations

import importlib.util
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from hive_planner.voice_bot import (
    MOSHI_DEFAULT_URL,
    VoiceAdapter,
    VoiceBotError,
    evidence_register_path,
)
from hive_planner.voice_moshi_server import SERVER, q8_server_command

KIND_HANDSHAKE = 0x00
KIND_AUDIO = 0x01
KIND_TEXT = 0x02

CONNECT_TIMEOUT_S = 15.0  # 2026-11-15: local q8 handshake measured 4.9 s; 3 s refused a healthy server
PROBE_FRAMES = 25  # ~2 s of silence at 24 kHz / 1920-sample frames (Moshi's frame size)
PROBE_FRAME_SAMPLES = 1920
PROBE_SAMPLE_RATE = 24_000

# Utterance capture (T056 speech-to-task). Moshi does not return the user's words, so HIVE cuts the
# mic into utterances and sends each one through the pinned STT route (R36, labeled hybrid path).
UTTERANCE_RMS = 0.012  # float32 RMS above this counts as speech (about -38 dBFS)
UTTERANCE_END_SILENCE_S = 0.8  # this much quiet ends an utterance
UTTERANCE_MIN_SPEECH_S = 0.4  # shorter bursts are coughs or clicks, dropped
UTTERANCE_MAX_S = 20.0  # hard cap so a long monologue is still cut
ECHO_MUTE_S = 0.6  # mic is ignored this long after model audio, so the speaker does not loop back

MOSHI_SPOKEN = {
    "moshi_unavailable": "Moshi is not installed. Type the instruction.",
    "moshi_unreachable": "Moshi is not reachable. Type the instruction.",
    "moshi_server_exited": "The Moshi server stopped while starting. Type the instruction.",
    "moshi_server_timeout": "The Moshi server did not become ready in time. Type the instruction.",
}


def moshi_installed() -> bool:
    """True when the optional `moshi` package is importable (no model is loaded)."""
    return importlib.util.find_spec("moshi") is not None


class MoshiSession:
    """One open, handshaken websocket to a Moshi server."""

    def __init__(self, ws: Any) -> None:
        self._ws = ws
        self.closed = False

    def send_audio(self, opus: bytes) -> None:
        from websockets.exceptions import ConnectionClosed

        if not opus:
            return
        try:
            self._ws.send(bytes([KIND_AUDIO]) + bytes(opus))
        except ConnectionClosed as exc:
            raise VoiceBotError("moshi_unreachable") from exc

    def recv_frame(self, timeout: float) -> tuple[int, bytes] | None:
        """Next (kind, payload) or None on timeout. Non-binary or empty frames are skipped."""
        from websockets.exceptions import ConnectionClosed

        if self.closed:
            return None
        try:
            msg = self._ws.recv(timeout=timeout)
        except TimeoutError:
            return None
        except ConnectionClosed as exc:
            raise VoiceBotError("moshi_unreachable") from exc
        if not isinstance(msg, bytes) or not msg:
            return None
        return msg[0], msg[1:]

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            try:
                self._ws.close()
            except Exception:  # noqa: BLE001 - closing a dead socket must not raise
                pass


HOLD_MAX_AGE_S = 30.0  # R37: a held handshake older than this is closed, not reused
_HOLD_LOCK = threading.Lock()
_HELD: tuple[str, MoshiSession, float] | None = None  # one slot: (url, session, made_at)


def _peek_fresh(url: str) -> bool:
    with _HOLD_LOCK:
        held = _HELD
    return (
        held is not None
        and held[0] == url
        and not held[1].closed
        and time.monotonic() - held[2] <= HOLD_MAX_AGE_S
    )


def _pop_held(url: str) -> MoshiSession | None:
    """Take the held socket for `url` (R37 handover). A stale or other-URL hold is closed."""
    global _HELD
    with _HOLD_LOCK:
        held, _HELD = _HELD, None
    if held is None:
        return None
    held_url, session, made_at = held
    if held_url == url and not session.closed and time.monotonic() - made_at <= HOLD_MAX_AGE_S:
        return session
    session.close()
    return None


def open_session(url: str = MOSHI_DEFAULT_URL, timeout: float = CONNECT_TIMEOUT_S) -> MoshiSession:
    """Connect and wait for the `0x00` handshake. Raises VoiceBotError (never a silent success).

    If the call gate just handshook this URL and kept the socket (`moshi_call_gate`), that same
    socket is returned instead of a second connect, which the q8 server refuses back to back.
    """
    held = _pop_held(url)
    if held is not None:
        return held
    if not moshi_installed():
        raise VoiceBotError("moshi_unavailable")
    try:
        from websockets.exceptions import WebSocketException
        from websockets.sync.client import connect
    except ImportError as exc:
        raise VoiceBotError("moshi_unavailable") from exc
    try:
        ws = connect(url, open_timeout=timeout, close_timeout=1)
    except (OSError, TimeoutError, WebSocketException, ValueError) as exc:
        raise VoiceBotError("moshi_unreachable") from exc
    try:
        first = ws.recv(timeout=timeout)
    except (TimeoutError, OSError, WebSocketException) as exc:
        ws.close()
        raise VoiceBotError("moshi_unreachable") from exc
    if not isinstance(first, bytes) or first[:1] != bytes([KIND_HANDSHAKE]):
        ws.close()
        raise VoiceBotError("moshi_unreachable")
    return MoshiSession(ws)


def _probe_code(url: str) -> str | None:
    """None when a handshake arrives at `url`; else the refusal code. Never raises."""
    try:
        session = open_session(url)
    except VoiceBotError as exc:
        return str(exc) or "moshi_unreachable"
    session.close()
    return None


def _probe_hold(url: str) -> str | None:
    """Like `_probe_code`, but a successful handshake stays open in the one-slot holder (R37)."""
    global _HELD
    if _peek_fresh(url):
        return None
    leftover = _pop_held(url)  # closes a stale hold before a new connect
    if leftover is not None:
        leftover.close()
    try:
        session = open_session(url)
    except VoiceBotError as exc:
        return str(exc) or "moshi_unreachable"
    with _HOLD_LOCK:
        _HELD = (url, session, time.monotonic())
    return None


def _listen_gate(config: Any, hold: bool) -> str | None:
    if config is None or getattr(config, "voice_layer", "typed") != "moshi":
        return None
    probe = _probe_hold if hold else _probe_code
    code = probe(config.moshi_url)
    if code == "moshi_unreachable" and getattr(config, "moshi_autostart", False):
        launch = None
        if getattr(config, "moshi_q8_weights", None):
            launch = lambda u: q8_server_command(u, config)  # noqa: E731 - A3c q8 override
        return SERVER.ensure(config.moshi_url, lambda u: probe(u) is None, launch)
    return code


def moshi_listen_gate(config: Any) -> str | None:
    """T053: None when the spoken listen layer may run; else the refusal code.

    Only `voice_layer == "moshi"` is gated. `typed` and absent configs return None.
    With `moshi_autostart` (default on) and a loopback URL, a missing handshake starts the
    Moshi server through `SERVER` (voice_moshi_server) and waits for it. Package-missing is
    never auto-fixed here; that stays `moshi_unavailable`. This gate closes its probe socket.
    """
    return _listen_gate(config, hold=False)


def moshi_call_gate(config: Any) -> str | None:
    """Same refusal rules as `moshi_listen_gate`, but a passing handshake is kept open.

    The next `open_session` for the same URL (the call's `talk()`) takes that socket, so one
    call makes one connection (R37 handover). Use only where a call follows immediately.
    """
    return _listen_gate(config, hold=True)


class MoshiVoiceAdapter(VoiceAdapter):
    """Listen and converse through Moshi; speak HIVE text through the speech-out adapter (OD-2)."""

    name = "moshi"
    cancel_on_interruption = False

    def __init__(self, speech_out: VoiceAdapter, url: str = MOSHI_DEFAULT_URL) -> None:
        self.speech_out = speech_out
        self.url = url

    def transcribe(self, audio: bytes) -> str:
        # R36: Moshi transcription is untrusted until a WER row is recorded. Use the pinned STT path.
        raise VoiceBotError("stt_unavailable")

    def connect(self, timeout: float = CONNECT_TIMEOUT_S) -> MoshiSession:
        return open_session(self.url, timeout)

    def speak(self, text: str) -> dict[str, Any]:
        payload = dict(self.speech_out.speak(text))
        payload["voice_layer"] = "moshi"
        return payload


def moshi_live_probe(
    url: str = MOSHI_DEFAULT_URL,
    *,
    timeout: float = 30.0,
    frames: int = PROBE_FRAMES,
    model_repo: str = "",
) -> dict[str, Any]:
    """T055 G7 probe: handshake, then one audio round trip. Only this probe may write G7 pass.

    Round trip = at least one `0x01` audio or `0x02` text frame after sending silence frames.
    Unreachable or unavailable server is `blocked` (not a failure of the model).
    """
    result: dict[str, Any] = {
        "g7": "blocked",
        "url": url,
        "model_repo": model_repo,
        "moshi_package_installed": moshi_installed(),
        "handshake_ms": None,
        "audio_frames": 0,
        "text_frames": 0,
        "reason": "",
    }
    try:
        started = time.monotonic()
        session = open_session(url, timeout=CONNECT_TIMEOUT_S)
    except VoiceBotError as exc:
        result["reason"] = str(exc)
        return result
    try:
        result["handshake_ms"] = round((time.monotonic() - started) * 1000, 1)
        try:
            import numpy as np
            import sphn
        except ImportError as exc:
            result["g7"] = "blocked"
            result["reason"] = f"probe_dependency_missing:{exc.name}"
            return result
        writer = sphn.OpusStreamWriter(PROBE_SAMPLE_RATE)
        silence = np.zeros(PROBE_FRAME_SAMPLES, dtype=np.float32)
        for _ in range(frames):
            session.send_audio(writer.append_pcm(silence))
            time.sleep(PROBE_FRAME_SAMPLES / PROBE_SAMPLE_RATE)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            frame = session.recv_frame(timeout=max(0.1, deadline - time.monotonic()))
            if frame is None:
                continue
            kind, _payload = frame
            if kind == KIND_AUDIO:
                result["audio_frames"] += 1
            elif kind == KIND_TEXT:
                result["text_frames"] += 1
            if result["audio_frames"] or result["text_frames"]:
                break
        if result["audio_frames"] or result["text_frames"]:
            result["g7"] = "pass"
            result["reason"] = "handshake_and_round_trip"
        else:
            result["g7"] = "fail"
            result["reason"] = "no_round_trip"
        return result
    except VoiceBotError as exc:
        result["g7"] = "fail"
        result["reason"] = str(exc)
        return result
    finally:
        session.close()


class UtteranceSegmenter:
    """Energy-based endpointing: turns a mic stream into utterance PCM blocks.

    An utterance starts at the first chunk above `rms_threshold` and ends after `end_silence_s` of
    quiet. Bursts shorter than `min_speech_s` are dropped; a run longer than `max_s` is cut.
    Plain RMS is enough for a push-to-talk style call; it is not a trained VAD.
    """

    def __init__(
        self,
        sample_rate: int,
        *,
        rms_threshold: float = UTTERANCE_RMS,
        end_silence_s: float = UTTERANCE_END_SILENCE_S,
        min_speech_s: float = UTTERANCE_MIN_SPEECH_S,
        max_s: float = UTTERANCE_MAX_S,
    ) -> None:
        import numpy as np

        self._np = np
        self._sr = int(sample_rate)
        self._rms = float(rms_threshold)
        self._end_silence = int(end_silence_s * self._sr)
        self._min_speech = int(min_speech_s * self._sr)
        self._max = int(max_s * self._sr)
        self.reset()

    def reset(self) -> None:
        self._chunks: list[Any] = []
        self._total = 0
        self._speech = 0
        self._quiet = 0
        self._in_speech = False

    def push(self, chunk: Any) -> list[Any]:
        """Feed mic PCM. Returns the utterances (float32 arrays) that completed with this chunk."""
        np = self._np
        x = np.asarray(chunk, dtype=np.float32).reshape(-1)
        if x.size == 0:
            return []
        loud = float(np.sqrt(np.mean(x * x))) >= self._rms
        finished: list[Any] = []
        if loud:
            self._in_speech = True
            self._quiet = 0
            self._speech += x.size
            self._chunks.append(x)
            self._total += x.size
        elif self._in_speech:
            self._quiet += x.size
            self._chunks.append(x)
            self._total += x.size
            if self._quiet >= self._end_silence:
                finished.append(self._finish())
        if self._in_speech and self._total >= self._max:
            finished.append(self._finish())
        return [utt for utt in finished if utt is not None]

    def _finish(self) -> Any:
        pcm = self._np.concatenate(self._chunks) if self._chunks else self._np.zeros(0, dtype=self._np.float32)
        keep = self._speech >= self._min_speech
        self.reset()
        return pcm if keep else None


def pcm_to_wav_bytes(pcm: Any, sample_rate: int) -> bytes:
    """Float32 mono PCM to 16-bit PCM WAV bytes (what the spoken submit route stores and decodes)."""
    import io
    import wave

    import numpy as np

    clipped = np.clip(np.asarray(pcm, dtype=np.float32).reshape(-1), -1.0, 1.0)
    data = (clipped * 32767.0).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(int(sample_rate))
        writer.writeframes(data)
    return buf.getvalue()


class MoshiConversation:
    """T056: duplex conversation over one open session (mic out, model audio in, model text in).

    - Mic PCM (float32 mono at `sample_rate`) is re-framed into `frame_samples` blocks, Opus-encoded,
      and sent as `0x01` frames.
    - Model `0x01` frames are Opus-decoded to PCM for playback.
    - Model `0x02` text is appended to `transcript`. It is never evidence and never creates a
      task (R36). If `on_text` returns true, the frame was an approval reply. Else a pending
      Moshi tool-lane approval uses `tool_broker.reply`; otherwise `tool_broker.offer` may parse
      a `TOOL:` line. Routing Moshi text as a new instruction still needs a recorded WER row.
    The encoder is used only by the sending side and the decoder only by the receiving side, so
    the two threads never share sphn state.
    """

    def __init__(
        self,
        session: MoshiSession,
        *,
        sample_rate: int = PROBE_SAMPLE_RATE,
        frame_samples: int = PROBE_FRAME_SAMPLES,
        tool_broker: Any | None = None,
        on_text: Callable[[str], Any] | None = None,
        on_utterance: Callable[[Any, int], Any] | None = None,
    ) -> None:
        import numpy as np
        import sphn

        self._np = np
        self._session = session
        self._tool_broker = tool_broker  # ML-T4: text lines become proposals only; never audio
        self._on_text = on_text  # Voice_Bot R36: pending approval reply; never a new task
        # T056 speech-to-task: each finished user utterance (PCM, sample rate) goes to the caller,
        # which sends it through the pinned STT route. Moshi text is never used for this.
        self._on_utterance = on_utterance
        self._segmenter = UtteranceSegmenter(sample_rate) if on_utterance is not None else None
        self._sample_rate = sample_rate
        self._mute_until = 0.0  # monotonic time; mic is ignored for segmentation until then
        self.utterances = 0
        self._frame = frame_samples
        self._writer = sphn.OpusStreamWriter(sample_rate)
        self._reader = sphn.OpusStreamReader(sample_rate)
        self._pending = np.zeros(0, dtype=np.float32)
        self.sent_frames = 0
        self.audio_out_samples = 0
        self.transcript: list[str] = []
        self.tool_results: list[dict[str, Any]] = []

    def _segment(self, chunk: Any) -> None:
        if self._segmenter is None:
            return
        if time.monotonic() < self._mute_until:
            # Model audio is playing; the mic mostly hears the speaker. Drop any half utterance.
            self._segmenter.reset()
            return
        for utterance in self._segmenter.push(chunk):
            self.utterances += 1
            try:
                self._on_utterance(utterance, self._sample_rate)
            except Exception:  # noqa: BLE001 - a failed submit must not drop the live call
                pass

    def feed_mic(self, chunk: Any) -> int:
        """Queue mic PCM and send every complete frame. Returns the number of frames sent."""
        np = self._np
        self._segment(chunk)
        self._pending = np.concatenate([self._pending, np.asarray(chunk, dtype=np.float32).reshape(-1)])
        sent = 0
        while self._pending.size >= self._frame:
            frame, self._pending = self._pending[: self._frame], self._pending[self._frame :]
            packet = self._writer.append_pcm(frame)
            if packet:
                self._session.send_audio(bytes(packet))
                sent += 1
        self.sent_frames += sent
        return sent

    def handle_frame(self, kind: int, payload: bytes) -> Any:
        """Process one server frame. Returns decoded PCM for `0x01`, else None (text or ignored kind)."""
        if kind == KIND_AUDIO:
            self._mute_until = time.monotonic() + ECHO_MUTE_S
            pcm = self._np.asarray(self._reader.append_bytes(bytes(payload)), dtype=self._np.float32).reshape(-1)
            self.audio_out_samples += int(pcm.size)
            return pcm if pcm.size else None
        if kind == KIND_TEXT:
            text = bytes(payload).decode("utf-8", errors="replace").strip()
            if text:
                self.transcript.append(text)
                consumed = False
                if self._on_text is not None:
                    try:
                        consumed = bool(self._on_text(text))
                    except Exception:  # noqa: BLE001 - approval routing must not drop the call
                        consumed = False
                if not consumed and self._tool_broker is not None:
                    if self._tool_broker.pending is not None:
                        self.tool_results.append(self._tool_broker.reply(text))
                    else:
                        row = self._tool_broker.offer(text)
                        if row.get("reason") != "no_tool_line":
                            self.tool_results.append(row)
        return None


def run_conversation(
    url: str,
    *,
    mic_read: Callable[[float], Any],
    speaker: Callable[[Any], None],
    stop: threading.Event,
    timeout: float = CONNECT_TIMEOUT_S,
    sample_rate: int = PROBE_SAMPLE_RATE,
    frame_samples: int = PROBE_FRAME_SAMPLES,
    session: MoshiSession | None = None,
    on_text: Callable[[str], Any] | None = None,
    tool_broker: Any | None = None,
    on_utterance: Callable[[Any, int], Any] | None = None,
) -> dict[str, Any]:
    """Run one full-duplex conversation until `stop` is set or the socket drops.

    `mic_read(timeout)` returns a PCM chunk or None. `speaker(pcm)` plays decoded model audio.
    Raises VoiceBotError only when the handshake fails. A later drop is reported in `error`.
    A caller may pass an already-handshaken `session`; it is closed when this returns.
    `on_text` sees each `0x02` line (approval routing). `tool_broker` is the Moshi tool lane.
    `on_utterance(pcm, sample_rate)` gets each finished user utterance (speech-to-task, T056).
    """
    if session is None:
        session = open_session(url, timeout=timeout)
    conv = MoshiConversation(
        session,
        sample_rate=sample_rate,
        frame_samples=frame_samples,
        on_text=on_text,
        tool_broker=tool_broker,
        on_utterance=on_utterance,
    )
    state: dict[str, Any] = {"error": "", "speaker_errors": 0}

    def _receive() -> None:
        while not stop.is_set():
            try:
                frame = session.recv_frame(timeout=0.2)
            except VoiceBotError as exc:
                # A close during our own shutdown is expected; only a drop mid-call is an error.
                if not stop.is_set():
                    state["error"] = str(exc)
                stop.set()
                return
            if frame is None:
                continue
            pcm = conv.handle_frame(*frame)
            if pcm is not None:
                try:
                    speaker(pcm)
                except Exception:  # noqa: BLE001 - a playback fault must not drop the conversation
                    state["speaker_errors"] += 1

    receiver = threading.Thread(target=_receive, name="moshi-recv", daemon=True)
    receiver.start()
    try:
        while not stop.is_set():
            chunk = mic_read(0.2)
            if chunk is not None:
                try:
                    conv.feed_mic(chunk)
                except VoiceBotError as exc:
                    if not stop.is_set():
                        state["error"] = str(exc)
                    stop.set()
    finally:
        stop.set()
        session.close()
        receiver.join(timeout=2.0)
    return {
        "sent_frames": conv.sent_frames,
        "utterances": conv.utterances,
        "audio_out_samples": conv.audio_out_samples,
        "text_frames": len(conv.transcript),
        "transcript": list(conv.transcript),
        "speaker_errors": state["speaker_errors"],
        "error": state["error"],
    }


class SoundDeviceIO:
    """Mic and speaker for `run_conversation` through `sounddevice` (lazy import, voice extra).

    Mic blocks go into a queue (`read`). Model audio goes into a buffer that the output callback
    drains, so playback never blocks the receive thread.
    """

    def __init__(self, sample_rate: int = PROBE_SAMPLE_RATE, device: str | None = None, *, sounddevice: Any = None):
        self._sr = sample_rate
        self._device = device
        self._sd = sounddevice
        self._mic: Any = None
        self._out: Any = None
        self._queue: Any = None
        self._buffer: Any = None
        self._lock = threading.Lock()

    def open(self) -> None:
        import queue

        import numpy as np

        sd = self._sd
        if sd is None:
            try:
                import sounddevice as sd  # noqa: PLC0415 - lazy so the module imports without audio hardware
            except (ImportError, OSError) as exc:
                raise VoiceBotError("moshi_audio_unavailable") from exc
        self._np = np
        self._queue = queue.Queue(maxsize=200)
        self._buffer = np.zeros(0, dtype=np.float32)

        def _in(indata: Any, _frames: int, _time: Any, _status: Any) -> None:
            try:
                self._queue.put_nowait(np.asarray(indata, dtype=np.float32).reshape(-1).copy())
            except queue.Full:
                pass  # dropping mic blocks under load beats stalling the audio callback

        def _out(outdata: Any, frames: int, _time: Any, _status: Any) -> None:
            with self._lock:
                take, self._buffer = self._buffer[:frames], self._buffer[frames:]
            outdata[:, 0] = 0.0
            outdata[: take.size, 0] = take

        try:
            self._mic = sd.InputStream(
                samplerate=self._sr, channels=1, dtype="float32", device=self._device, callback=_in
            )
            self._out = sd.OutputStream(samplerate=self._sr, channels=1, dtype="float32", callback=_out)
            self._mic.start()
            self._out.start()
        except Exception as exc:  # PortAudioError, bad device name, unsupported sample rate
            self.close()
            raise VoiceBotError(f"moshi_audio_unavailable: {exc}") from exc

    def read(self, timeout: float) -> Any:
        import queue

        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def play(self, pcm: Any) -> None:
        with self._lock:
            self._buffer = self._np.concatenate([self._buffer, self._np.asarray(pcm, dtype=self._np.float32)])

    def close(self) -> None:
        for stream in (self._mic, self._out):
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:  # noqa: BLE001 - closing an already-failed stream must not raise
                    pass
        self._mic = self._out = None


def count_utterance_only(pcm: Any, sample_rate: int) -> None:
    """`on_utterance` sink for the `moshi-talk` CLI: the utterance is counted, then dropped.

    Speech-to-task runs on the panel path. The CLI only needs the segmenter running so that
    `utterances` reports real user speech instead of always 0 (T056 evidence).
    """
    return None


def talk(
    url: str,
    io: Any,
    *,
    stop: threading.Event | None = None,
    duration_s: float = 0.0,
    timeout: float = CONNECT_TIMEOUT_S,
    on_text: Callable[[str], Any] | None = None,
    tool_broker: Any | None = None,
    on_utterance: Callable[[Any, int], Any] | None = None,
) -> dict[str, Any]:
    """Open the audio devices, run one conversation, then close the devices.

    `io` has `open()`, `read(timeout)`, `play(pcm)`, and `close()` (see `SoundDeviceIO`). `duration_s`
    of 0 talks until `stop` is set (Ctrl+C in the CLI). Device faults raise VoiceBotError.
    `on_text` is forwarded to the conversation (pending R6 approval replies). `on_utterance` is
    forwarded too (speech-to-task).
    """
    stop = stop or threading.Event()
    timer: threading.Timer | None = None
    # Handshake first: a dead server must not grab the microphone or speaker.
    session = open_session(url, timeout=timeout)
    try:
        io.open()
    except VoiceBotError:
        session.close()
        raise
    try:
        if duration_s and duration_s > 0:
            timer = threading.Timer(duration_s, stop.set)
            timer.daemon = True
            timer.start()
        return run_conversation(
            url,
            mic_read=io.read,
            speaker=io.play,
            stop=stop,
            timeout=timeout,
            session=session,
            on_text=on_text,
            tool_broker=tool_broker,
            on_utterance=on_utterance,
        )
    finally:
        if timer is not None:
            timer.cancel()
        io.close()


def apply_gate_row(text: str, gate: str, result: str, date: str, note: str) -> str:
    """Set the result, date, and note cells of one gate row in the evidence register."""
    if result not in ("pass", "fail", "blocked"):
        raise VoiceBotError(f"invalid {gate} result {result}")
    lines: list[str] = []
    prefix = f"| {gate} |"
    for line in text.splitlines(keepends=True):
        if line.startswith(prefix):
            cells = line.rstrip("\n").split("|")
            if len(cells) >= 8:
                cells[5] = f" **{result}** "
                cells[6] = f" {date} "
                cells[7] = f" {note.replace('|', '/')} "
                line = "|".join(cells) + "\n"
        lines.append(line)
    return "".join(lines)


def record_g7_evidence(paths: Any, result: str, note: str) -> Path:
    """Write the G7 row. Called only by the live probe path with a real handshake result."""
    from datetime import datetime, timezone

    path = evidence_register_path(paths)
    if not path.is_file():
        raise VoiceBotError(f"evidence register missing: {path}")
    date = datetime.now(timezone.utc).date().isoformat()
    updated = apply_gate_row(path.read_text(encoding="utf-8"), "G7", result, date, note)
    path.write_text(updated, encoding="utf-8")
    return path

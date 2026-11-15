"""Real microphone recorder for the launcher Voice panel (T042 slice 5d).

Contract with `voice_panel_controller.VoicePanelController`:
- `start()` opens the input device and begins capture. Raises OSError when capture cannot start.
- `stop()` ends capture and returns WAV bytes (16 kHz, mono, 16-bit PCM).

`sounddevice` is imported lazily, so the launcher still starts when it is not installed.
Declared under the `voice` extra in pyproject.toml.
"""

from __future__ import annotations

import io
import threading
import wave
from collections.abc import Callable
from typing import Any

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH_BYTES = 2  # int16


class WavMicRecorder:
    """Records one utterance from the configured input device into memory as WAV bytes."""

    def __init__(self, device_getter: Callable[[], str | None] | None = None, *, sounddevice: Any = None) -> None:
        # device_getter returns the saved `input_device` name, or None for the system default.
        self._device_getter = device_getter or (lambda: None)
        self._sd = sounddevice  # injectable for tests; None means import on start
        self._stream: Any = None
        self._chunks: list[bytes] = []
        self._lock = threading.Lock()

    def _load_sounddevice(self) -> Any:
        if self._sd is not None:
            return self._sd
        try:
            import sounddevice  # noqa: PLC0415 - lazy so a missing optional dep does not break the launcher
        except (ImportError, OSError) as exc:
            raise OSError(f"sounddevice is not installed ({exc}). Install the voice extra.") from exc
        return sounddevice

    def start(self) -> None:
        if self._stream is not None:
            return
        sd = self._load_sounddevice()
        device = (self._device_getter() or "").strip() or None
        with self._lock:
            self._chunks = []

        def _callback(indata: Any, _frames: int, _time: Any, _status: Any) -> None:
            with self._lock:
                self._chunks.append(bytes(indata))

        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                device=device,
                callback=_callback,
            )
            stream.start()
        except Exception as exc:  # PortAudioError, ValueError for an unknown device name, etc.
            raise OSError(f"could not open microphone {device or 'default'}: {exc}") from exc
        self._stream = stream

    def stop(self) -> bytes:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
        with self._lock:
            pcm = b"".join(self._chunks)
            self._chunks = []
        return _wav_bytes(pcm)


def _wav_bytes(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH_BYTES)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)
    return buf.getvalue()

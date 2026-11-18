"""Local speech-out for Voice_Bot (R32, OD-2): Pipecat TTS service backed by Windows SAPI.

Why this exists: Pipecat 1.12 ships many TTS services, but in this install every one of them
needs a cloud key or model weights. The one voice that works offline on Windows is the built-in
speech synthesizer (System.Speech). `SapiTTSService` is a real Pipecat `TTSService` subclass:
Pipecat's `run_tts` produces the `TTSAudioRawFrame`s, and `speak_via_pipecat` plays them through
`sounddevice`. Nothing here claims audio unless playback started. Any failure is a
`VoiceBotError`, so the caller falls back to the typed no-audio path (no silent failure).

Heavy imports (pipecat, sounddevice, numpy) are lazy so importing this module stays cheap.
"""

from __future__ import annotations

import base64
import io
import os
import subprocess
import sys
import tempfile
import threading
import wave
from pathlib import Path
from typing import Any

from hive_planner.voice_bot import VoiceBotError

SAPI_TIMEOUT_S = 60.0
_CREATE_NO_WINDOW = 0x08000000

# stop_playback bumps this so a later sd.play from an in-flight speak is refused.
_play_gate = threading.Lock()
_play_generation = 0
_expected_generation: int | None = None

# PowerShell reads the text and the output path from environment variables, never from the
# command line, so quotes or newlines in an update cannot change the script.
_SAPI_SCRIPT = r"""
Add-Type -AssemblyName System.Speech
$text = [Environment]::GetEnvironmentVariable('HIVE_TTS_TEXT')
$path = [Environment]::GetEnvironmentVariable('HIVE_TTS_PATH')
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $synth.SetOutputToWaveFile($path)
    $synth.Speak($text)
} finally {
    $synth.Dispose()
}
"""


def synthesize_wav_sapi(text: str) -> bytes:
    """Render `text` to WAV bytes with the Windows speech synthesizer. Raises VoiceBotError."""
    if os.name != "nt":
        raise VoiceBotError("tts_unavailable")
    encoded = base64.b64encode(_SAPI_SCRIPT.encode("utf-16-le")).decode("ascii")
    with tempfile.TemporaryDirectory(prefix="hive-tts-") as tmp:
        out = Path(tmp) / "speech.wav"
        env = {**os.environ, "HIVE_TTS_TEXT": text, "HIVE_TTS_PATH": str(out)}
        kwargs: dict[str, Any] = {"creationflags": _CREATE_NO_WINDOW} if sys.platform == "win32" else {}
        try:
            proc = subprocess.run(
                [
                    "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                    "-EncodedCommand", encoded,
                ],
                env=env,
                capture_output=True,
                timeout=SAPI_TIMEOUT_S,
                check=False,
                **kwargs,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise VoiceBotError("tts_failed") from exc
        if proc.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
            raise VoiceBotError("tts_failed")
        return out.read_bytes()


def wav_to_pcm16_mono(wav_bytes: bytes) -> tuple[bytes, int]:
    """Decode 16-bit PCM WAV to mono int16 little-endian bytes. Stereo is averaged to mono."""
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
            channels = reader.getnchannels()
            width = reader.getsampwidth()
            rate = reader.getframerate()
            frames = reader.readframes(reader.getnframes())
    except (wave.Error, EOFError) as exc:
        raise VoiceBotError("tts_failed") from exc
    if width != 2 or channels < 1 or rate <= 0:
        raise VoiceBotError("tts_failed")
    if channels == 1:
        return frames, rate
    import array

    samples = array.array("h", frames)
    mono = array.array("h", (
        int(sum(samples[i : i + channels]) / channels) for i in range(0, len(samples), channels)
    ))
    return mono.tobytes(), rate


def build_sapi_tts_service() -> Any:
    """Construct the Pipecat TTS service. Imports pipecat lazily (`voice` extra)."""
    try:
        from pipecat.frames.frames import ErrorFrame, TTSAudioRawFrame
        from pipecat.services.tts_service import TTSService
    except ImportError as exc:
        raise VoiceBotError("pipecat_unavailable") from exc

    class SapiTTSService(TTSService):
        """Pipecat TTSService that synthesizes with the Windows speech synthesizer (SAPI)."""

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        async def run_tts(self, text: str, context_id: str):  # noqa: ANN201 - Pipecat async generator
            try:
                pcm, rate = wav_to_pcm16_mono(synthesize_wav_sapi(text))
            except VoiceBotError as exc:
                yield ErrorFrame(error=str(exc))
                return
            yield TTSAudioRawFrame(audio=pcm, sample_rate=rate, num_channels=1, context_id=context_id)

    return SapiTTSService()


async def _collect_audio(service: Any, text: str) -> tuple[bytes, int]:
    """Drive the Pipecat service's run_tts and gather its audio frames."""
    from pipecat.frames.frames import ErrorFrame, TTSAudioRawFrame

    chunks: list[bytes] = []
    rate = 0
    async for frame in service.run_tts(text, "hive-speech"):
        if isinstance(frame, ErrorFrame):
            raise VoiceBotError(str(frame.error or "tts_failed"))
        if isinstance(frame, TTSAudioRawFrame) and frame.audio:
            chunks.append(bytes(frame.audio))
            rate = int(frame.sample_rate)
    if not chunks or rate <= 0:
        raise VoiceBotError("tts_failed")
    return b"".join(chunks), rate


def synthesize_via_pipecat(text: str) -> tuple[bytes, int]:
    """PCM16 mono bytes and sample rate, produced by the Pipecat TTS service."""
    import asyncio

    service = build_sapi_tts_service()
    try:
        return asyncio.run(_collect_audio(service, text))
    except VoiceBotError:
        raise
    except Exception as exc:  # noqa: BLE001 - any Pipecat fault becomes an explicit refusal
        raise VoiceBotError("tts_failed") from exc


def play_pcm16(pcm: bytes, sample_rate: int) -> None:
    """Start playback on the default output device (non-blocking). Raises VoiceBotError."""
    try:
        import numpy as np
        import sounddevice as sd
    except (ImportError, OSError) as exc:
        raise VoiceBotError("tts_playback_failed") from exc
    try:
        data = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        with _play_gate:
            if _expected_generation is not None and _expected_generation != _play_generation:
                raise VoiceBotError("tts_playback_failed")
            sd.play(data, sample_rate)
    except VoiceBotError:
        raise
    except Exception as exc:  # PortAudioError, no output device
        raise VoiceBotError(f"tts_playback_failed: {exc}") from exc


def stop_playback() -> None:
    """Stop any speech still playing (playback interrupt). Never raises.

    Also invalidates in-flight synthesize-then-play so interrupt during SAPI
    does not start audio after the stop (R7).
    """
    global _play_generation
    try:
        import sounddevice as sd

        sd.stop()
    except Exception:  # noqa: BLE001 - nothing playing, or no audio stack: nothing to stop
        pass
    with _play_gate:
        _play_generation += 1


def speak_via_pipecat(text: str) -> dict[str, Any]:
    """Synthesize `text` with Pipecat and play it. Returns the playback record or raises VoiceBotError."""
    global _expected_generation
    with _play_gate:
        generation = _play_generation
        _expected_generation = generation
    try:
        pcm, rate = synthesize_via_pipecat(text)
        play_pcm16(pcm, rate)
        return {"played": True, "sample_rate": rate, "duration_s": round(len(pcm) / 2 / rate, 3)}
    finally:
        with _play_gate:
            if _expected_generation == generation:
                _expected_generation = None

"""Mirror Windows playback to every connected Bluetooth speaker."""

from __future__ import annotations

import json
import queue
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from bluettooth_surround.devices import (
    PlaybackDevice,
    devices_refer_to_same_endpoint,
    filter_devices_by_names,
    list_wasapi_playback_devices,
)
from bluettooth_surround.adaptive_stream import (
    ADAPT_INTERVAL_SEC,
    AdaptiveAlignState,
    AdaptiveRouteController,
    StreamProfile,
    WriterTelemetry,
    compress_payload,
    decompress_payload,
    profile_buffer_min,
    profile_queue_depth,
)
from bluettooth_surround.speech_route import (
    NeuralBanditContext,
    apply_speech_route_to_payload,
)
from bluettooth_surround.calibration import (
    CalibrationProfile,
    load_calibration_for_routing,
    resolve_calibration_file,
)
from bluettooth_surround.spatial_pan import (
    apply_azimuth_pan_to_payload,
    resolve_speaker_azimuths,
)
from bluettooth_surround.content_split import (
    apply_content_split_to_payload,
    apply_level_trim_to_payload,
)
from bluettooth_surround.surround_matrix import (
    apply_surround_matrix_to_payload,
    should_skip_spatial_pan_for_role,
    surround_role_from_azimuth,
)
from bluettooth_surround.neural_upmix import (
    NeuralUpmixEngine,
    delete_overlay_state,
    load_overlay_state,
    resolve_onnx_model_path,
    resolve_overlay_state_path,
    save_overlay_state,
)
from bluettooth_surround.neural_upmix.overlay_presets import normalize_overlay_aggressiveness
from bluettooth_surround.azimuth_ipc import (
    apply_live_azimuth_overrides,
    clear_azimuth_override_file,
    read_azimuth_overrides_by_name,
)


@dataclass
class RouteConfig:
    chunk_frames: int = 1024
    device_indexes: list[int] | None = None
    device_names: list[str] | None = None
    source_loopback_index: int | None = None
    hotplug: bool = True
    hotplug_interval_sec: float = 3.0
    calibration_path: str | None = None
    use_calibration: bool = True
    low_latency: bool = True
    use_spatial_panning: bool = True
    use_content_split: bool = True
    max_surround_separation: bool = True
    neural_upmix: bool = False
    continual_overlay: bool = False
    overlay_aggressiveness: str = "normal"
    onnx_model_path: str | None = None
    onnx_device: str = "auto"
    onnx_device_id: int = 0
    reset_overlay: bool = False
    overlay_persist: bool = True
    overlay_state_path: str | None = None
    overlay_autosave_steps: int = 200
    overlay_autosave_interval_sec: float = 45.0
    use_adaptive_stream: bool = True
    speech_aware_routing: bool = True
    lip_sync: bool = True
    stop_file_path: str | None = None
    azimuth_override_path: str | None = None


STOP_FILE_NAME = "bt-surround.stop"


def resolve_stop_file_path(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / STOP_FILE_NAME
    return Path.cwd() / STOP_FILE_NAME


def request_route_stop(explicit: str | None = None) -> Path:
    path = resolve_stop_file_path(explicit)
    path.write_text("1\n", encoding="utf-8")
    return path


def clear_route_stop(explicit: str | None = None) -> None:
    try:
        resolve_stop_file_path(explicit).unlink(missing_ok=True)
    except OSError:
        pass


def route_stop_requested(explicit: str | None = None) -> bool:
    return resolve_stop_file_path(explicit).is_file()


LOW_LATENCY_QUEUE_CHUNKS = 2
LOW_LATENCY_BUFFER_MIN = 1024
BT_DEVICE_OPEN_DELAY_SEC = 0.25
BT_DEVICE_OPEN_RETRIES = 2
BT_TEST_DEVICE_GAP_SEC = 0.2
STABLE_QUEUE_CHUNKS = 12
STABLE_BUFFER_MIN = 4096
OUTPUT_WRITE_FAILURE_THRESHOLD = 8


def routing_buffer_tuning(config: RouteConfig) -> tuple[int, int]:
    """Return (output_queue_depth, min_output_buffer_frames) for the route profile."""
    if config.low_latency:
        return LOW_LATENCY_QUEUE_CHUNKS, LOW_LATENCY_BUFFER_MIN
    return STABLE_QUEUE_CHUNKS, STABLE_BUFFER_MIN


def estimate_routing_latency_ms(config: RouteConfig, sample_rate: int) -> float:
    """Rough end-to-end latency added by routing buffers (not Bluetooth radio lag)."""
    queue_depth, buffer_min = routing_buffer_tuning(config)
    chunk_ms = config.chunk_frames * 1000.0 / sample_rate
    buffer_ms = max(config.chunk_frames * 2, buffer_min) * 1000.0 / sample_rate
    return chunk_ms + buffer_ms + (queue_depth * chunk_ms * 0.5)


class AsyncOutputWriter:
    """Queue PCM chunks and write to a PyAudio stream on a background thread."""

    def __init__(
        self,
        device_name: str,
        stream: object,
        *,
        max_queued_chunks: int = LOW_LATENCY_QUEUE_CHUNKS,
        write_retries: int = 3,
        failure_threshold: int = OUTPUT_WRITE_FAILURE_THRESHOLD,
        compression: str = "none",
        out_channels: int = 2,
    ) -> None:
        self.device_name = device_name
        self._stream = stream
        self._write_retries = write_retries
        self._failure_threshold = max(1, failure_threshold)
        self._compression = compression
        self._out_channels = out_channels
        self._consecutive_failures = 0
        self._max_queued_chunks = max(1, max_queued_chunks)
        self._queue: queue.Queue[bytes | None] = queue.Queue(maxsize=self._max_queued_chunks)
        self._failed_error: OSError | None = None
        self._stop_event = threading.Event()
        self._telemetry = WriterTelemetry()
        self._thread = threading.Thread(
            target=self._run,
            name=f"bt-output-{device_name}",
            daemon=True,
        )
        self._thread.start()

    @property
    def failed_error(self) -> OSError | None:
        return self._failed_error

    @property
    def telemetry(self) -> WriterTelemetry:
        return self._telemetry

    @property
    def max_queued_chunks(self) -> int:
        return self._max_queued_chunks

    def queued_chunks(self) -> int:
        return self._queue.qsize()

    def wait_until_idle(self, timeout_sec: float = 2.0) -> bool:
        deadline = time.monotonic() + max(0.0, timeout_sec)
        while time.monotonic() < deadline:
            if self._failed_error is not None:
                return False
            if self._queue.empty():
                return True
            time.sleep(0.03)
        return self._queue.empty()

    def submit(self, payload: bytes) -> None:
        if not payload:
            return
        if self._failed_error is not None or self._stop_event.is_set():
            self._telemetry.note_dropped()
            return
        submitted = False
        try:
            self._queue.put_nowait(payload)
            submitted = True
        except queue.Full:
            # Drop the oldest chunk so mirrored speakers stay close to real time.
            try:
                evicted = self._queue.get_nowait()
            except queue.Empty:
                return
            try:
                self._queue.put_nowait(payload)
                submitted = True
                self._telemetry.note_dropped()
            except queue.Full:
                self._telemetry.note_dropped()
                try:
                    self._queue.put_nowait(evicted)
                except queue.Full:
                    self._telemetry.note_dropped()
                return
            dropped = self._telemetry.dropped_chunks
            if dropped in {1, 25, 100}:
                print(
                    f"Output buffer warning: {self.device_name} is falling behind "
                    f"(dropped {dropped} stale chunk(s) to reduce delay).",
                    flush=True,
                )
        if submitted:
            self._telemetry.note_submit()

    def stop(self) -> None:
        self._stop_event.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass
        self._thread.join(timeout=3.0)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                payload = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if payload is None:
                break

            payload = decompress_payload(payload, self._compression, self._out_channels)

            error: OSError | None = None
            while not self._stop_event.is_set():
                error = None
                for attempt in range(self._write_retries):
                    try:
                        self._stream.write(payload)
                        error = None
                        break
                    except OSError as exc:
                        error = exc
                        if attempt + 1 < self._write_retries:
                            time.sleep(0.01)
                if error is None:
                    self._consecutive_failures = 0
                    self._telemetry.note_successful_write()
                    break
                self._telemetry.note_write_failure()
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._failure_threshold:
                    self._failed_error = error
                    return
                time.sleep(0.05)


OutputStream = tuple[
    PlaybackDevice,
    int,
    int,
    object,
    AsyncOutputWriter,
    float,
    StreamProfile,
    AdaptiveAlignState,
]


def output_buffer_frames(chunk_frames: int, buffer_min: int = LOW_LATENCY_BUFFER_MIN) -> int:
    """Pick a WASAPI buffer size that balances latency and Bluetooth stability."""
    return max(chunk_frames * 2, buffer_min)


def loopback_playback_name(loopback_info: dict) -> str:
    """Strip loopback suffix to recover the underlying playback endpoint name."""
    name = str(loopback_info["name"])
    return re.sub(r"\[loopback\]", "", name, flags=re.IGNORECASE).strip()


def exclude_echo_targets(
    targets: list[PlaybackDevice],
    default_output_name: str,
    *,
    quiet: bool = False,
) -> list[PlaybackDevice]:
    """Drop targets that are already playing the captured default output natively."""
    filtered = [
        device
        for device in targets
        if not devices_refer_to_same_endpoint(device.name, default_output_name)
    ]
    if not filtered:
        raise RuntimeError(
            "All Bluetooth targets match the current default playback device. "
            "Set Windows default to one Bluetooth speaker, then run again so "
            "the other speakers can be routed."
        )

    skipped = [device.name for device in targets if device not in filtered]
    if skipped and not quiet:
        print(f"Skipping echo source(s): {', '.join(skipped)}", flush=True)

    return filtered


def targets_not_yet_routed(
    active_devices: list[PlaybackDevice],
    desired_targets: list[PlaybackDevice],
) -> list[PlaybackDevice]:
    """Return desired Bluetooth endpoints that are not already being routed."""
    return [
        device
        for device in desired_targets
        if not any(
            devices_refer_to_same_endpoint(device.name, active.name)
            for active in active_devices
        )
    ]


def routed_devices_no_longer_desired(
    active_devices: list[PlaybackDevice],
    desired_targets: list[PlaybackDevice],
) -> list[PlaybackDevice]:
    """Return active endpoints that disappeared or are no longer selected."""
    return [
        active
        for active in active_devices
        if not any(
            devices_refer_to_same_endpoint(active.name, device.name)
            for device in desired_targets
        )
    ]


def normalize_loopback_chunk(
    raw: bytes,
    capture_channels: int,
) -> np.ndarray:
    """Convert a loopback read into interleaved stereo int16 samples."""
    source = np.frombuffer(raw, dtype=np.int16)
    if capture_channels > 2:
        source = source.reshape(-1, capture_channels)[:, :2].reshape(-1)
    elif capture_channels == 1:
        source = np.repeat(source, 2)
    return source


def build_payload_cache(
    source: np.ndarray,
    capture_rate: int,
    signatures: set[tuple[int, int]],
) -> dict[tuple[int, int], bytes]:
    """Build output payloads once per unique (rate, channels) signature."""
    return {
        signature: prepare_output_payload(source, capture_rate, signature[0], signature[1])
        for signature in signatures
    }


def _routing_health_idle_message(output_streams: list[OutputStream]) -> str:
    if output_streams and all(
        writer.failed_error is not None for _, _, _, _, writer, *_ in output_streams
    ):
        return (
            "Routing health: all mirrored outputs failed — "
            "check Bluetooth volume, pairing, and routing options."
        )
    return "Routing health: waiting for Bluetooth speakers..."


def format_routing_health(
    output_streams: list[OutputStream],
    *,
    adaptive: bool = False,
    capture_max_rms: float | None = None,
    speech_profile_label: str | None = None,
) -> str:
    if not output_streams:
        return _routing_health_idle_message(output_streams)
    if adaptive:
        details = []
        for device, _, _, _, writer, _, profile, align in output_streams:
            if writer.failed_error is not None:
                continue
            capacity = writer.max_queued_chunks
            fill_pct = int(round(100 * writer.queued_chunks() / capacity)) if capacity else 0
            drift_note = ""
            drift_delta = (align.drift.rate_correction - 1.0) * 100.0
            if abs(drift_delta) >= 0.01:
                drift_note = f", drift {drift_delta:+.2f}%"
            details.append(
                f"{device.name} [{profile.display}, align {align.total_align_ms:.0f} ms, "
                f"queue {fill_pct}%{drift_note}]"
            )
        if not details:
            message = _routing_health_idle_message(output_streams)
        else:
            message = (
                f"Routing health: {len(details)} mirrored speaker(s) — "
                + "; ".join(details)
            )
        if speech_profile_label and details:
            message += f" | speech-at-work: {speech_profile_label}"
    else:
        live_names = [
            device.name
            for device, _, _, _, writer, *_ in output_streams
            if writer.failed_error is None
        ]
        if not live_names:
            message = _routing_health_idle_message(output_streams)
        else:
            names = ", ".join(live_names)
            message = (
                f"Routing health: {len(live_names)} mirrored speaker(s) active — {names}"
            )
    if capture_max_rms is not None and capture_max_rms < 120.0:
        message += (
            f" | loopback quiet (peak {capture_max_rms:.0f} RMS) — "
            "play audio on the Windows default speaker"
        )
    return message


def build_startup_beep_chunk(capture_rate: int, chunk_frames: int) -> np.ndarray:
    """Short stereo tone used to confirm routed outputs are alive."""
    frames = min(chunk_frames, max(256, int(capture_rate * 0.35)))
    t = np.arange(frames, dtype=np.float64) / capture_rate
    envelope = np.minimum(1.0, t / 0.02) * np.minimum(1.0, (frames / capture_rate - t) / 0.05)
    tone = (0.65 * 32767.0 * envelope * np.sin(2.0 * np.pi * 523.25 * t)).astype(np.int16)
    return np.column_stack((tone, tone)).reshape(-1)


def build_tone_chunk(
    sample_rate: int,
    chunk_frames: int,
    *,
    frequency_hz: float = 523.25,
    duration_sec: float = 0.35,
    amplitude: float = 0.65,
) -> np.ndarray:
    """Build a short stereo tone for speaker path checks."""
    frames = min(chunk_frames * 6, max(256, int(sample_rate * duration_sec)))
    t = np.arange(frames, dtype=np.float64) / sample_rate
    envelope = np.minimum(1.0, t / 0.02) * np.minimum(1.0, (frames / sample_rate - t) / 0.08)
    tone = (
        amplitude * 32767.0 * envelope * np.sin(2.0 * np.pi * frequency_hz * t)
    ).astype(np.int16)
    return np.column_stack((tone, tone)).reshape(-1)


def prepare_output_payload(
    source: np.ndarray,
    capture_rate: int,
    output_rate: int,
    out_channels: int,
) -> bytes:
    """Convert captured stereo audio into the bytes expected by an output stream."""
    if source.size == 0:
        return b""
    if source.size % 2 != 0:
        source = source[:-1]
    if source.size == 0:
        return b""

    payload = source
    if output_rate != capture_rate:
        stereo = source.reshape(-1, 2)
        target_frames = int(round(stereo.shape[0] * output_rate / capture_rate))
        if target_frames <= 0:
            return b""
        x_old = np.linspace(0.0, 1.0, stereo.shape[0], endpoint=False)
        x_new = np.linspace(0.0, 1.0, target_frames, endpoint=False)
        left = np.interp(x_new, x_old, stereo[:, 0])
        right = np.interp(x_new, x_old, stereo[:, 1])
        payload = np.column_stack((left, right)).astype(np.int16).reshape(-1)

    if out_channels == 1:
        mono = payload.reshape(-1, 2).mean(axis=1).astype(np.int16)
        return mono.tobytes()
    return payload.tobytes()


def loopback_frames_to_read(
    output_frames: int,
    output_rate: int,
    capture_rate: int,
) -> int:
    """Scale a loopback read size when default output and capture rates differ."""
    if output_rate == capture_rate or output_frames <= 0:
        return max(0, output_frames)
    return max(1, int(round(output_frames * capture_rate / output_rate)))


def capture_chunk_rms(source: np.ndarray) -> float:
    """Return RMS level for a mono or interleaved int16 capture buffer."""
    if source.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(source.astype(np.float64) ** 2)))


def format_silent_loopback_hint(default_output_name: str) -> str:
    """Explain why routed speakers may be quiet while the default device plays."""
    return (
        "Loopback capture is silent while routing is active. "
        f"The Windows default speaker ({default_output_name}) may still play audio, "
        "but mirrored speakers will stay quiet until loopback receives sound.\n"
        "  1) Keep Start Route running (do not close this window).\n"
        "  2) Set your movie app output to the same Windows default device.\n"
        "  3) Sound settings -> your default speaker -> Advanced -> turn OFF "
        "'Allow applications to take exclusive control of this device'.\n"
        "  4) Retry after playing a test sound, then start the movie again."
    )


def loopback_matches_current_default(loopback: dict, default_output_name: str) -> bool:
    """Return True when ``loopback`` still captures the current default playback device."""
    return devices_refer_to_same_endpoint(
        loopback_playback_name(loopback),
        default_output_name,
    )


def format_routing_plan(
    default_output_name: str,
    routed_devices: list[PlaybackDevice],
) -> str:
    """Explain how audio reaches each speaker for the current Windows default device."""
    lines = [
        f"Windows default output: {default_output_name}",
        "",
        "Audio routing:",
        f"  Direct (Windows default): {default_output_name}",
    ]
    if routed_devices:
        for device in routed_devices:
            lines.append(f"  Routed by bt-surround:    {device.name}")
    else:
        lines.append("  Routed by bt-surround:    (none — only the default device will play)")

    lines.extend(
        [
            "",
            "Bluetooth-only setup:",
            "  You do NOT need PC speakers.",
            "  Set Windows default to ANY one Bluetooth speaker.",
            "  The other Bluetooth speakers get the same audio automatically.",
            "  Settings -> System -> Sound -> Output -> pick one BT device.",
        ]
    )
    return "\n".join(lines)


class SurroundRouter:
    def __init__(self, pyaudio_instance) -> None:
        self._pa = pyaudio_instance
        self._waiting_for_devices = False
        self._loopback_stale_warned = False
        self._neural_engine: NeuralUpmixEngine | None = None
        self._overlay_last_saved_steps = 0
        self._overlay_last_autosave_time = 0.0
        self._route_shutting_down = False

    def _probe_routed_outputs(
        self,
        output_streams: list[OutputStream],
        chunk_frames: int,
    ) -> None:
        """Play a loud distinct tone on each routed speaker (no loopback required)."""
        check_freqs = (523.25, 659.25, 784.0, 392.0)
        for index, (device, out_channels, output_rate, _, writer, *_) in enumerate(output_streams):
            freq = check_freqs[index % len(check_freqs)]
            tone = build_tone_chunk(output_rate, chunk_frames, frequency_hz=freq)
            if out_channels == 1:
                payload = tone.reshape(-1, 2).mean(axis=1).astype(np.int16).tobytes()
            else:
                payload = tone.tobytes()
            writer.submit(payload)
            print(f"Speaker check: [{device.index}] {device.name} @ {freq:.0f} Hz", flush=True)
            writer.wait_until_idle(timeout_sec=1.5)

    def _probe_loopback_mirror(
        self,
        capture_stream: object,
        capture_channels: int,
        capture_rate: int,
        default_index: int,
        config: RouteConfig,
        output_streams: list[OutputStream],
        output_lock: threading.Lock,
        *,
        calibration: CalibrationProfile | None,
        azimuth_by_index: dict[int, float],
        controller: AdaptiveRouteController | None = None,
    ) -> float:
        """Play on the Windows default device and verify loopback reaches routed outputs."""
        peak_rms = 0.0
        prev_learning: bool | None = None
        if self._neural_engine is not None:
            prev_learning = self._neural_engine.learning_enabled
            self._neural_engine.set_learning_enabled(False)
        default_rate = int(self._pa.get_device_info_by_index(default_index)["defaultSampleRate"])
        verify_rate = capture_rate
        verify_out = None
        open_error: OSError | None = None
        for rate in (capture_rate, default_rate):
            try:
                verify_out = self._pa.open(
                    format=self._pa.get_format_from_width(2),
                    channels=2,
                    rate=rate,
                    output=True,
                    output_device_index=default_index,
                    frames_per_buffer=config.chunk_frames,
                )
                verify_rate = rate
                open_error = None
                break
            except OSError as exc:
                open_error = exc
        if verify_out is None:
            print(
                f"Loopback mirror check skipped: could not open default output ({open_error})",
                flush=True,
            )
            if self._neural_engine is not None and prev_learning is not None:
                self._neural_engine.set_learning_enabled(prev_learning)
            return peak_rms

        try:
            if not verify_out.is_active():
                verify_out.start_stream()
            for _ in range(3):
                raw = capture_stream.read(config.chunk_frames, exception_on_overflow=False)
                _ = normalize_loopback_chunk(raw, capture_channels)
            tone = build_tone_chunk(verify_rate, config.chunk_frames, frequency_hz=440.0)
            stereo = tone.reshape(-1, 2)
            for offset in range(0, stereo.shape[0], config.chunk_frames):
                chunk = stereo[offset : offset + config.chunk_frames]
                if chunk.size == 0:
                    break
                verify_out.write(chunk.astype(np.int16).tobytes())
                frames_to_read = loopback_frames_to_read(
                    chunk.shape[0],
                    verify_rate,
                    capture_rate,
                )
                raw = capture_stream.read(frames_to_read, exception_on_overflow=False)
                source = normalize_loopback_chunk(raw, capture_channels)
                peak_rms = max(peak_rms, capture_chunk_rms(source))
                self._dispatch_chunk(
                    source,
                    capture_rate,
                    output_streams,
                    output_lock,
                    use_spatial_panning=config.use_spatial_panning,
                    use_content_split=config.use_content_split,
                    max_surround_separation=config.max_surround_separation,
                    calibration=calibration,
                    azimuth_by_index=azimuth_by_index,
                    count_neural_chunk=False,
                    controller=controller,
                    speech_aware=False,
                )
            time.sleep(0.5)
        finally:
            if self._neural_engine is not None and prev_learning is not None:
                self._neural_engine.set_learning_enabled(prev_learning)
            verify_out.stop_stream()
            verify_out.close()

        if peak_rms >= 500.0:
            print(
                f"Loopback mirror check: OK (peak {peak_rms:.0f} RMS). "
                "Routed speakers should mirror the Windows default.",
                flush=True,
            )
        else:
            print(
                f"Loopback mirror check: FAILED (peak {peak_rms:.0f} RMS). "
                "Mirrored speakers will stay quiet until loopback captures audio.",
                flush=True,
            )
            print(format_silent_loopback_hint(self._pa.get_device_info_by_index(default_index)["name"]), flush=True)
        return peak_rms

    def _warn_if_capture_loopback_stale(self, config: RouteConfig, loopback: dict) -> None:
        if config.source_loopback_index is not None or self._loopback_stale_warned:
            return
        if loopback_matches_current_default(loopback, self._wasapi_default_output_name()):
            return
        self._loopback_stale_warned = True
        print(
            "Warning: Windows default output changed since routing started. "
            "Captured audio may be wrong — stop and restart route so loopback "
            "re-binds to the new default speaker.",
            flush=True,
        )

    def _wasapi_default_output_name(self) -> str:
        import pyaudiowpatch as pyaudio

        wasapi = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_out = self._pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
        return str(default_out["name"])

    def _wasapi_default_output_index(self) -> int:
        import pyaudiowpatch as pyaudio

        wasapi = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        return int(wasapi["defaultOutputDevice"])

    def _default_loopback_device(self) -> dict:
        default_name = self._wasapi_default_output_name()

        get_default_loopback = getattr(self._pa, "get_default_wasapi_loopback", None)
        if callable(get_default_loopback):
            try:
                return get_default_loopback()
            except (OSError, LookupError):
                pass

        for loopback in self._pa.get_loopback_device_info_generator():
            if loopback_matches_current_default(loopback, default_name):
                return loopback

        raise RuntimeError(
            "Could not find WASAPI loopback for the default playback device. "
            "Play a test sound once, then retry."
        )

    def _resolve_loopback(self, config: RouteConfig) -> dict:
        if config.source_loopback_index is None:
            return self._default_loopback_device()

        info = self._pa.get_device_info_by_index(config.source_loopback_index)
        name = str(info["name"]).lower()
        if "loopback" not in name:
            raise RuntimeError(
                f"Device [{config.source_loopback_index}] '{info['name']}' is not a "
                "loopback endpoint. Omit --source to use the default playback loopback."
            )
        return info

    def _resolve_targets(self, config: RouteConfig) -> list[PlaybackDevice]:
        devices = list_wasapi_playback_devices(self._pa, bluetooth_only=True)
        if not devices:
            raise RuntimeError(
                "No Bluetooth playback devices found. Pair/connect speakers, then run "
                "`bt-surround list`."
            )

        if config.device_indexes and config.device_names:
            raise ValueError(
                "Use either device indexes or device name patterns, not both."
            )

        if config.device_indexes:
            wanted = set(config.device_indexes)
            selected = [device for device in devices if device.index in wanted]
            missing = wanted - {device.index for device in selected}
            if missing:
                raise RuntimeError(
                    f"Requested device index(es) not found: {sorted(missing)}"
                )
            return selected

        if config.device_names:
            return filter_devices_by_names(devices, config.device_names)

        return devices

    def _open_output_stream(
        self,
        device: PlaybackDevice,
        capture_rate: int,
        chunk_frames: int,
        buffer_min: int,
    ):
        channels = min(2, device.max_output_channels)
        device_rate = int(device.default_sample_rate)
        rates_to_try: list[int] = []
        for rate in (capture_rate, device_rate):
            if rate > 0 and rate not in rates_to_try:
                rates_to_try.append(rate)

        last_exc: OSError | None = None
        for rate in rates_to_try:
            try:
                stream = self._pa.open(
                    format=self._pa.get_format_from_width(2),
                    channels=channels,
                    rate=rate,
                    frames_per_buffer=output_buffer_frames(chunk_frames, buffer_min),
                    output=True,
                    output_device_index=device.index,
                )
            except OSError as exc:
                last_exc = exc
                continue
            if not stream.is_active():
                stream.start_stream()
            if rate != capture_rate:
                print(
                    f"Output note: {device.name} opened at {rate} Hz "
                    f"(capture/loopback is {capture_rate} Hz; resampling applied).",
                    flush=True,
                )
            return channels, rate, stream

        tried = ", ".join(str(rate) for rate in rates_to_try) or str(capture_rate)
        raise OSError(
            f"{device.name}: cannot open output at {tried} Hz "
            f"(device default is {device_rate} Hz): {last_exc}"
        ) from last_exc

    def _echo_source_name(self, config: RouteConfig, loopback: dict) -> str:
        if config.source_loopback_index is None:
            return self._wasapi_default_output_name()
        return loopback_playback_name(loopback)

    def _desired_targets(
        self,
        config: RouteConfig,
        echo_source_name: str,
        *,
        quiet: bool = False,
    ) -> list[PlaybackDevice]:
        try:
            targets = self._resolve_targets(config)
        except RuntimeError:
            if quiet:
                return []
            raise

        try:
            return exclude_echo_targets(targets, echo_source_name, quiet=quiet)
        except RuntimeError:
            if quiet:
                return []
            raise

    def explain_plan(self, config: RouteConfig) -> str:
        loopback = self._resolve_loopback(config)
        echo_source_name = self._echo_source_name(config, loopback)
        default_output_name = self._wasapi_default_output_name()
        routing_note = ""
        try:
            all_targets = self._resolve_targets(config)
            routed_devices = exclude_echo_targets(all_targets, echo_source_name, quiet=True)
        except RuntimeError as exc:
            routed_devices = []
            routing_note = f"\n\nRouting note: {exc}"

        plan = format_routing_plan(default_output_name, routed_devices) + routing_note
        plan += self._spatial_pan_summary(config, routed_devices)
        plan += self._content_split_summary(config)
        plan += self._neural_summary(config)
        plan += self._adaptive_stream_summary(config)
        calibration = self._resolve_calibration(config, quiet=True)
        if calibration is None:
            return plan

        align_lines = ["", "Echolocation alignment:"]
        for device in routed_devices:
            if not calibration.has_calibration_for(device.name):
                align_lines.append(
                    f"  {device.name}: not in calibration (re-run calibrate)"
                )
                continue
            align_ms = (
                calibration.mirror_alignment_ms_for(
                    device.name,
                    [routed.name for routed in routed_devices],
                )
                if config.lip_sync
                else calibration.alignment_ms_for(device.name)
            )
            level_db = calibration.level_db_for(device.name)
            level_note = ""
            if abs(level_db) >= 0.1:
                sign = "+" if level_db > 0 else ""
                level_note = f", {sign}{level_db:.1f} dB level trim"
            if align_ms > 0:
                align_lines.append(
                    f"  {device.name}: +{align_ms:.1f} ms routing delay{level_note}"
                )
            else:
                align_lines.append(f"  {device.name}: no extra delay{level_note}")
        if len(align_lines) == 2:
            align_lines.append("  (no routed speakers — only Windows default is active)")
        return plan + "\n" + "\n".join(align_lines)

    def _spatial_pan_summary(
        self,
        config: RouteConfig,
        routed_devices: list[PlaybackDevice],
    ) -> str:
        if (
            not config.use_spatial_panning
            or config.max_surround_separation
            or not routed_devices
        ):
            return ""
        return (
            "\n\nSpatial panning: ON — each routed speaker gets an L/R mix based on "
            "stage azimuth (GUI layout or calibration.json)."
        )

    def _content_split_summary(self, config: RouteConfig) -> str:
        if config.max_surround_separation:
            return (
                "\n\nSurround matrix: MAX — center=dialogue only, rear=decorrelated "
                "ambience, sides=directional (5.1-style separation from stereo)."
            )
        if not config.use_content_split:
            return ""
        return (
            "\n\nContent split: ON — front speakers emphasize dialogue (mid), "
            "side/rear speakers carry ambience (reduces echo vs the direct default)."
        )

    def _overlay_persist_label(self, config: RouteConfig) -> str:
        path = resolve_overlay_state_path(config.overlay_state_path)
        if config.overlay_state_path:
            return str(path)
        return path.name

    def _neural_summary(self, config: RouteConfig) -> str:
        if not config.neural_upmix and not config.continual_overlay:
            return ""
        from bluettooth_surround.neural_upmix.onnx_providers import (
            list_installed_ort_providers,
            normalize_onnx_device,
            provider_display_name,
        )

        parts: list[str] = []
        device = normalize_onnx_device(config.onnx_device)
        device_note = f"ONNX device {device}"
        if device in {"auto", "cuda"} and config.onnx_device_id:
            device_note += f" (CUDA index {config.onnx_device_id})"
        parts.append(device_note)
        installed = [
            provider_display_name(provider)
            for provider in list_installed_ort_providers()
        ]
        if installed:
            parts.append("installed providers: " + ", ".join(installed))
        if config.neural_upmix:
            onnx = resolve_onnx_model_path(config.onnx_model_path)
            if onnx:
                parts.append(f"ONNX upmix ({onnx})")
            else:
                parts.append("matrix base (no upmix.onnx found)")
        if config.continual_overlay:
            preset = config.overlay_aggressiveness
            overlay_file = self._overlay_persist_label(config)
            parts.append(
                "live-conditioning overlay "
                f"({preset}; speech/ambience-aware; persists to {overlay_file})"
            )
            if config.overlay_autosave_steps > 0 or config.overlay_autosave_interval_sec > 0:
                parts.append(
                    f"autosave every {config.overlay_autosave_steps} chunks"
                    + (
                        f" or {config.overlay_autosave_interval_sec:.0f}s"
                        if config.overlay_autosave_interval_sec > 0
                        else ""
                    )
                )
            parts.append("live learn telemetry every ~15s in route health log")
            if not config.neural_upmix:
                onnx = resolve_onnx_model_path(config.onnx_model_path)
                if onnx:
                    parts.append(f"ONNX content hints ({onnx})")
        return "\n\nNeural path: " + "; ".join(parts) + "."

    def _activate_neural_engine(self, config: RouteConfig, *, announce: bool = True) -> None:
        onnx_path = resolve_onnx_model_path(config.onnx_model_path)
        if config.onnx_model_path and onnx_path is None and announce:
            print(
                f"Neural: ONNX model not found at '{config.onnx_model_path}' "
                "(using matrix/heuristic fallback).",
                flush=True,
            )
        self._neural_engine = NeuralUpmixEngine.from_route_flags(
            neural_upmix=config.neural_upmix,
            continual_overlay=config.continual_overlay,
            onnx_model_path=onnx_path,
            onnx_device=config.onnx_device,
            onnx_device_id=config.onnx_device_id,
            overlay_aggressiveness=config.overlay_aggressiveness,
        )
        if self._neural_engine is None:
            return

        self._neural_engine.set_learning_enabled(True)

        restored = False
        restored_preset: str | None = None
        overlay_path = resolve_overlay_state_path(config.overlay_state_path)
        if config.reset_overlay:
            self._neural_engine.reset_overlay()
            delete_overlay_state(overlay_path)
        elif config.continual_overlay:
            if config.overlay_persist:
                saved = None
                if overlay_path.is_file():
                    saved = load_overlay_state(overlay_path)
                    if saved is None:
                        print(
                            f"Live overlay: ignoring stale or invalid {overlay_path} "
                            "(version mismatch or corrupt file — use Reset Overlay).",
                            flush=True,
                        )
                if saved is not None:
                    if not self._neural_engine.load_overlay(saved):
                        print(
                            f"Live overlay: ignoring incompatible weights in {overlay_path} "
                            "(shape mismatch — use Reset Overlay).",
                            flush=True,
                        )
                    else:
                        restored = True
                        # Autosave threshold is measured in capture chunks, not overlay learn steps.
                        self._overlay_last_saved_steps = 0
                        current_preset = normalize_overlay_aggressiveness(
                            config.overlay_aggressiveness
                        )
                        saved_preset = saved.training_aggressiveness
                        restored_preset = saved_preset
                        if saved_preset and saved_preset != current_preset and announce:
                            print(
                                f"Live overlay: warning — saved state was trained with "
                                f"'{saved_preset}' preset but route uses '{current_preset}'. "
                                "Use Reset Overlay if adaptation sounds wrong.",
                                flush=True,
                            )

        if not announce:
            return
        if config.neural_upmix:
            if self._neural_engine.onnx_active:
                provider = self._neural_engine.onnx_execution_provider
                provider_note = f", {provider}" if provider else ""
                print(
                    f"Neural upmix: ONNX frozen base ({onnx_path}{provider_note})",
                    flush=True,
                )
            elif onnx_path is not None:
                print(
                    f"Neural upmix: ONNX model at '{onnx_path}' failed to load "
                    "(using matrix/heuristic fallback).",
                    flush=True,
                )
            else:
                print(
                    "Neural upmix: frozen surround-matrix base (place upmix.onnx beside exe for ONNX).",
                    flush=True,
                )
        if config.continual_overlay:
            if restored:
                preset = restored_preset or config.overlay_aggressiveness
                print(
                    f"Live overlay: restored plastic state "
                    f"({self._neural_engine.overlay_steps} steps, {preset} preset) "
                    f"from {overlay_path}",
                    flush=True,
                )
            else:
                preset = config.overlay_aggressiveness
                overlay_file = self._overlay_persist_label(config)
                print(
                    f"Live overlay: ON ({preset}) — plastic MLP conditions each chunk; "
                    f"base weights frozen (persists to {overlay_file}).",
                    flush=True,
                )
            if (
                not config.neural_upmix
                and self._neural_engine.onnx_active
                and onnx_path
            ):
                provider = self._neural_engine.onnx_execution_provider
                provider_note = f" ({provider})" if provider else ""
                print(
                    f"Live overlay: using ONNX content hints from {onnx_path}{provider_note}.",
                    flush=True,
                )

    def _print_overlay_learn_telemetry(
        self,
        config: RouteConfig,
        *,
        idle_message: bool = False,
    ) -> None:
        if not config.continual_overlay or self._neural_engine is None:
            return
        overlay_line = getattr(self._neural_engine, "overlay_telemetry_line", None)
        if not callable(overlay_line):
            return
        line = overlay_line()
        if line:
            print(line, flush=True)
        elif idle_message:
            print(
                "Overlay learn: waiting for routed audio (updates every ~15s).",
                flush=True,
            )

    def _persist_overlay_state(self, config: RouteConfig) -> bool:
        if self._neural_engine is None:
            return False
        overlay_path = resolve_overlay_state_path(config.overlay_state_path)
        try:
            save_overlay_state(self._neural_engine.export_overlay(), overlay_path)
        except OSError as exc:
            print(
                f"Live overlay: could not save {overlay_path} ({exc}).",
                flush=True,
            )
            return False
        return True

    def _deactivate_neural_engine(self, config: RouteConfig, *, persist: bool = True) -> None:
        if self._neural_engine is None:
            return
        if (
            persist
            and config.continual_overlay
            and config.overlay_persist
        ):
            if self._persist_overlay_state(config):
                overlay_path = resolve_overlay_state_path(config.overlay_state_path)
                print(
                    f"Live overlay: saved plastic state to {overlay_path}.",
                    flush=True,
                )
        self._neural_engine = None
        self._overlay_last_saved_steps = 0
        self._overlay_last_autosave_time = 0.0

    def _maybe_autosave_overlay(self, config: RouteConfig, *, now: float | None = None) -> None:
        if self._route_shutting_down:
            return
        if self._neural_engine is None or not config.continual_overlay or not config.overlay_persist:
            return
        monotonic_now = now if now is not None else time.monotonic()
        chunks = self._neural_engine.chunks_processed
        step_due = (
            config.overlay_autosave_steps > 0
            and chunks > self._overlay_last_saved_steps
            and chunks - self._overlay_last_saved_steps >= config.overlay_autosave_steps
        )
        interval_due = (
            config.overlay_autosave_interval_sec > 0
            and monotonic_now - self._overlay_last_autosave_time
            >= config.overlay_autosave_interval_sec
        )
        if not step_due and not interval_due:
            return
        if self._persist_overlay_state(config):
            self._overlay_last_saved_steps = chunks
            self._overlay_last_autosave_time = monotonic_now

    def _adaptive_stream_summary(self, config: RouteConfig) -> str:
        if not config.use_adaptive_stream:
            return ""
        summary = (
            "\n\nAdaptive stream: ON — Thompson sampling picks per-speaker compression "
            "and buffer profiles using the Windows default speaker as timing reference."
        )
        if config.speech_aware_routing:
            summary += (
                "\nSpeech-at-work: ON — second Thompson branch gates dialogue on rear/side "
                "speakers (skipped when ONNX speech stems are active)."
            )
        return summary

    def _resolve_calibration(
        self,
        config: RouteConfig,
        *,
        quiet: bool = False,
    ) -> CalibrationProfile | None:
        search_paths: list[str | None] = []
        if config.calibration_path:
            search_paths.append(config.calibration_path)
        if config.use_calibration:
            search_paths.append(None)
        elif not search_paths:
            return None

        last_error: str | None = None
        for path in search_paths:
            resolved = resolve_calibration_file(path)
            if resolved is None:
                if path is not None and not quiet:
                    last_error = f"file not found '{path}'"
                continue
            try:
                profile = load_calibration_for_routing(resolved)
                if not config.use_calibration:
                    for entry in profile.speakers.values():
                        entry.delay_ms = 0.0
                        entry.align_delay_ms = 0.0
                return profile
            except (OSError, ValueError, json.JSONDecodeError, KeyError) as exc:
                last_error = f"could not load '{resolved}' ({exc})"
                if not quiet:
                    print(
                        f"Calibration warning: {last_error}.",
                        flush=True,
                    )

        if not quiet and last_error is not None:
            print(
                f"Calibration warning: {last_error}. Continuing without time alignment.",
                flush=True,
            )
        elif not quiet and config.calibration_path is not None:
            print(
                f"Calibration warning: file not found '{config.calibration_path}'. "
                "Continuing without time alignment.",
                flush=True,
            )
        return None

    def _live_routed_targets(
        self,
        output_streams: list[OutputStream],
    ) -> list[PlaybackDevice]:
        return [device for device, *_ in output_streams]

    def _live_dispatch_indices(self, outputs: list[OutputStream]) -> list[int]:
        """Speaker indices whose async writers are still accepting audio."""
        return [
            index
            for index, (_device, _ch, _rate, _stream, writer, *_rest) in enumerate(outputs)
            if writer.failed_error is None
        ]

    def _bound_writer_for_device(
        self,
        device: PlaybackDevice,
        output_streams: list[OutputStream],
    ) -> AsyncOutputWriter | None:
        for active, _, _, _, writer, _, _, _ in output_streams:
            if active.index == device.index:
                return writer
        return None

    def _live_adapt_targets(
        self,
        output_streams: list[OutputStream],
    ) -> list[
        tuple[
            PlaybackDevice,
            WriterTelemetry,
            StreamProfile,
            int,
            int,
        ]
    ]:
        """Collect per-device adapt inputs, skipping outputs already in write-failure state."""
        targets: list[
            tuple[
                PlaybackDevice,
                WriterTelemetry,
                StreamProfile,
                int,
                int,
            ]
        ] = []
        for (
            device,
            _,
            _,
            _,
            writer,
            _,
            profile,
            _,
        ) in output_streams:
            if writer.failed_error is not None:
                continue
            targets.append(
                (
                    device,
                    writer.telemetry,
                    profile,
                    writer.queued_chunks(),
                    writer.max_queued_chunks,
                )
            )
        return targets

    def _routing_align_ms(
        self,
        device: PlaybackDevice,
        calibration: CalibrationProfile | None,
        routed_targets: list[PlaybackDevice] | None,
        *,
        lip_sync: bool,
    ) -> float:
        if calibration is None:
            return 0.0
        if lip_sync:
            peers = list(routed_targets or [])
            if not any(
                devices_refer_to_same_endpoint(peer.name, device.name) for peer in peers
            ):
                peers.append(device)
            if peers:
                return calibration.mirror_alignment_ms_for(
                    device.name,
                    [target.name for target in peers],
                )
            return calibration.mirror_alignment_ms_for(device.name, [device.name])
        return calibration.alignment_ms_for(device.name)

    def _prepare_output_stream(
        self,
        device: PlaybackDevice,
        capture_rate: int,
        chunk_frames: int,
        warnings: list[str],
        calibration: CalibrationProfile | None = None,
        *,
        controller: AdaptiveRouteController | None = None,
        stream_profile: StreamProfile | None = None,
        fallback_queue: int = LOW_LATENCY_QUEUE_CHUNKS,
        fallback_buffer_min: int = LOW_LATENCY_BUFFER_MIN,
        azimuth_deg: float = 0.0,
        routed_targets: list[PlaybackDevice] | None = None,
        lip_sync: bool = True,
        quiet: bool = False,
    ) -> OutputStream | None:
        base_align_ms = self._routing_align_ms(
            device,
            calibration,
            routed_targets,
            lip_sync=lip_sync,
        )
        if controller is not None and controller.enabled:
            profile = stream_profile or controller.pick_profile(device.index)
            if stream_profile is not None:
                controller.selector.set_active(device.index, stream_profile.profile_id)
            controller.ensure_device(device.index, base_align_ms=base_align_ms)
            align_state = controller.align_by_index[device.index]
            queue_depth = profile_queue_depth(profile, fallback_queue)
            buffer_min = profile_buffer_min(chunk_frames, profile, fallback_buffer_min)
        else:
            profile = stream_profile or StreamProfile(
                "fixed",
                fallback_queue,
                2,
                "none",
                "fixed",
            )
            align_state = AdaptiveAlignState(base_align_ms=base_align_ms)
            queue_depth = fallback_queue
            buffer_min = fallback_buffer_min

        try:
            channels, output_rate, stream = self._open_output_stream(
                device,
                capture_rate,
                chunk_frames,
                buffer_min,
            )
        except OSError as exc:
            if controller is not None and controller.enabled and stream_profile is None:
                controller.clear_device(device.index)
            warnings.append(str(exc))
            if not quiet:
                print(f"Output warning: {exc}", flush=True)
            return None

        writer = AsyncOutputWriter(
            device.name,
            stream,
            max_queued_chunks=queue_depth,
            compression=profile.compression,
            out_channels=channels,
        )
        if not quiet:
            align_note = ""
            if calibration is not None:
                if not calibration.has_calibration_for(device.name):
                    note = (
                        f"{device.name}: not in calibration file; "
                        "no time alignment applied"
                    )
                    if note not in warnings:
                        warnings.append(note)
                    print(f"  Output note: {note}", flush=True)
                elif base_align_ms > 0:
                    align_note = f", align +{base_align_ms:.1f} ms"
            pan_note = f", pan {azimuth_deg:+.0f}°"
            profile_note = f", profile {profile.display}"
            print(
                f"Output:  [{device.index}] {device.name} "
                f"@ {output_rate} Hz{pan_note}{profile_note}{align_note}",
                flush=True,
            )
        return (
            device,
            channels,
            output_rate,
            stream,
            writer,
            azimuth_deg,
            profile,
            align_state,
        )

    def _attach_output_device(
        self,
        device: PlaybackDevice,
        capture_rate: int,
        chunk_frames: int,
        output_streams: list[OutputStream],
        warnings: list[str],
        calibration: CalibrationProfile | None = None,
        *,
        controller: AdaptiveRouteController | None = None,
        stream_profile: StreamProfile | None = None,
        fallback_queue: int = LOW_LATENCY_QUEUE_CHUNKS,
        fallback_buffer_min: int = LOW_LATENCY_BUFFER_MIN,
        azimuth_deg: float = 0.0,
        routed_targets: list[PlaybackDevice] | None = None,
        lip_sync: bool = True,
    ) -> bool:
        for attempt in range(BT_DEVICE_OPEN_RETRIES + 1):
            prepared = self._prepare_output_stream(
                device,
                capture_rate,
                chunk_frames,
                warnings,
                calibration,
                controller=controller,
                stream_profile=stream_profile,
                fallback_queue=fallback_queue,
                fallback_buffer_min=fallback_buffer_min,
                azimuth_deg=azimuth_deg,
                routed_targets=routed_targets,
                lip_sync=lip_sync,
                quiet=attempt > 0,
            )
            if prepared is not None:
                output_streams.append(prepared)
                return True
            if attempt < BT_DEVICE_OPEN_RETRIES:
                time.sleep(0.35 * (attempt + 1))
        return False

    def _writer_still_bound(
        self,
        device: PlaybackDevice,
        writer: AsyncOutputWriter,
        output_streams: list[OutputStream],
        output_lock: threading.Lock,
    ) -> bool:
        with output_lock:
            for bound_device, _, _, _, bound_writer, _, _, _ in output_streams:
                if bound_device.index == device.index:
                    return bound_writer is writer
        return False

    def _pop_output_stream(
        self,
        device: PlaybackDevice,
        output_streams: list[OutputStream],
    ) -> OutputStream | None:
        for index, entry in enumerate(output_streams):
            active = entry[0]
            if not devices_refer_to_same_endpoint(active.name, device.name):
                continue
            _, _, _, stream, writer, _, _, _ = entry
            writer.stop()
            stream.stop_stream()
            stream.close()
            return output_streams.pop(index)
        return None

    def _detach_output_device(
        self,
        device: PlaybackDevice,
        output_streams: list[OutputStream],
        *,
        reason: str = "disconnected",
        controller: AdaptiveRouteController | None = None,
        clear_controller: bool = True,
    ) -> None:
        removed = self._pop_output_stream(device, output_streams)
        if removed is None:
            return
        active = removed[0]
        if (
            controller is not None
            and clear_controller
            and reason != "write failure"
        ):
            controller.clear_device(active.index)
        if reason == "write failure":
            print(
                f"Output dropped: {active.name} (write failures). "
                "Hot-plug will retry in a few seconds.",
                flush=True,
            )
        else:
            print(f"Removed disconnected device: {active.name}", flush=True)

    def _reattach_output_device(
        self,
        device: PlaybackDevice,
        capture_rate: int,
        chunk_frames: int,
        output_streams: list[OutputStream],
        warnings: list[str],
        calibration: CalibrationProfile | None,
        controller: AdaptiveRouteController,
        stream_profile: StreamProfile,
        azimuth_by_index: dict[int, float],
        *,
        previous_profile: StreamProfile | None = None,
        fallback_queue: int = LOW_LATENCY_QUEUE_CHUNKS,
        fallback_buffer_min: int = LOW_LATENCY_BUFFER_MIN,
        output_lock: threading.Lock | None = None,
        routed_targets: list[PlaybackDevice] | None = None,
        lip_sync: bool = True,
    ) -> None:
        def detach_preserve_controller() -> None:
            if output_lock is not None:
                with output_lock:
                    self._pop_output_stream(device, output_streams)
            else:
                self._pop_output_stream(device, output_streams)

        detach_preserve_controller()

        prepared = self._prepare_output_stream(
            device,
            capture_rate,
            chunk_frames,
            warnings,
            calibration,
            controller=controller,
            stream_profile=stream_profile,
            fallback_queue=fallback_queue,
            fallback_buffer_min=fallback_buffer_min,
            azimuth_deg=azimuth_by_index.get(device.index, 0.0),
            routed_targets=routed_targets,
            lip_sync=lip_sync,
            quiet=True,
        )
        if prepared is None:
            if previous_profile is not None:
                controller.selector.set_active(device.index, previous_profile.profile_id)
                prepared = self._prepare_output_stream(
                    device,
                    capture_rate,
                    chunk_frames,
                    warnings,
                    calibration,
                    controller=controller,
                    stream_profile=previous_profile,
                    fallback_queue=fallback_queue,
                    fallback_buffer_min=fallback_buffer_min,
                    azimuth_deg=azimuth_by_index.get(device.index, 0.0),
                    routed_targets=routed_targets,
                    lip_sync=lip_sync,
                    quiet=True,
                )
            if prepared is None:
                print(
                    f"Adaptive profile switch failed: {device.name} "
                    f"could not reopen (tried {stream_profile.display}"
                    f"{f' and {previous_profile.display}' if previous_profile else ''}).",
                    flush=True,
                )
                return
            print(
                f"Adaptive profile switch rolled back: {device.name} "
                f"staying on {previous_profile.display}",
                flush=True,
            )
            stream_profile = previous_profile
        else:
            controller.selector.set_active(device.index, stream_profile.profile_id)

        if output_lock is not None:
            with output_lock:
                output_streams.append(prepared)
        else:
            output_streams.append(prepared)
        print(
            f"Adaptive profile switch: {device.name} -> {stream_profile.display}",
            flush=True,
        )

    def _sync_live_azimuth_overrides(
        self,
        config: RouteConfig,
        devices: list[PlaybackDevice],
        azimuth_by_index: dict[int, float],
    ) -> bool:
        if not config.azimuth_override_path or not devices:
            return False
        overrides = read_azimuth_overrides_by_name(config.azimuth_override_path)
        return apply_live_azimuth_overrides(azimuth_by_index, devices, overrides)

    def _sync_hotplug_devices(
        self,
        config: RouteConfig,
        capture_rate: int,
        output_streams: list[OutputStream],
        warnings: list[str],
        calibration: CalibrationProfile | None,
        controller: AdaptiveRouteController | None,
        *,
        echo_source_name: str,
        default_output_name: str,
        fallback_queue: int,
        fallback_buffer_min: int,
        azimuth_by_index: dict[int, float],
        output_lock: threading.Lock | None = None,
    ) -> None:
        desired_targets = self._desired_targets(config, echo_source_name, quiet=True)

        def mutate_outputs(action) -> None:
            if output_lock is not None:
                with output_lock:
                    action()
            else:
                action()

        removed: list[PlaybackDevice] = []

        def collect_removed() -> None:
            active = [device for device, _, _, _, _, _, _, _ in output_streams]
            removed.extend(routed_devices_no_longer_desired(active, desired_targets))

        mutate_outputs(collect_removed)
        for device in removed:
            mutate_outputs(
                lambda device=device: self._detach_output_device(
                    device, output_streams, controller=controller
                )
            )

        all_bt = list_wasapi_playback_devices(self._pa, bluetooth_only=True)
        resolved_azimuths = resolve_speaker_azimuths(
            desired_targets, all_bt, default_output_name, calibration
        )

        def apply_azimuths() -> None:
            azimuth_by_index.update(resolved_azimuths)
            self._sync_live_azimuth_overrides(config, desired_targets, azimuth_by_index)

        mutate_outputs(apply_azimuths)

        pending_devices: list[PlaybackDevice] = []

        def collect_pending() -> None:
            active = [device for device, _, _, _, _, _, _, _ in output_streams]
            pending_devices.extend(targets_not_yet_routed(active, desired_targets))

        mutate_outputs(collect_pending)
        for device in pending_devices:
            print(f"Hot-plugged: [{device.index}] {device.name}", flush=True)
            live_routed = self._live_routed_targets(output_streams)
            prepared_stream = self._prepare_output_stream(
                device,
                capture_rate,
                config.chunk_frames,
                warnings,
                calibration,
                controller=controller,
                fallback_queue=fallback_queue,
                fallback_buffer_min=fallback_buffer_min,
                azimuth_deg=azimuth_by_index.get(device.index, 0.0),
                routed_targets=live_routed,
                lip_sync=config.lip_sync,
            )
            if prepared_stream is None:
                continue

            def append_stream(entry: OutputStream = prepared_stream) -> None:
                output_streams.append(entry)

            mutate_outputs(append_stream)

        def update_waiting_flag() -> None:
            if not output_streams and config.hotplug:
                if not self._waiting_for_devices:
                    print("Waiting for Bluetooth devices...", flush=True)
                    self._waiting_for_devices = True
            else:
                self._waiting_for_devices = False

        mutate_outputs(update_waiting_flag)

    def _dispatch_chunk(
        self,
        source: np.ndarray,
        capture_rate: int,
        output_streams: list[OutputStream],
        output_lock: threading.Lock,
        *,
        use_spatial_panning: bool,
        use_content_split: bool,
        max_surround_separation: bool,
        calibration: CalibrationProfile | None,
        azimuth_by_index: dict[int, float],
        count_neural_chunk: bool = True,
        controller: AdaptiveRouteController | None = None,
        speech_aware: bool = True,
    ) -> None:
        with output_lock:
            outputs = list(output_streams)
            azimuth_snapshot = dict(azimuth_by_index)
        if not outputs:
            return

        speech_profile = None
        speech_likelihood = 0.0
        overlay_steps = 0
        if controller is not None and speech_aware and controller.speech_aware:
            speech_profile = controller.speech.pick_profile()

        signatures = {
            (output_rate, out_channels)
            for _, out_channels, output_rate, _, _, _, _, _ in outputs
        }
        payload_cache = build_payload_cache(source, capture_rate, signatures)
        failed_devices: list[PlaybackDevice] = []
        failed_indexes: set[int] = set()
        live_indices = self._live_dispatch_indices(outputs)
        learn_slot = 0
        if self._neural_engine is not None and live_indices:
            self._neural_engine.begin_chunk(source, count_toward_cadence=count_neural_chunk)
            if self._neural_engine.chunks_processed > 0:
                learn_slot = (self._neural_engine.chunks_processed - 1) % len(live_indices)
            set_learn_context = getattr(
                self._neural_engine,
                "set_learn_context",
                None,
            )
            if callable(set_learn_context):
                set_learn_context(learn_slot, len(live_indices))
        if (
            controller is not None
            and speech_aware
            and controller.speech_aware
            and live_indices
        ):
            speech_hint = None
            if self._neural_engine is not None:
                hint_lookup = getattr(self._neural_engine, "current_speech_hint", None)
                if callable(hint_lookup):
                    speech_hint = hint_lookup()
            speech_likelihood = controller.speech.observe_source_chunk(
                source,
                speech_hint=speech_hint,
            )
        try:
            for speaker_index, (
                device,
                out_channels,
                output_rate,
                _,
                writer,
                azimuth_deg,
                profile,
                align_state,
            ) in enumerate(outputs):
                if writer.failed_error is not None:
                    if device.index not in failed_indexes:
                        failed_indexes.add(device.index)
                        failed_devices.append(device)
                    continue
                payload = payload_cache.get((output_rate, out_channels), b"")
                if not payload:
                    continue
                azimuth = azimuth_snapshot.get(device.index, azimuth_deg)
                apply_pan = use_spatial_panning and not max_surround_separation
                if apply_pan and self._neural_engine is not None:
                    role = surround_role_from_azimuth(azimuth)
                    if should_skip_spatial_pan_for_role(role):
                        apply_pan = False
                if apply_pan:
                    payload = apply_azimuth_pan_to_payload(payload, azimuth, out_channels)
                if self._neural_engine is not None:
                    live_pos = live_indices.index(speaker_index)
                    allow_learn = live_pos == learn_slot
                    payload = self._neural_engine.apply_to_payload(
                        payload,
                        azimuth,
                        out_channels,
                        use_matrix_fallback=max_surround_separation,
                        matrix_strength=1.0,
                        allow_learn=allow_learn,
                    )
                elif max_surround_separation:
                    payload = apply_surround_matrix_to_payload(
                        payload,
                        azimuth,
                        out_channels,
                        strength=1.0,
                    )
                elif use_content_split:
                    payload = apply_content_split_to_payload(payload, azimuth, out_channels)
                onnx_stems = None
                if self._neural_engine is not None:
                    stem_lookup = getattr(self._neural_engine, "current_onnx_stems", None)
                    if callable(stem_lookup):
                        onnx_stems = stem_lookup()
                onnx_stems_active = onnx_stems is not None
                neural_handles_dialogue = onnx_stems_active
                upstream_content_split = (
                    max_surround_separation
                    or use_content_split
                    or self._neural_engine is not None
                )
                speech_telemetry_active = (
                    controller is not None
                    and speech_aware
                    and controller.speech_aware
                    and controller.speech.enabled
                )
                if speech_telemetry_active:
                    if (
                        onnx_stems_active
                        and onnx_stems is not None
                        and onnx_stems.speech is not None
                    ):
                        controller.speech.observe_stem_routed_leak(
                            onnx_stems.speech,
                            azimuth,
                            payload,
                            out_channels,
                        )
                    else:
                        controller.speech.observe_routed_leak(
                            source,
                            azimuth,
                            payload,
                            out_channels,
                        )
                if (
                    speech_profile is not None
                    and speech_likelihood > 0.2
                    and not neural_handles_dialogue
                ):
                    if self._neural_engine is not None:
                        overlay_steps = self._neural_engine.overlay_steps
                    payload = apply_speech_route_to_payload(
                        payload,
                        azimuth,
                        out_channels,
                        speech_profile,
                        speech_likelihood,
                        overlay_steps=overlay_steps,
                        blend_content_split=not upstream_content_split,
                    )
                payload = align_state.process_payload(payload, output_rate, out_channels)
                if calibration is not None:
                    level_db = calibration.level_db_for(device.name)
                    payload = apply_level_trim_to_payload(payload, level_db, out_channels)
                if profile.compression != "none":
                    payload = compress_payload(payload, profile.compression, out_channels)
                if not self._writer_still_bound(
                    device,
                    writer,
                    output_streams,
                    output_lock,
                ):
                    continue
                writer.submit(payload)
                if writer.failed_error is not None and device.index not in failed_indexes:
                    failed_indexes.add(device.index)
                    failed_devices.append(device)
        finally:
            if self._neural_engine is not None and live_indices:
                self._neural_engine.end_chunk()

        if failed_devices:
            with output_lock:
                for device in failed_devices:
                    self._detach_output_device(
                        device,
                        output_streams,
                        reason="write failure",
                        controller=controller,
                    )

    def route(self, config: RouteConfig) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Bluetooth surround routing is only supported on Windows.")
        if config.chunk_frames <= 0:
            raise ValueError("chunk_frames must be greater than zero.")
        if config.hotplug_interval_sec <= 0:
            raise ValueError("hotplug_interval_sec must be greater than zero.")

        loopback = self._resolve_loopback(config)
        bound_echo_source_name = self._echo_source_name(config, loopback)
        bound_default_output_name = self._wasapi_default_output_name()
        targets = self._desired_targets(config, bound_echo_source_name)
        if not targets:
            raise RuntimeError(
                "No Bluetooth speakers available to route. Connect at least two "
                "Bluetooth speakers, set Windows default to one of them, then run "
                "`bt-surround list`."
            )

        capture_rate = int(loopback["defaultSampleRate"])
        capture_channels = int(loopback["maxInputChannels"])
        if capture_channels <= 0:
            capture_channels = 2

        calibration = self._resolve_calibration(config)
        self._route_shutting_down = False
        if calibration is not None:
            resolved = resolve_calibration_file(config.calibration_path)
            source = resolved or config.calibration_path or "calibration.json"
            print(
                f"Echolocation alignment: {source} ({len(calibration.speakers)} speakers)",
                flush=True,
            )

        print(f"Capture: {loopback['name']} @ {capture_rate} Hz, {capture_channels} ch", flush=True)
        queue_depth, buffer_min = routing_buffer_tuning(config)
        latency_ms = estimate_routing_latency_ms(config, capture_rate)
        profile = "low-latency" if config.low_latency else "stable"
        print(
            f"Routing profile: {profile} (~{latency_ms:.0f} ms mirrored delay; "
            "Windows default speaker stays direct/instant).",
            flush=True,
        )

        if config.use_spatial_panning and not config.max_surround_separation:
            print(
                "Spatial panning: ON — routed speakers get per-position L/R mixes.",
                flush=True,
            )
        if config.max_surround_separation:
            print(
                "Surround matrix: MAX — 5.1-style channel separation "
                "(center=dialogue, rear=decorrelated ambience).",
                flush=True,
            )
        elif config.use_content_split:
            print(
                "Content split: ON — front speakers favor dialogue, sides favor ambience.",
                flush=True,
            )
        if config.use_adaptive_stream:
            print(
                "Adaptive stream: ON — Thompson sampling picks per-speaker bandwidth "
                "(chunk/compression) with the Windows default as prior; alignment "
                "nudges keep routed speakers in sync with that main Bluetooth speaker.",
                flush=True,
            )
        if config.speech_aware_routing and config.use_adaptive_stream:
            print(
                "Speech-at-work: ON — second Thompson branch gates dialogue on rear/side "
                "speakers and exchanges peer comments with the bandwidth bandit using "
                "neural overlay telemetry.",
                flush=True,
            )
        if config.lip_sync:
            print(
                "Lip-sync: ON — minimal mirrored delay; adaptive trim never adds "
                "echo delay when buffers are under pressure.",
                flush=True,
            )

        self._activate_neural_engine(config)
        clear_route_stop(config.stop_file_path)
        self._overlay_last_autosave_time = time.monotonic()

        controller = AdaptiveRouteController(
            enabled=config.use_adaptive_stream,
            lip_sync=config.lip_sync,
            speech_aware=config.speech_aware_routing and config.use_adaptive_stream,
        )
        controller.speech.enabled = config.speech_aware_routing and config.use_adaptive_stream
        fallback_queue, fallback_buffer_min = routing_buffer_tuning(config)

        capture_stream = None
        output_streams: list[OutputStream] = []
        warnings: list[str] = []
        all_bluetooth_devices = list_wasapi_playback_devices(self._pa, bluetooth_only=True)
        azimuth_by_index = resolve_speaker_azimuths(
            targets,
            all_bluetooth_devices,
            bound_default_output_name,
            calibration,
        )
        self._sync_live_azimuth_overrides(config, targets, azimuth_by_index)

        try:
            capture_stream = self._pa.open(
                format=self._pa.get_format_from_width(2),
                channels=capture_channels,
                rate=capture_rate,
                frames_per_buffer=config.chunk_frames,
                input=True,
                input_device_index=loopback["index"],
            )
            if not capture_stream.is_active():
                capture_stream.start_stream()

            for device_index, device in enumerate(targets):
                if device_index > 0:
                    time.sleep(BT_DEVICE_OPEN_DELAY_SEC)
                live_routed = self._live_routed_targets(output_streams)
                self._attach_output_device(
                    device,
                    capture_rate,
                    config.chunk_frames,
                    output_streams,
                    warnings,
                    calibration,
                    controller=controller,
                    fallback_queue=fallback_queue,
                    fallback_buffer_min=fallback_buffer_min,
                    azimuth_deg=azimuth_by_index.get(device.index, 0.0),
                    routed_targets=live_routed,
                    lip_sync=config.lip_sync,
                )

            attached_indexes = {entry[0].index for entry in output_streams}
            missing_targets = [
                device for device in targets if device.index not in attached_indexes
            ]
            if missing_targets:
                print(
                    "Retrying Bluetooth outputs that failed to open on the first pass...",
                    flush=True,
                )
                for device in missing_targets:
                    time.sleep(BT_DEVICE_OPEN_DELAY_SEC * 2)
                    live_routed = self._live_routed_targets(output_streams)
                    self._attach_output_device(
                        device,
                        capture_rate,
                        config.chunk_frames,
                        output_streams,
                        warnings,
                        calibration,
                        controller=controller,
                        fallback_queue=fallback_queue,
                        fallback_buffer_min=fallback_buffer_min,
                        azimuth_deg=azimuth_by_index.get(device.index, 0.0),
                        routed_targets=live_routed,
                        lip_sync=config.lip_sync,
                    )

            if not output_streams:
                details = "\n  ".join(warnings) if warnings else "No additional details."
                raise RuntimeError(f"Failed to open any Bluetooth output devices.\n  {details}")

            if warnings and not config.hotplug:
                print("Warnings:", flush=True)
                for warning in warnings:
                    print(f"  {warning}", flush=True)

            print("Routing active. Press Ctrl+C to stop.", flush=True)
            if config.hotplug:
                print(
                    f"Hot-plug enabled: checking for new Bluetooth devices every "
                    f"{config.hotplug_interval_sec:g}s.",
                    flush=True,
                )
            if calibration is not None:
                print(
                    "Time alignment active (relative among mirrored speakers; "
                    "lip-sync avoids echo vs the direct default).",
                    flush=True,
                )
            if config.use_content_split and not config.max_surround_separation:
                print(
                    "Surround isolation: routed speakers use role-specific mixes; "
                    "Windows default carries front left/right stereo.",
                    flush=True,
                )
            print(
                "Tip: Bluetooth-only PC? Set Windows default to one BT speaker; "
                "the others are routed automatically. No PC speakers needed.",
                flush=True,
            )
            print(
                format_routing_health(
                    output_streams,
                    adaptive=config.use_adaptive_stream,
                ),
                flush=True,
            )
            self._print_overlay_learn_telemetry(config, idle_message=True)
            print(
                f"Direct (instant): {bound_default_output_name} — front left/right stereo",
                flush=True,
            )
            print(
                "Mirrored (loopback): "
                + ", ".join(device.name for device, *_ in output_streams),
                flush=True,
            )
            print(
                "Layout: routed speakers use stage azimuth (X2=center, GT909MF=rear). "
                "Drag speakers on the GUI grid to match your room.",
                flush=True,
            )
            print(
                "Play movies/music on the Windows default speaker above — "
                "routed speakers mirror that same output.",
                flush=True,
            )

            output_lock = threading.Lock()
            stop_capture = threading.Event()
            capture_stats = {"max_rms": 0.0}
            capture_stats_lock = threading.Lock()
            capture_error: list[BaseException] = []

            default_index = self._wasapi_default_output_index()

            print("Running speaker path checks...", flush=True)
            self._probe_routed_outputs(output_streams, config.chunk_frames)
            print(
                "If you did not hear tones on the routed speakers above, "
                "turn up their volume or use Test Tones in the GUI.",
                flush=True,
            )
            self._probe_loopback_mirror(
                capture_stream,
                capture_channels,
                capture_rate,
                default_index,
                config,
                output_streams,
                output_lock,
                calibration=calibration,
                azimuth_by_index=azimuth_by_index,
                controller=controller,
            )

            def capture_worker() -> None:
                try:
                    while not stop_capture.is_set():
                        raw = capture_stream.read(config.chunk_frames, exception_on_overflow=False)
                        frame_count = len(raw) // (2 * capture_channels)
                        if frame_count == 0:
                            continue
                        source = normalize_loopback_chunk(raw, capture_channels)
                        chunk_rms = capture_chunk_rms(source)
                        with capture_stats_lock:
                            capture_stats["max_rms"] = max(
                                capture_stats["max_rms"],
                                chunk_rms,
                            )
                        self._dispatch_chunk(
                            source,
                            capture_rate,
                            output_streams,
                            output_lock,
                            use_spatial_panning=config.use_spatial_panning,
                            use_content_split=config.use_content_split,
                            max_surround_separation=config.max_surround_separation,
                            calibration=calibration,
                            azimuth_by_index=azimuth_by_index,
                            controller=controller,
                            speech_aware=(
                                config.speech_aware_routing
                                and config.use_adaptive_stream
                            ),
                        )
                        if not self._route_shutting_down:
                            self._maybe_autosave_overlay(config)
                except BaseException as exc:
                    capture_error.append(exc)

            capture_thread = threading.Thread(
                target=capture_worker,
                name="bt-surround-capture",
                daemon=True,
            )
            capture_thread.start()

            last_hotplug_check = time.monotonic()
            last_azimuth_check = time.monotonic()
            last_silent_check = time.monotonic()
            last_health_check = time.monotonic()
            last_adapt_check = time.monotonic()
            azimuth_poll_interval = 0.2
            last_silent_warn = 0.0
            silent_check_interval = 5.0
            silent_warn_cooldown = 30.0
            health_check_interval = 15.0
            silent_rms_threshold = 120.0
            try:
                while capture_thread.is_alive():
                    if route_stop_requested(config.stop_file_path):
                        will_persist_overlay = (
                            config.continual_overlay
                            and config.overlay_persist
                            and self._neural_engine is not None
                        )
                        if will_persist_overlay:
                            print(
                                "Stop requested — saving overlay and shutting down...",
                                flush=True,
                            )
                        else:
                            print("Stop requested — shutting down...", flush=True)
                        self._route_shutting_down = True
                        stop_capture.set()
                        break
                    if capture_error:
                        raise capture_error[0]

                    with output_lock:
                        active_count = len(output_streams)
                    if active_count == 0:
                        if config.hotplug:
                            if not self._waiting_for_devices:
                                print("Waiting for Bluetooth devices...", flush=True)
                                self._waiting_for_devices = True
                        else:
                            raise RuntimeError(
                                "All Bluetooth output devices failed. Restart bt-surround route."
                            )

                    self._warn_if_capture_loopback_stale(config, loopback)

                    now = time.monotonic()
                    period_peak: float | None = None
                    if (
                        now - last_silent_check >= silent_check_interval
                        or now - last_health_check >= health_check_interval
                    ):
                        with capture_stats_lock:
                            period_peak = capture_stats["max_rms"]
                            capture_stats["max_rms"] = 0.0

                    if (
                        period_peak is not None
                        and now - last_silent_check >= silent_check_interval
                    ):
                        if (
                            active_count > 0
                            and period_peak < silent_rms_threshold
                            and now - last_silent_warn >= silent_warn_cooldown
                        ):
                            last_silent_warn = now
                            print(
                                format_silent_loopback_hint(
                                    self._wasapi_default_output_name()
                                ),
                                flush=True,
                            )
                        last_silent_check = now

                    if (
                        period_peak is not None
                        and now - last_health_check >= health_check_interval
                    ):
                        speech_label = None
                        if controller.speech_aware and controller.speech.enabled:
                            speech_label = controller.speech.pick_profile().display
                        with output_lock:
                            print(
                                format_routing_health(
                                    output_streams,
                                    adaptive=config.use_adaptive_stream,
                                    capture_max_rms=period_peak,
                                    speech_profile_label=speech_label,
                                ),
                                flush=True,
                            )
                        self._print_overlay_learn_telemetry(config)
                        last_health_check = now

                    if (
                        controller.enabled
                        and now - last_adapt_check >= ADAPT_INTERVAL_SEC
                    ):
                        last_adapt_check = now
                        pending_reattach: list[
                            tuple[PlaybackDevice, StreamProfile, StreamProfile]
                        ] = []
                        with output_lock:
                            adapt_targets = self._live_adapt_targets(
                                list(output_streams),
                            )
                        neural_context: NeuralBanditContext | None = None
                        if (
                            controller.speech_aware
                            and controller.speech.enabled
                            and adapt_targets
                        ):
                            speech_hint = controller.speech.last_neural_speech_hint()
                            if speech_hint is None and self._neural_engine is not None:
                                hint_lookup = getattr(
                                    self._neural_engine,
                                    "current_speech_hint",
                                    None,
                                )
                                if callable(hint_lookup):
                                    speech_hint = hint_lookup()
                            neural_context = NeuralBanditContext(
                                overlay_steps=(
                                    self._neural_engine.overlay_steps
                                    if self._neural_engine is not None
                                    else 0
                                ),
                                speech_hint=speech_hint,
                                overlay_aggressiveness=config.overlay_aggressiveness,
                            )
                            controller.speech.sync_peer_overlay_telemetry(
                                overlay_steps=neural_context.overlay_steps,
                                overlay_aggressiveness=neural_context.overlay_aggressiveness,
                            )
                        for (
                            device,
                            telemetry,
                            profile,
                            queued_chunks,
                            max_queued_chunks,
                        ) in adapt_targets:
                            new_profile, _ = controller.adapt_device(
                                device.index,
                                telemetry,
                                current_profile=profile,
                                queued_chunks=queued_chunks,
                                max_queued_chunks=max_queued_chunks,
                            )
                            if (
                                new_profile is not None
                                and new_profile.profile_id != profile.profile_id
                            ):
                                pending_reattach.append((device, new_profile, profile))
                        if (
                            controller.speech_aware
                            and controller.speech.enabled
                            and adapt_targets
                        ):
                            controller.speech.finalize_bandwidth_tick()
                            if neural_context is None:
                                neural_context = NeuralBanditContext(
                                    overlay_aggressiveness=config.overlay_aggressiveness,
                                )
                            new_speech_profile = controller.speech.adapt_tick(
                                neural_context,
                            )
                            if new_speech_profile is not None:
                                controller.speech.selector.set_active(
                                    new_speech_profile.profile_id,
                                )
                                print(
                                    "Speech-at-work: switched to "
                                    f"{new_speech_profile.display} profile.",
                                    flush=True,
                                )
                        elif controller.speech_aware and controller.speech.enabled:
                            controller.speech.reset_adapt_window()
                        for device, new_profile, previous_profile in pending_reattach:
                            with output_lock:
                                bound_writer = self._bound_writer_for_device(
                                    device,
                                    output_streams,
                                )
                                if (
                                    bound_writer is None
                                    or bound_writer.failed_error is not None
                                ):
                                    continue
                                live_targets = [
                                    target
                                    for target in self._live_routed_targets(
                                        output_streams
                                    )
                                    if target.index != device.index
                                ]
                            self._reattach_output_device(
                                device,
                                capture_rate,
                                config.chunk_frames,
                                output_streams,
                                warnings,
                                calibration,
                                controller,
                                new_profile,
                                azimuth_by_index,
                                previous_profile=previous_profile,
                                fallback_queue=fallback_queue,
                                fallback_buffer_min=fallback_buffer_min,
                                output_lock=output_lock,
                                routed_targets=live_targets,
                                lip_sync=config.lip_sync,
                            )

                    if (
                        config.azimuth_override_path
                        and now - last_azimuth_check >= azimuth_poll_interval
                    ):
                        last_azimuth_check = now
                        with output_lock:
                            active_devices = [
                                device for device, _, _, _, _, _, _, _ in output_streams
                            ]
                            if self._sync_live_azimuth_overrides(
                                config, active_devices, azimuth_by_index
                            ):
                                print("Live azimuth update applied.", flush=True)

                    if config.hotplug and now - last_hotplug_check >= config.hotplug_interval_sec:
                        last_hotplug_check = now
                        self._sync_hotplug_devices(
                            config,
                            capture_rate,
                            output_streams,
                            warnings,
                            calibration,
                            controller,
                            echo_source_name=bound_echo_source_name,
                            default_output_name=bound_default_output_name,
                            fallback_queue=fallback_queue,
                            fallback_buffer_min=fallback_buffer_min,
                            azimuth_by_index=azimuth_by_index,
                            output_lock=output_lock,
                        )
                        with output_lock:
                            if output_streams:
                                self._waiting_for_devices = False

                    interval_end = time.monotonic() + 0.2
                    while time.monotonic() < interval_end:
                        if route_stop_requested(config.stop_file_path):
                            self._route_shutting_down = True
                            stop_capture.set()
                            break
                        time.sleep(0.05)
                    if stop_capture.is_set():
                        break
            finally:
                stop_capture.set()
                if capture_stream is not None:
                    try:
                        if capture_stream.is_active():
                            capture_stream.stop_stream()
                    except (OSError, AttributeError):
                        pass
                    try:
                        capture_stream.close()
                    except OSError:
                        pass
                    capture_stream = None
                capture_thread.join(timeout=5.0)
                if capture_thread.is_alive():
                    print(
                        "Warning: capture thread did not stop within 5s; "
                        "closing streams anyway.",
                        flush=True,
                    )
                if capture_error:
                    raise capture_error[0]

        except KeyboardInterrupt:
            print("\nStopping router...")
        finally:
            self._route_shutting_down = True
            clear_route_stop(config.stop_file_path)
            if capture_stream is not None:
                try:
                    if capture_stream.is_active():
                        capture_stream.stop_stream()
                except (OSError, AttributeError):
                    pass
                try:
                    capture_stream.close()
                except OSError:
                    pass
            for _, _, _, stream, writer, _, _, _ in output_streams:
                writer.stop()
                stream.stop_stream()
                stream.close()
            self._deactivate_neural_engine(config, persist=True)

    def test_outputs(self, config: RouteConfig, seconds: float = 2.5) -> None:
        """Play short test tones on the default speaker and each routed target."""
        if sys.platform != "win32":
            raise RuntimeError("Bluetooth surround routing is only supported on Windows.")
        if seconds <= 0:
            raise ValueError("seconds must be greater than zero.")

        import math

        import pyaudiowpatch as pyaudio

        default_output_name = self._wasapi_default_output_name()
        loopback = self._resolve_loopback(config)
        echo_source_name = self._echo_source_name(config, loopback)
        targets = self._desired_targets(config, echo_source_name)
        if not targets:
            print(
                "Note: no additional Bluetooth speakers to route; "
                "testing the Windows default output only.",
                flush=True,
            )

        wasapi = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_index = int(wasapi["defaultOutputDevice"])

        print(self.explain_plan(config))
        print("", flush=True)
        print("Playing test tones (listen on each speaker):", flush=True)

        test_hz = [440.0, 523.0, 659.0, 784.0]
        speakers: list[tuple[str, int, float]] = [
            (default_output_name, default_index, test_hz[0]),
        ]
        for index, device in enumerate(targets):
            speakers.append((device.name, device.index, test_hz[(index + 1) % len(test_hz)]))

        for speaker_index, (label, device_index, hz) in enumerate(speakers):
            if speaker_index > 0:
                time.sleep(BT_TEST_DEVICE_GAP_SEC)
            info = self._pa.get_device_info_by_index(device_index)
            rate = int(info["defaultSampleRate"])
            channels = min(2, int(info["maxOutputChannels"]))
            frames = int(rate * seconds)
            tone = (
                np.sin(2 * math.pi * hz * np.arange(frames) / rate) * 0.45 * 32767
            ).astype(np.int16)
            if channels == 1:
                payload = tone.tobytes()
            else:
                payload = np.column_stack((tone, tone)).reshape(-1).tobytes()

            role = "default" if device_index == default_index else "routed"
            print(f"  [{device_index}] {label} ({role}) @ {int(hz)} Hz", flush=True)
            stream = None
            last_error: OSError | None = None
            for attempt in range(BT_DEVICE_OPEN_RETRIES + 1):
                try:
                    stream = self._pa.open(
                        format=self._pa.get_format_from_width(2),
                        channels=channels,
                        rate=rate,
                        output=True,
                        output_device_index=device_index,
                    )
                    last_error = None
                    break
                except OSError as exc:
                    last_error = exc
                    if attempt < BT_DEVICE_OPEN_RETRIES:
                        time.sleep(0.35 * (attempt + 1))
            if stream is None:
                print(
                    f"  Test tone failed on [{device_index}] {label}: {last_error}",
                    flush=True,
                )
                continue
            if not stream.is_active():
                stream.start_stream()
            stream.write(payload)
            stream.stop_stream()
            stream.close()
            time.sleep(BT_TEST_DEVICE_GAP_SEC)

        print("", flush=True)
        print(
            "If you heard tones on the default speaker but NOT on routed speakers, "
            "keep Start-BtSurround.bat open and run: bt-surround route",
            flush=True,
        )

    def diagnose(self, config: RouteConfig) -> int:
        """Open routed outputs and run speaker + loopback mirror checks (no long capture loop)."""
        if sys.platform != "win32":
            raise RuntimeError("Bluetooth surround routing is only supported on Windows.")

        import pyaudiowpatch as pyaudio

        loopback = self._resolve_loopback(config)
        echo_source_name = self._echo_source_name(config, loopback)
        targets = self._desired_targets(config, echo_source_name)
        if not targets:
            print(
                "Diagnose: no routed Bluetooth speakers (only the Windows default is connected).",
                flush=True,
            )
            return 1

        capture_rate = int(loopback["defaultSampleRate"])
        capture_channels = int(loopback["maxInputChannels"]) or 2
        calibration = self._resolve_calibration(config)
        default_output_name = self._wasapi_default_output_name()
        all_bluetooth_devices = list_wasapi_playback_devices(self._pa, bluetooth_only=True)
        azimuth_by_index = resolve_speaker_azimuths(
            targets,
            all_bluetooth_devices,
            default_output_name,
            calibration,
        )
        self._sync_live_azimuth_overrides(config, targets, azimuth_by_index)

        print(self.explain_plan(config))
        print("", flush=True)
        print(
            f"Direct (instant): {default_output_name}",
            flush=True,
        )
        print(
            "Mirrored (loopback): "
            + ", ".join(device.name for device in targets),
            flush=True,
        )
        print(
            "Only the Windows default plays movies directly. "
            "Other speakers mirror whatever plays on that default.",
            flush=True,
        )
        print("", flush=True)

        self._activate_neural_engine(config, announce=False)
        if self._neural_engine is not None:
            self._neural_engine.set_learning_enabled(False)

        controller = AdaptiveRouteController(
            enabled=config.use_adaptive_stream,
            lip_sync=config.lip_sync,
            speech_aware=config.speech_aware_routing and config.use_adaptive_stream,
        )
        controller.speech.enabled = config.speech_aware_routing and config.use_adaptive_stream
        fallback_queue, fallback_buffer_min = routing_buffer_tuning(config)
        output_streams: list[OutputStream] = []
        warnings: list[str] = []
        capture_stream = None

        try:
            capture_stream = self._pa.open(
                format=self._pa.get_format_from_width(2),
                channels=capture_channels,
                rate=capture_rate,
                frames_per_buffer=config.chunk_frames,
                input=True,
                input_device_index=loopback["index"],
            )
            if not capture_stream.is_active():
                capture_stream.start_stream()

            for device in targets:
                live_routed = self._live_routed_targets(output_streams)
                self._attach_output_device(
                    device,
                    capture_rate,
                    config.chunk_frames,
                    output_streams,
                    warnings,
                    calibration,
                    controller=controller,
                    fallback_queue=fallback_queue,
                    fallback_buffer_min=fallback_buffer_min,
                    azimuth_deg=azimuth_by_index.get(device.index, 0.0),
                    routed_targets=live_routed,
                    lip_sync=config.lip_sync,
                )

            if not output_streams:
                details = "\n  ".join(warnings) if warnings else "No additional details."
                raise RuntimeError(f"Failed to open routed outputs.\n  {details}")

            output_lock = threading.Lock()
            wasapi = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_index = int(wasapi["defaultOutputDevice"])

            print("Step 1/2 — routed speaker check (no loopback):", flush=True)
            self._probe_routed_outputs(output_streams, config.chunk_frames)
            print("", flush=True)
            print("Step 2/2 — loopback mirror check (tone on default → routed):", flush=True)
            peak_rms = self._probe_loopback_mirror(
                capture_stream,
                capture_channels,
                capture_rate,
                default_index,
                config,
                output_streams,
                output_lock,
                calibration=calibration,
                azimuth_by_index=azimuth_by_index,
                controller=controller,
            )

            ok_outputs = all(
                writer.telemetry.successful_writes > 0 and writer.failed_error is None
                for _, _, _, _, writer, _, _, _ in output_streams
            )
            if ok_outputs and peak_rms >= 500.0:
                print("", flush=True)
                print(
                    "Diagnose: OK — routed speakers and loopback mirror path are working.",
                    flush=True,
                )
                return 0

            print("", flush=True)
            print("Diagnose: FAILED — see messages above.", flush=True)
            if not ok_outputs:
                print(
                    "Routed outputs did not accept audio. Check Bluetooth volume and pairing.",
                    flush=True,
                )
            elif peak_rms < 500.0:
                print(
                    format_silent_loopback_hint(default_output_name),
                    flush=True,
                )
            return 1
        finally:
            self._deactivate_neural_engine(config, persist=False)
            if capture_stream is not None:
                try:
                    if capture_stream.is_active():
                        capture_stream.stop_stream()
                except (OSError, AttributeError):
                    pass
                try:
                    capture_stream.close()
                except OSError:
                    pass
            for _, _, _, stream, writer, _, _, _ in output_streams:
                writer.stop()
                stream.stop_stream()
                stream.close()

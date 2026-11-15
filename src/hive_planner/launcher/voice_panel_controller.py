"""Controller between the launcher Voice panel and the Voice_Bot runtime (T042 slice 5a).

The panel (`voice_panel.py`) only forwards clicks. This module holds the decisions:
which hop a control calls, and what message a refusal shows. The hops are the
local bridge (`voice-bot bridge`, bearer token + `bridge.json`) and the config
read (`.hive/voice-bot/config.json`).

Slice 5a scope:
- mic start is refused with a clear code (never a fake "listening" state);
  real record -> submit is slice 5d.
- end-call interrupts playback when `audio_enabled`, then calls the bridge
  `POST /v1/call/end` when a bridge is live.
- the menu reports bridge and speech config and starts or stops the bridge (slice 5c).
  The launcher owns only the bridge process it started; it never kills one it did not start.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from hive_planner.config import RepoPaths
from hive_planner.launcher.__main__ import _console_python
from hive_planner.launcher.service import _hidden_subprocess_kwargs
from hive_planner.voice_bot import (
    TERMINAL_TASK_STATES,
    VoiceBotError,
    load_voice_bot_config,
    save_voice_bot_config,
)
from hive_planner.voice_bridge import bridge_endpoint_path, bridge_is_live, bridge_token_path
from hive_planner.voice_moshi import SoundDeviceIO, moshi_call_gate, talk

# Stable codes the panel and tests match on. Do not reword without updating tests.
CODE_NO_PROJECT = "no_project"
CODE_STT_NOT_CONFIGURED = "stt_not_configured"
CODE_MIC_CAPTURE_NOT_WIRED = "mic_capture_not_wired"
CODE_BRIDGE_NOT_RUNNING = "bridge_not_running"
CODE_CALL_ENDED = "call_ended"
CODE_BRIDGE_UNREACHABLE = "bridge_unreachable"
CODE_EMPTY_INSTRUCTION = "empty_instruction"
CODE_SUBMITTED = "submitted"
CODE_CONFIG_INVALID = "config_invalid"
CODE_INPUT_DEVICE_SAVED = "input_device_saved"
CODE_BRIDGE_STARTED = "bridge_started"
CODE_BRIDGE_STOPPED = "bridge_stopped"
CODE_BRIDGE_ALREADY_RUNNING = "bridge_already_running"
CODE_BRIDGE_START_FAILED = "bridge_start_failed"
CODE_BRIDGE_NOT_OWNED = "bridge_not_owned"

PostFn = Callable[[str, dict[str, Any]], tuple[int, dict[str, Any]]]
SpawnFn = Callable[[list[str], str], Any]

REQUEST_TIMEOUT_S = 1.0
# Spoken routes run STT on the bridge; the first load of the pinned model takes a few seconds.
SPOKEN_REQUEST_TIMEOUT_S = 120.0
BRIDGE_START_TIMEOUT_S = 10.0
BRIDGE_START_POLL_S = 0.1
BRIDGE_STOP_TIMEOUT_S = 5.0
# T042 slice 5e: the greeting follows the last typed task. Poll the bridge, then stop at a terminal state.
TASK_POLL_S = 2.0
TASK_WATCH_LIMIT_S = 600.0
TASK_LABEL_WORKING = "Working on it..."
TASK_LABEL_APPROVAL = "Waiting for your approval..."


def bridge_command(root: Path) -> list[str]:
    """Command line for the bridge CLI. It stays up until its stdin closes."""
    return [_console_python(), "-m", "hive_planner", "--root", str(root.resolve()), "voice-bot", "bridge"]


def _spawn_bridge_process(argv: list[str], cwd: str) -> subprocess.Popen:
    """Start the bridge with stdin held open (the clean-stop signal). No console window."""
    return subprocess.Popen(
        argv,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
        **_hidden_subprocess_kwargs(),
    )


@dataclass(frozen=True)
class BridgeResult:
    ok: bool
    code: str
    message: str


@dataclass(frozen=True)
class EndCallResult:
    ok: bool
    code: str
    message: str


@dataclass(frozen=True)
class InputDeviceResult:
    ok: bool
    code: str
    input_device: str | None
    message: str = ""


@dataclass(frozen=True)
class SubmitResult:
    ok: bool
    code: str
    message: str
    task_id: str | None = None


class VoicePanelController:
    """Maps panel controls to runtime hops. `post` is injectable so tests need no socket."""

    def __init__(
        self,
        project_root_getter: Callable[[], Path | None],
        *,
        post: PostFn | None = None,
        spawn: SpawnFn | None = None,
        recorder: Any = None,
        talk_fn: Callable[..., dict[str, Any]] | None = None,
        io_factory: Callable[[str | None], Any] | None = None,
        listen_gate: Callable[[Any], str | None] | None = None,
    ) -> None:
        self._project_root_getter = project_root_getter
        self._post_fn = post or self._post_to_bridge
        self._spawn = spawn or _spawn_bridge_process
        # Slice 5d: injected recorder with start() and stop() -> bytes. None means no real capture.
        self._recorder = recorder
        self._pending_audio: bytes | None = None
        # Moshi call (voice_layer "moshi"): the mic button runs one duplex call on a worker thread.
        # All three are injectable so tests need no socket and no audio device.
        self._talk_fn = talk_fn or talk
        self._io_factory = io_factory or (lambda device: SoundDeviceIO(device=device))
        # The call gate keeps its handshaken socket for the talk() that follows (R37 handover).
        self._listen_gate = listen_gate or moshi_call_gate
        self._talk_thread: threading.Thread | None = None
        self._talk_stop: threading.Event | None = None
        self._talk_result: dict[str, Any] = {}
        self._moshi_approval_buf = ""
        # Notices from a Moshi call (refusals, utterance results), last five. Written by worker threads.
        self.call_notices: list[str] = []
        self._notice_lock = threading.Lock()
        # Only the bridge process this launcher started. Never a bridge started elsewhere.
        self._bridge_proc: Any = None
        self.mic_active = False
        # Last instruction the bridge accepted this session; the side dialog prefills it (in memory only).
        self.last_instruction: str | None = None
        # T042 slice 5e: the last typed task (task_id, context_snapshot_id) and the greeting label it drives.
        # The watcher thread writes the label; the panel reads it on the UI thread.
        self._task_ref: tuple[str, str] | None = None
        self._task_label: str | None = None
        self._task_stop: threading.Event | None = None

    # --- helpers --------------------------------------------------------

    def project_root(self) -> Path | None:
        root = self._project_root_getter()
        return Path(root) if root else None

    def _paths(self) -> RepoPaths | None:
        root = self.project_root()
        return RepoPaths(root=root.resolve()) if root else None

    def _config_state(self) -> tuple[Any, str | None]:
        """Return (config, error). A broken config.json is reported, never silently defaulted."""
        paths = self._paths()
        if paths is None:
            return None, None
        try:
            return load_voice_bot_config(paths), None
        except VoiceBotError as exc:
            return None, str(exc)

    def _config(self):
        return self._config_state()[0]

    def bridge_running(self) -> bool:
        paths = self._paths()
        return bool(paths is not None and bridge_is_live(paths))

    def _post_to_bridge(self, route: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """Authenticated POST to the live bridge. Returns (0, error) instead of raising."""
        paths = self._paths()
        if paths is None:
            return 0, {"error": CODE_NO_PROJECT}
        try:
            endpoint = json.loads(bridge_endpoint_path(paths).read_text(encoding="utf-8"))
            token = bridge_token_path(paths).read_text(encoding="utf-8").strip()
            url = f"http://{endpoint['host']}:{int(endpoint['port'])}{route}"
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return 0, {"error": CODE_BRIDGE_UNREACHABLE, "message": str(exc)}
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        )
        # Spoken routes transcribe on the bridge (STT takes seconds, and the first model load longer),
        # so they get the spoken timeout. Other routes keep the short one.
        timeout = SPOKEN_REQUEST_TIMEOUT_S if route.endswith("/spoken") else REQUEST_TIMEOUT_S
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return int(resp.status), json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8") or "{}")
            except ValueError:
                payload = {}
            return int(exc.code), payload
        except (OSError, ValueError) as exc:
            return 0, {"error": CODE_BRIDGE_UNREACHABLE, "message": str(exc)}

    def _get_from_bridge(self, route: str, extra: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
        """Authenticated GET to the live bridge. Returns (0, error) instead of raising."""
        paths = self._paths()
        if paths is None:
            return 0, {"error": CODE_NO_PROJECT}
        try:
            endpoint = json.loads(bridge_endpoint_path(paths).read_text(encoding="utf-8"))
            token = bridge_token_path(paths).read_text(encoding="utf-8").strip()
            query = urllib.parse.urlencode({"workspace": str(paths.root), **(extra or {})})
            url = f"http://{endpoint['host']}:{int(endpoint['port'])}{route}?{query}"
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return 0, {"error": CODE_BRIDGE_UNREACHABLE, "message": str(exc)}
        req = urllib.request.Request(url, method="GET", headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
                return int(resp.status), json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8") or "{}")
            except ValueError:
                payload = {}
            return int(exc.code), payload
        except (OSError, ValueError) as exc:
            return 0, {"error": CODE_BRIDGE_UNREACHABLE, "message": str(exc)}

    def _pending_approval(self) -> dict[str, Any] | None:
        """The bridge's pending approval view, or None when none is pending or the bridge cannot say."""
        status, payload = self._get_from_bridge("/v1/approval")
        if status == 200 and payload.get("pending") is True:
            return payload
        return None

    def _workspace_body(self) -> dict[str, Any]:
        root = self.project_root()
        return {"workspace": str(root.resolve()) if root else ""}

    # --- panel controls -------------------------------------------------

    def status(self) -> dict[str, Any]:
        cfg, config_error = self._config_state()
        return {
            "project": str(self.project_root() or ""),
            "bridge_running": self.bridge_running(),
            "stt_provider": cfg.stt_provider if cfg else None,
            "voice_layer": cfg.voice_layer if cfg else "moshi",
            "audio_enabled": bool(cfg.audio_enabled) if cfg else False,
            "edits_enabled": bool(cfg.edits_enabled) if cfg else False,
            "input_device": cfg.input_device if cfg else None,
            "config_error": config_error,
        }

    def on_mic(self, start: bool) -> str | None:
        """Mic toggle. Return None when accepted, or a refusal message the panel shows.

        Stop always succeeds. Start is refused until a real capture exists, so the
        panel never shows "listening" without a recording.
        """
        if not start:
            if self._talk_thread is not None:
                # Moshi call: the mic button ends the duplex call. No WAV is recorded or sent.
                self.mic_active = False
                return self._stop_moshi_call()
            if self._recorder is not None and self.mic_active:
                self._pending_audio = self._recorder.stop()
            self.mic_active = False
            audio, self._pending_audio = self._pending_audio, None
            if audio is None:
                return None
            return self._submit_recording(audio)
        if self.project_root() is None:
            return "Open a project first. The mic needs an active project."
        cfg = self._config()
        if cfg is not None and cfg.voice_layer == "moshi":
            return self._start_moshi_call(cfg)
        if cfg is None or not cfg.stt_provider:
            return (
                f"Mic off: speech input is not configured ({CODE_STT_NOT_CONFIGURED}). "
                "Set stt_provider in .hive/voice-bot/config.json, or type your instruction."
            )
        if self._recorder is None:
            return f"Mic capture is not wired yet ({CODE_MIC_CAPTURE_NOT_WIRED})."
        try:
            self._recorder.start()
        except OSError as exc:
            return f"Mic off: could not start recording ({exc})."
        self.mic_active = True
        return None

    def _start_moshi_call(self, cfg: Any) -> str | None:
        """Start one duplex Moshi call on a worker thread (R36, R37). Refused when no handshake.

        The gate runs first, so a dead server is a refusal the panel shows, not a silent "listening".
        Live `0x02` text is passed to `_on_moshi_text` so a pending approval can be answered by voice.
        """
        if self._talk_thread is not None and self._talk_thread.is_alive():
            self.mic_active = True
            return None
        stop = threading.Event()
        io = self._io_factory(cfg.input_device)
        self._talk_stop = stop
        self._talk_result = {}
        self._moshi_approval_buf = ""

        def _run() -> None:
            # The gate may start the Moshi server and wait for it (minutes on a cold start). It runs
            # here, not on the UI thread, so the panel stays responsive. A refusal is recorded as a
            # notice and the mic turns off; it is never shown as a live call.
            try:
                code = self._listen_gate(cfg)
                if code:
                    self._talk_result = {"error": code}
                    self.mic_active = False  # state first, then the notice that reports it
                    self._add_notice(
                        f"Mic off: Moshi is not reachable ({code}). Type your instruction, or check the Moshi install."
                    )
                    return
                self._talk_result = dict(
                    self._talk_fn(
                        cfg.moshi_url,
                        io,
                        stop=stop,
                        on_text=self._on_moshi_text,
                        on_utterance=self._on_moshi_utterance,
                    )
                )
            except VoiceBotError as exc:
                self._talk_result = {"error": str(exc)}
            except Exception as exc:  # noqa: BLE001 - a worker fault must reach the panel, not kill the app
                self._talk_result = {"error": f"moshi_call_failed: {exc}"}

        self.mic_active = True  # set before the worker starts, so a refusal can clear it
        self._talk_thread = threading.Thread(target=_run, name="moshi-call", daemon=True)
        self._talk_thread.start()
        return None

    def _add_notice(self, note: str) -> None:
        """Keep the last five notices (refusals and results from worker threads)."""
        with self._notice_lock:
            self.call_notices.append(note)
            del self.call_notices[:-5]

    def _on_moshi_text(self, text: str) -> bool:
        """R36: Moshi `0x02` text may reply to a pending R6 approval. It is never a new task.

        Moshi often streams a phrase across several frames, so fragments are joined while
        the same request is pending. Returns True when the line was sent to that request
        (including a re-prompt). Returns False when nothing is pending, so the line stays
        transcript-only.
        """
        clean = (text or "").strip()
        if not clean:
            return False
        pending = self._pending_approval()
        if pending is None:
            self._moshi_approval_buf = ""
            return False
        buf = f"{self._moshi_approval_buf} {clean}".strip()
        self._moshi_approval_buf = buf
        body = {
            **self._workspace_body(),
            "task_id": str(pending.get("task_id") or ""),
            "request_id": str(pending.get("request_id") or ""),
            "text": buf,
        }
        _status, payload = self._post_fn("/v1/reply", body)
        if payload.get("status") in (
            "approved", "denied", "answered", "stale", "stale_approval",
            "no_pending_approval", "task_mismatch", "not_delivered",
        ):
            self._moshi_approval_buf = ""
        return True

    def _on_moshi_utterance(self, pcm: Any, sample_rate: int) -> None:
        """T056 speech-to-task: one finished user utterance becomes a task or an approval reply.

        Runs on the mic thread, so the STT round trip happens on a worker thread. The utterance goes
        through `_submit_recording` (the same route as the WAV mic path): the bridge transcribes it
        with the pinned STT provider and creates a task. Moshi text is not used here (R36).
        """
        from hive_planner.voice_moshi import pcm_to_wav_bytes  # lazy: numpy only when a call runs

        wav = pcm_to_wav_bytes(pcm, sample_rate)

        def _send() -> None:
            try:
                refusal = self._submit_recording(wav)
            except Exception as exc:  # noqa: BLE001 - a worker fault must reach the notice list
                refusal = f"Utterance was not sent ({exc})."
            self._add_notice(refusal or "Heard you. Sent to the bridge.")

        threading.Thread(target=_send, name="moshi-utterance", daemon=True).start()

    def _stop_moshi_call(self) -> str | None:
        """Stop the Moshi call and wait for its worker. Returns an error message if the call failed."""
        thread, stop = self._talk_thread, self._talk_stop
        if stop is not None:
            stop.set()
        if thread is not None:
            thread.join(timeout=5.0)
        self._talk_thread = None
        self._talk_stop = None
        self._moshi_approval_buf = ""
        error = str(self._talk_result.get("error") or "")
        self._talk_result = {}
        if error:
            return f"Call ended with an error ({error})."
        return None

    def _submit_recording(self, audio: bytes) -> str | None:
        """Slice 5d: write the WAV under the workspace, then POST its relative path to /v1/submit/spoken.

        Returns None when the bridge accepted it, else a refusal message the panel shows.
        """
        root = self.project_root()
        if root is None:
            return "Open a project first. The recording was not sent."
        if not self.bridge_running():
            return f"Bridge is not running ({CODE_BRIDGE_NOT_RUNNING}). The recording was not sent."
        request_id = str(uuid.uuid4())
        rel_dir = Path(".hive") / "voice-bot" / "recordings"
        wav_rel = rel_dir / f"{request_id}.wav"
        wav_abs = root.resolve() / wav_rel
        try:
            wav_abs.parent.mkdir(parents=True, exist_ok=True)
            wav_abs.write_bytes(audio)
        except OSError as exc:
            return f"Could not save the recording: {exc}"
        # A pending approval takes the recording as its reply (R6); otherwise it is a new instruction.
        pending = self._pending_approval()
        if pending is not None:
            body = {
                **self._workspace_body(),
                "task_id": str(pending.get("task_id") or ""),
                "request_id": str(pending.get("request_id") or ""),
                "wav_path": wav_rel.as_posix(),
            }
            status, payload = self._post_fn("/v1/reply/spoken", body)
            # Accepted replies (approved, denied, answered) return None. A re-prompt or an
            # undelivered answer, and any bridge refusal, is shown so the user knows nothing ran.
            if status == 200 and payload.get("status") not in ("reprompt", "not_delivered"):
                return None
            code = payload.get("error", payload.get("status", status))
            return str(
                payload.get("message") or payload.get("spoken")
                or f"Approval reply was not accepted ({code})."
            )
        body = {
            **self._workspace_body(),
            "client_request_id": request_id,
            "wav_path": wav_rel.as_posix(),
            "mode": "ask",
        }
        status, payload = self._post_fn("/v1/submit/spoken", body)
        if status == 200:
            return None
        code = str(payload.get("error", CODE_BRIDGE_UNREACHABLE))
        return str(payload.get("message") or payload.get("spoken") or f"Bridge did not accept the recording ({code}).")

    def on_end(self) -> EndCallResult:
        """Hang-up: mic off, interrupt playback when audio is on, then end the call on the bridge."""
        self.mic_active = False
        self._stop_task_watch()  # the greeting stops following the task when the call ends
        if self._talk_thread is not None:
            self._stop_moshi_call()  # hang-up always stops the Moshi call, even without a bridge
        if self.project_root() is None:
            return EndCallResult(False, CODE_NO_PROJECT, "No project open. Nothing to end.")
        if not self.bridge_running():
            return EndCallResult(False, CODE_BRIDGE_NOT_RUNNING, "Bridge is not running. Start the bridge first.")
        cfg = self._config()
        if cfg is not None and cfg.audio_enabled:
            self._post_fn("/v1/playback/interrupt", self._workspace_body())
        status, payload = self._post_fn("/v1/call/end", self._workspace_body())
        if status == 200:
            return EndCallResult(True, CODE_CALL_ENDED, "Call ended.")
        code = str(payload.get("error", CODE_BRIDGE_UNREACHABLE))
        return EndCallResult(False, code, str(payload.get("message", "Bridge did not end the call.")))

    def submit_typed(self, instruction: str) -> SubmitResult:
        """Side button (typed fallback, slice 5b): POST one instruction to the live bridge.

        Never reports success without a 200 from the bridge. A queued submit is still a success
        (the bridge accepted it); `task_id` is None in that case.
        """
        text = (instruction or "").strip()
        if self.project_root() is None:
            return SubmitResult(False, CODE_NO_PROJECT, "Open a project first. Nothing was sent.")
        if not text:
            return SubmitResult(False, CODE_EMPTY_INSTRUCTION, "Nothing to send. Type an instruction first.")
        if not self.bridge_running():
            return SubmitResult(
                False, CODE_BRIDGE_NOT_RUNNING, "Bridge is not running. Start the bridge first. Nothing was sent."
            )
        body = {
            **self._workspace_body(),
            "instruction": text,
            "client_request_id": str(uuid.uuid4()),
            "mode": "ask",
        }
        status, payload = self._post_fn("/v1/submit", body)
        if status == 200:
            self.last_instruction = text
            task_id = str(payload.get("task_id") or "") or None
            context_id = str(payload.get("context_snapshot_id") or "")
            if task_id and context_id:
                self._start_task_watch(task_id, context_id)
            if payload.get("status") == "queued":
                message = str(payload.get("spoken") or "Queued behind the active task.")
            elif task_id:
                message = f"Sent. Task {task_id} started."
            else:
                message = "Sent."
            return SubmitResult(True, CODE_SUBMITTED, message, task_id)
        code = str(payload.get("error", CODE_BRIDGE_UNREACHABLE))
        message = str(payload.get("message") or payload.get("spoken") or "Bridge did not accept the instruction.")
        return SubmitResult(False, code, message)

    # --- T042 slice 5e: greeting follows the last typed task -----------------

    def task_text(self) -> str | None:
        """Greeting label for the panel, or None for the normal greeting. Read on the UI thread."""
        return self._task_label

    def _start_task_watch(self, task_id: str, context_id: str) -> None:
        """Watch one task on a daemon thread. A new submit replaces the previous watch."""
        self._stop_task_watch()
        stop = threading.Event()
        self._task_stop = stop
        self._task_ref = (task_id, context_id)
        self._task_label = TASK_LABEL_WORKING
        threading.Thread(
            target=self._watch_task, args=(task_id, context_id, stop), name="task-watch", daemon=True
        ).start()

    def _stop_task_watch(self) -> None:
        stop, self._task_stop = self._task_stop, None
        if stop is not None:
            stop.set()
        self._task_label = None

    def _set_task_label(self, stop: threading.Event, label: str | None) -> None:
        """Write the label only while this watch is still the current one (a new submit wins)."""
        if self._task_stop is stop and not stop.is_set():
            self._task_label = label

    def _watch_task(self, task_id: str, context_id: str, stop: threading.Event) -> None:
        """Poll GET /v1/task until a terminal state, an error, a stop, or the watch limit."""
        deadline = time.monotonic() + TASK_WATCH_LIMIT_S
        while not stop.is_set() and time.monotonic() < deadline:
            status, view = self._get_from_bridge(
                "/v1/task", {"task_id": task_id, "context_snapshot_id": context_id}
            )
            state = str(view.get("state") or "")
            if status != 200 or state in TERMINAL_TASK_STATES:
                # Terminal, unknown task, or bridge gone: the greeting goes back to normal.
                self._set_task_label(stop, None)
                return
            self._set_task_label(stop, TASK_LABEL_APPROVAL if state == "awaiting_approval" else TASK_LABEL_WORKING)
            stop.wait(TASK_POLL_S)
        self._set_task_label(stop, None)

    def set_input_device(self, name: str | None) -> InputDeviceResult:
        """T042b: save `input_device` to config.json, then return the value reloaded from disk.

        Blank or whitespace saves null. A broken config.json is refused so it is never overwritten.
        """
        paths = self._paths()
        if paths is None:
            return InputDeviceResult(False, CODE_NO_PROJECT, None, "Open a project before choosing a microphone.")
        cfg, err = self._config_state()
        if err is not None or cfg is None:
            return InputDeviceResult(
                False,
                CODE_CONFIG_INVALID,
                None,
                f"config.json is invalid; fix it before saving the microphone: {err}",
            )
        value = (name or "").strip() or None
        try:
            save_voice_bot_config(paths, replace(cfg, input_device=value))
            reloaded = load_voice_bot_config(paths).input_device
        except VoiceBotError as exc:
            return InputDeviceResult(False, CODE_CONFIG_INVALID, None, str(exc))
        return InputDeviceResult(True, CODE_INPUT_DEVICE_SAVED, reloaded, "Microphone saved.")

    def start_bridge(self) -> BridgeResult:
        """Menu (slice 5c): start `voice-bot bridge` for the project and wait until it answers.

        Refuses when no project is open or a live bridge already exists. Reports failure if the
        process exits or does not answer within BRIDGE_START_TIMEOUT_S. Never reports success
        without a live endpoint.
        """
        root = self.project_root()
        if root is None:
            return BridgeResult(False, CODE_NO_PROJECT, "Open a project first. The bridge needs a project.")
        if self.bridge_running():
            return BridgeResult(False, CODE_BRIDGE_ALREADY_RUNNING, "A bridge is already running for this project.")
        try:
            proc = self._spawn(bridge_command(root), str(root.resolve()))
        except OSError as exc:
            return BridgeResult(False, CODE_BRIDGE_START_FAILED, f"Could not start the bridge: {exc}")
        self._bridge_proc = proc
        deadline = time.monotonic() + BRIDGE_START_TIMEOUT_S
        while True:
            exit_code = proc.poll()
            if exit_code is not None:
                self._bridge_proc = None
                return BridgeResult(
                    False,
                    CODE_BRIDGE_START_FAILED,
                    f"The bridge exited during start (exit code {exit_code}). Check the project's voice-bot setup.",
                )
            if self.bridge_running():
                return BridgeResult(True, CODE_BRIDGE_STARTED, "Bridge started.")
            if time.monotonic() >= deadline:
                self._stop_owned(kill=True)
                return BridgeResult(False, CODE_BRIDGE_START_FAILED, "The bridge did not answer in time. Stopped it.")
            time.sleep(BRIDGE_START_POLL_S)

    def stop_bridge(self) -> BridgeResult:
        """Menu (slice 5c): clean stop of the bridge this launcher started (close stdin, then wait)."""
        if self._bridge_proc is not None:
            self._stop_owned(kill=False)
            return BridgeResult(True, CODE_BRIDGE_STOPPED, "Bridge stopped.")
        if self.bridge_running():
            return BridgeResult(
                False,
                CODE_BRIDGE_NOT_OWNED,
                "This bridge was not started from the launcher. Stop it from where it was started.",
            )
        return BridgeResult(False, CODE_BRIDGE_NOT_RUNNING, "Bridge is not running.")

    def _stop_owned(self, *, kill: bool) -> None:
        proc, self._bridge_proc = self._bridge_proc, None
        if proc is None:
            return
        if kill:
            proc.kill()
            proc.wait()
            return
        try:
            proc.stdin.close()
        except (OSError, ValueError):
            pass
        try:
            proc.wait(timeout=BRIDGE_STOP_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    def back_target(self) -> str:
        """Header back arrow: focus returns to the main shell. The panel stays visible."""
        return "main_shell"

    def menu_text(self) -> str:
        s = self.status()
        lines = [
            f"Project: {s['project'] or 'none'}",
            f"Bridge: {'running' if s['bridge_running'] else 'not running'}",
            f"Voice layer (voice_layer): {s['voice_layer']}",
            f"Speech input (stt_provider): {s['stt_provider'] or 'off (typed only)'}",
            f"Audio playback (audio_enabled): {'on' if s['audio_enabled'] else 'off'}",
        ]
        if s["config_error"]:
            lines.append(f"Config error (fix config.json; speech values above are not loaded): {s['config_error']}")
        return "\n".join(lines)


"""Hive-owned Moshi server lifecycle (OD-1 revised 2026-11-14, operator choice: Hive starts it).

When `moshi_autostart` is true and `moshi_url` points at loopback, a listen-gate probe that finds
no handshake starts `python -m moshi.server --host H --port P` as a child process and waits for
the handshake. The child is stopped at interpreter exit. Non-loopback URLs are never started.

The model still runs in its own process: the upstream server owns the GPU and the weights. Hive
only starts, waits for, and stops that process. It never imports the model.
"""

from __future__ import annotations

import atexit
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
DEFAULT_PORT = 8998
READY_TIMEOUT_S = 240.0  # first start loads the model; the operator's GPU sets the real time
POLL_S = 1.0
STOP_TIMEOUT_S = 10.0


def server_command(url: str) -> list[str]:
    """The exact command Hive runs for a loopback `moshi_url`."""
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or DEFAULT_PORT
    return [sys.executable, "-m", "moshi.server", "--host", host, "--port", str(port)]


Q8_LAUNCHER = Path(__file__).resolve().parents[2] / "scripts" / "moshi_q8_server.py"
Q8_DEVICE = "cuda:0"


def q8_server_command(url: str, cfg: Any) -> list[str]:
    """The command Hive runs for a loopback `moshi_url` when the four q8 config keys are set (A3c).

    Runs `scripts/moshi_q8_server.py` as a child; the model loads in that child, never in HIVE.
    """
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or DEFAULT_PORT
    return [
        sys.executable, str(Q8_LAUNCHER),
        "--host", host, "--port", str(port), "--device", Q8_DEVICE,
        "--q8", cfg.moshi_q8_weights,
        "--mimi", cfg.moshi_mimi_weights,
        "--tokenizer", cfg.moshi_tokenizer,
        "--config", cfg.moshi_model_config,
    ]


def is_loopback(url: str) -> bool:
    return (urlparse(url).hostname or "") in LOOPBACK_HOSTS


class MoshiServerProcess:
    """Owns at most one child Moshi server started by Hive."""

    def __init__(
        self,
        *,
        popen: Callable[..., subprocess.Popen] = subprocess.Popen,
        command: Callable[[str], list[str]] = server_command,
        ready_timeout_s: float = READY_TIMEOUT_S,
        poll_s: float = POLL_S,
        log_path: Path | None = None,
    ) -> None:
        self._popen = popen
        self._command = command
        self._ready_timeout_s = ready_timeout_s
        self._poll_s = poll_s
        # None sends child output to DEVNULL. Set, stdout and stderr append to this file (R37).
        self._log_path = log_path
        self._proc: subprocess.Popen | None = None

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def ensure(
        self,
        url: str,
        is_ready: Callable[[str], bool],
        launch: Callable[[str], list[str]] | None = None,
    ) -> str | None:
        """Return None once `is_ready(url)` is true, starting the server if needed.

        `launch` overrides the default command for this start only (A3c: the q8 launcher).
        Otherwise return a refusal code: `moshi_unreachable` (remote URL, never started),
        `moshi_server_exited` (child died during startup), or `moshi_server_timeout`.
        """
        if is_ready(url):
            return None
        if not is_loopback(url):
            return "moshi_unreachable"
        if not self.running:
            log = None
            out: Any = subprocess.DEVNULL
            if self._log_path is not None:
                self._log_path.parent.mkdir(parents=True, exist_ok=True)
                log = open(self._log_path, "ab")  # noqa: SIM115 - child keeps its own handle
                out = log
            kwargs: dict = {"stdout": out, "stderr": out}
            if sys.platform == "win32":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            command = launch(url) if launch is not None else self._command(url)
            try:
                self._proc = self._popen(command, **kwargs)
            finally:
                if log is not None:
                    log.close()
        deadline = time.monotonic() + self._ready_timeout_s
        while time.monotonic() < deadline:
            if self._proc is None or self._proc.poll() is not None:
                self._proc = None
                return "moshi_server_exited"
            if is_ready(url):
                return None
            time.sleep(self._poll_s)
        return "moshi_server_timeout"

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(STOP_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            proc.kill()


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_LOG = REPO_ROOT / ".hive" / "voice-bot" / "moshi-server.log"
SERVER = MoshiServerProcess(log_path=SERVER_LOG)
atexit.register(lambda: SERVER.stop())

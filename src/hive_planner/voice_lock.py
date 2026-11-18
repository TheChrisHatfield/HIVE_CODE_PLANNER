"""Cross-process runner lock for Voice_Bot (closes the bridge start race).

Exactly one process may own a `VoiceTaskRunner` for a repo at a time. The lock is an OS
byte-range / flock lock on `.hive/voice-bot/runner.lock`, held from runner construction
until `close()`. The OS releases it when the owning process exits, so a crashed runner
never leaves a stale lock behind.

Why it matters: the bridge loads `state.json` once when it starts. Without this lock a
standalone `voice-bot turn` that is already running could keep writing the same file.
With it, the bridge cannot start a runner while another process holds the lock, and
`voice-bot init` cannot replace state under a live runner.
"""

from __future__ import annotations

import errno
import os
import sys
from pathlib import Path
from typing import IO, Any

from hive_planner.config import RepoPaths
from hive_planner.voice_bot import VOICE_BOT_DIR, VoiceBotError

LOCK_FILE = "runner.lock"
# msvcrt.LK_NBLCK uses EACCES; flock LOCK_NB uses EAGAIN/EWOULDBLOCK.
_LOCK_BUSY = {errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK, errno.EBUSY}
if hasattr(errno, "EDEADLK"):
    _LOCK_BUSY.add(errno.EDEADLK)
if hasattr(errno, "EDEADLOCK"):
    _LOCK_BUSY.add(errno.EDEADLOCK)


class RunnerLockHeld(VoiceBotError):
    """Another process (a bridge or a standalone turn) owns this repo's voice-bot runner."""


def runner_lock_path(paths: RepoPaths) -> Path:
    return paths.root / VOICE_BOT_DIR / LOCK_FILE


class RunnerLock:
    """Non-blocking exclusive lock on the runner lock file. Call `release()` to free it."""

    def __init__(self, paths: RepoPaths) -> None:
        self.path = runner_lock_path(paths)
        self._handle: IO[bytes] | None = None

    @property
    def held(self) -> bool:
        return self._handle is not None

    def acquire(self) -> None:
        if self._handle is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+b")  # noqa: SIM115 - held for the runner's lifetime
        try:
            _lock_nonblocking(handle)
            self._handle = handle
        except OSError as exc:
            handle.close()
            if exc.errno not in _LOCK_BUSY:
                raise
            raise RunnerLockHeld(
                "a voice bridge or standalone turn is already running for this repo; "
                f"runner lock held: {self.path}"
            ) from exc
        except BaseException:
            handle.close()
            raise

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        try:
            _unlock(handle)
        finally:
            handle.close()

    def __enter__(self) -> RunnerLock:
        self.acquire()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.release()


def _lock_nonblocking(handle: IO[bytes]) -> None:
    handle.seek(0)
    if sys.platform == "win32":
        import msvcrt

        # Lock one byte at offset 0. The file may be empty, so make sure byte 0 exists.
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle: IO[bytes]) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

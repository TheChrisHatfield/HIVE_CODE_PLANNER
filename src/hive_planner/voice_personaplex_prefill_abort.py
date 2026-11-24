"""PP-T16 / PP17: Hive abort closes the in-flight handshake so child ``is_alive`` stops prefill."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any, Mapping

HANDSHAKE_ABORT_SLICE_S = 0.2
SC_PP10_LIVE = "HIVE_PP_SC_PP10_LIVE"
SC_PP10_SLOT1 = "HIVE_PP_SC_PP10_SLOT1_FREED"


class HandshakeAborted(Exception):
    """Hive abort/hold-drop while waiting for ``0x00`` (7B prefill still running)."""


class HandshakeTimedOut(Exception):
    """Handshake recv never returned ``0x00`` before the connect timeout."""


def websocket_prefill_alive(close_flag: bool, ws_closed: bool) -> bool:
    """NVIDIA ``is_alive`` first clause: False when Hive closed the socket (PP17)."""
    return not (bool(close_flag) or bool(ws_closed))


def recv_handshake_until(
    *,
    recv: Callable[[float], Any],
    close: Callable[[], None],
    abort: Callable[[], bool] | None,
    timeout: float,
    slice_s: float = HANDSHAKE_ABORT_SLICE_S,
    now: Callable[[], float] | None = None,
) -> Any:
    """Poll ``abort`` between short recv slices. Abort/timeout always ``close()`` the socket."""
    clock = now or time.monotonic
    deadline = clock() + timeout
    while True:
        if abort is not None and abort():
            try:
                close()
            except Exception:
                pass
            raise HandshakeAborted("moshi_unreachable")
        remaining = deadline - clock()
        if remaining <= 0:
            try:
                close()
            except Exception:
                pass
            raise HandshakeTimedOut("moshi_unreachable")
        try:
            return recv(min(slice_s, remaining))
        except TimeoutError:
            continue


def sc_pp10_live_passed(environ: Mapping[str, str] | None = None) -> bool:
    """Live 7B prefill abort (SC-PP10) is fail-closed without both operator flags."""
    env = os.environ if environ is None else environ
    return env.get(SC_PP10_LIVE) == "1" and env.get(SC_PP10_SLOT1) == "1"

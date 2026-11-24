"""PP-T16 / PP17: Hive abort closes handshake WS so child is_alive frees slot 1."""

from __future__ import annotations

import ast
import threading
import time
from pathlib import Path

import pytest

from hive_planner.voice_bot import VoiceBotError
from hive_planner.voice_personaplex_prefill_abort import (
    HandshakeAborted,
    SC_PP10_LIVE,
    SC_PP10_SLOT1,
    recv_handshake_until,
    sc_pp10_live_passed,
    websocket_prefill_alive,
)

_ROOT = Path(__file__).resolve().parents[1]
_SERVER = _ROOT / "code-improvements" / "personaplex-migrate" / "moshi" / "moshi" / "server.py"
_CHILD_ALIVE = _ROOT / "code-improvements" / "personaplex-migrate" / "moshi" / "moshi" / "hive_is_alive.py"


def test_pp_t16_child_is_alive_false_when_hive_closes_socket():
    import importlib.util

    spec = importlib.util.spec_from_file_location("hive_is_alive", _CHILD_ALIVE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.websocket_prefill_alive(False, False) is True
    assert mod.websocket_prefill_alive(False, True) is False
    assert mod.websocket_prefill_alive(True, False) is False
    assert websocket_prefill_alive(False, True) is False


def test_pp_t16_server_passes_is_alive_into_prefill():
    src = _SERVER.read_text(encoding="utf-8")
    assert "websocket_prefill_alive" in src
    assert "step_system_prompts_async" in src
    assert "is_alive=is_alive" in src
    tree = ast.parse(src)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "step_system_prompts_async"
    ]
    assert calls
    kws = {kw.arg for kw in calls[0].keywords}
    assert "is_alive" in kws


def test_pp_t16_recv_abort_closes_socket_before_0x00():
    closed = {"n": 0}

    def recv(_timeout: float) -> bytes:
        raise TimeoutError()

    def close() -> None:
        closed["n"] += 1

    with pytest.raises(HandshakeAborted):
        recv_handshake_until(
            recv=recv,
            close=close,
            abort=lambda: True,
            timeout=15.0,
            now=lambda: 0.0,
        )
    assert closed["n"] == 1
    assert websocket_prefill_alive(False, closed["n"] > 0) is False


def test_pp_t16_slot_1_lock_frees_when_is_alive_drops():
    lock = threading.Lock()
    alive = {"v": True}
    finished = {"ok": False}

    def prefill() -> None:
        with lock:
            while websocket_prefill_alive(False, not alive["v"]):
                time.sleep(0.01)
            finished["ok"] = True

    alive["v"] = True  # ws still open → prefill holds slot 1
    t = threading.Thread(target=prefill)
    t.start()
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and lock.acquire(blocking=False):
        lock.release()
        time.sleep(0.01)
    assert not lock.acquire(blocking=False)
    alive["v"] = False  # Hive close → is_alive False
    t.join(timeout=2.0)
    assert finished["ok"]
    assert lock.acquire(timeout=0.5)
    lock.release()


def test_pp_t16_connect_handshake_abort_closes_ws(monkeypatch) -> None:
    import hive_planner.voice_moshi as vm

    closed = {"n": 0}

    class _WS:
        def recv(self, timeout: float = None):  # noqa: ARG002
            time.sleep(min(0.05, timeout or 0.05))
            raise TimeoutError()

        def close(self) -> None:
            closed["n"] += 1

    monkeypatch.setattr(vm, "_load_websocket_client", lambda: (Exception, lambda *a, **k: _WS()))
    n = {"i": 0}

    def abort() -> bool:
        n["i"] += 1
        return n["i"] > 1

    with pytest.raises(VoiceBotError, match="moshi_unreachable"):
        vm._connect_handshake("ws://127.0.0.1:1/api/chat", timeout=2.0, abort=abort)
    assert closed["n"] >= 1


def test_pp_t16_drop_held_session_closes_socket():
    import hive_planner.voice_moshi as vm

    closed = {"n": 0}

    class _Sess:
        closed = False

        def close(self) -> None:
            closed["n"] += 1
            self.closed = True

    sess = _Sess()
    with vm._HOLD_LOCK:
        vm._HELD = ("ws://127.0.0.1:8998/api/chat", sess, time.monotonic())
    vm.drop_held_session()
    assert closed["n"] == 1
    assert websocket_prefill_alive(False, sess.closed) is False


def test_pp_t16_sc_pp10_fail_closed_without_live_7b():
    assert sc_pp10_live_passed({}) is False
    assert sc_pp10_live_passed({SC_PP10_LIVE: "1"}) is False
    assert sc_pp10_live_passed({SC_PP10_LIVE: "1", SC_PP10_SLOT1: "1"}) is True

"""T003 — ACP JSON-RPC adapter: persistent process, response routing, disconnect detection.

These run against a real child process (tests/fixtures/acp_fake_server.py) over
stdio, so framing, routing, and disconnect paths are exercised end to end.
"""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from hive_planner.voice_acp import (
    AcpClient,
    AcpDisconnected,
    AcpRemoteError,
    AcpTimeout,
)

FAKE_SERVER = Path(__file__).parent / "fixtures" / "acp_fake_server.py"


@pytest.fixture
def client():
    permission_calls: list[tuple[str, object]] = []

    def handler(method, params):
        permission_calls.append((method, params))
        return {"outcome": "approved"}

    c = AcpClient([sys.executable, str(FAKE_SERVER)], server_request_handler=handler)
    c.permission_calls = permission_calls  # type: ignore[attr-defined]
    try:
        yield c
    finally:
        c.close()


def test_persistent_process_serves_multiple_requests(client: AcpClient) -> None:
    pid = client.pid
    assert client.request("initialize", {})["protocolVersion"] == 1
    assert client.request("echo", {"n": 1}) == {"n": 1}
    assert client.request("echo", {"n": 2}) == {"n": 2}
    assert client.pid == pid
    assert client.is_connected()


def test_concurrent_requests_route_to_their_own_ids(client: AcpClient) -> None:
    results: dict[int, object] = {}

    def call(n: int) -> None:
        results[n] = client.request("echo", {"n": n}, timeout=10)

    threads = [threading.Thread(target=call, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
    assert results == {n: {"n": n} for n in range(8)}


def test_notification_and_server_request_during_prompt(client: AcpClient) -> None:
    result = client.request("session/prompt", {"text": "hi"}, timeout=10)

    # The server's permission request was answered by the handler and the
    # reply reached the server, which echoed it back in the prompt result.
    assert result == {
        "stopReason": "end_turn",
        "permission": {"outcome": "approved"},
    }
    assert client.permission_calls == [  # type: ignore[attr-defined]
        ("session/request_permission", {"action": "write"})
    ]
    update = client.notifications.get(timeout=5)
    assert update is not None
    assert update["method"] == "session/update"
    assert update["params"]["update"] == "started"


def test_null_jsonrpc_error_code_does_not_kill_the_reader(client: AcpClient) -> None:
    from hive_planner.voice_acp import _Pending

    pending = _Pending()
    with client._state_lock:
        client._pending["null-err"] = pending
    client._route_response({"id": "null-err", "error": {"code": None, "message": "nope"}})
    assert pending.event.is_set()
    assert isinstance(pending.error, AcpRemoteError)
    assert pending.error.code == 0
    assert client.request("echo", {"ok": True}, timeout=10) == {"ok": True}


def test_close_does_not_raise_when_child_wait_times_out(monkeypatch) -> None:
    c = AcpClient([sys.executable, str(FAKE_SERVER)])
    real_wait = c._proc.wait
    real_kill = c._proc.kill

    def boom_wait(timeout=None):
        raise subprocess.TimeoutExpired(cmd="agent", timeout=timeout or 0)

    monkeypatch.setattr(c._proc, "wait", boom_wait)
    monkeypatch.setattr(c._proc, "kill", lambda: None)
    try:
        c.close()
    finally:
        try:
            real_kill()
            real_wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass


def test_remote_error_is_surfaced_not_swallowed(client: AcpClient) -> None:
    with pytest.raises(AcpRemoteError) as info:
        client.request("fail", {}, timeout=10)
    assert info.value.code == -32000
    assert info.value.message == "boom"
    assert client.is_connected()


def test_timeout_does_not_kill_the_session(client: AcpClient) -> None:
    with pytest.raises(AcpTimeout):
        client.request("slow", {"seconds": 1.5}, timeout=0.2)
    # Late reply arrives and is dropped; the session still answers new requests.
    time.sleep(1.6)
    assert client.request("echo", {"ok": True}, timeout=10) == {"ok": True}


def test_unknown_server_request_gets_method_not_found() -> None:
    c = AcpClient([sys.executable, str(FAKE_SERVER)])  # no handler registered
    try:
        # session/prompt triggers a server request; with no handler the client
        # answers method-not-found, so the server reads an error object as its reply.
        result = c.request("session/prompt", {}, timeout=10)
        assert result["permission"] is None
    finally:
        c.close()


def test_crash_is_detected_and_fails_pending_request() -> None:
    c = AcpClient([sys.executable, str(FAKE_SERVER)])
    try:
        with pytest.raises(AcpDisconnected):
            c.request("crash", {}, timeout=10)
        assert not c.is_connected()
        assert "provider_disconnected" in (c.disconnect_reason() or "")
        with pytest.raises(AcpDisconnected):
            c.request("echo", {}, timeout=2)
    finally:
        c.close()


def test_close_fails_an_in_flight_request() -> None:
    c = AcpClient([sys.executable, str(FAKE_SERVER)])
    errors: list[BaseException] = []

    def hang() -> None:
        try:
            c.request("slow", {"seconds": 8}, timeout=15)
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=hang)
    worker.start()
    time.sleep(0.2)
    c.close()
    worker.join(timeout=6)
    assert not worker.is_alive()
    assert errors and isinstance(errors[0], AcpDisconnected)


def test_terminate_then_close_emits_one_disconnect_sentinel() -> None:
    c = AcpClient([sys.executable, str(FAKE_SERVER)])
    try:
        assert c.request("initialize", {}, timeout=10)["protocolVersion"] == 1
        c.terminate()
    finally:
        c.close()
    sentinels = 0
    while True:
        try:
            item = c.notifications.get_nowait()
        except queue.Empty:
            break
        if item is None:
            sentinels += 1
    assert sentinels == 1


def test_terminate_kills_child_and_fails_pending() -> None:
    c = AcpClient([sys.executable, str(FAKE_SERVER)])
    try:
        assert c.request("initialize", {}, timeout=10)["protocolVersion"] == 1
        c.terminate()
        with pytest.raises(AcpDisconnected):
            c.request("echo", {}, timeout=5)
        assert not c.is_connected()
        assert "provider_terminated" in (c.disconnect_reason() or "")
    finally:
        c.close()


def test_killed_process_is_detected_on_next_request() -> None:
    c = AcpClient([sys.executable, str(FAKE_SERVER)])
    try:
        assert c.request("initialize", {}, timeout=10)["protocolVersion"] == 1
        c._proc.kill()  # simulate external termination
        c._proc.wait(timeout=5)
        with pytest.raises(AcpDisconnected):
            c.request("echo", {}, timeout=5)
        assert not c.is_connected()
    finally:
        c.close()


def test_missing_binary_raises_oserror() -> None:
    with pytest.raises(OSError):
        AcpClient(["definitely-not-a-real-agent-binary-xyz"])


def test_real_agent_acp_initialize_round_trip() -> None:
    """Live smoke against the installed Cursor Agent CLI (skipped when absent)."""
    from hive_planner.voice_acp import open_agent_acp
    from hive_planner.voice_bot import resolve_cursor_agent_cli

    info = resolve_cursor_agent_cli()
    if not info["available"] or not info["acp_subcommand"]:
        pytest.skip("Cursor Agent CLI with `acp` subcommand not installed")
    c = open_agent_acp(str(info["path"]), cwd=str(Path.cwd()))
    try:
        result = c.request("initialize", {"protocolVersion": 1, "clientCapabilities": {}}, timeout=60)
        assert result["protocolVersion"] == 1
        assert c.is_connected()
    finally:
        c.close()

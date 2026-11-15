"""Hive-owned Moshi server lifecycle (OD-1 revised 2026-11-14, Option A).

Real child processes and real loopback websockets. The only stand-in is `moshi_stub_server.py`
in place of `python -m moshi.server`, which needs a GPU model. Nothing here loads a model.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import hive_planner.voice_moshi as vm
from hive_planner.voice_bot import VoiceBotConfig, VoiceBotError, voice_bot_config_path
from hive_planner.voice_moshi_server import MoshiServerProcess, is_loopback, server_command

STUB = str(Path(__file__).with_name("moshi_stub_server.py"))


def _closed_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _stub_command(url: str) -> list[str]:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return [sys.executable, STUB, "--host", parsed.hostname or "127.0.0.1", "--port", str(parsed.port)]


@pytest.fixture
def stub_server(monkeypatch):
    """Swap the module SERVER for one that runs the stub instead of moshi.server."""
    server = MoshiServerProcess(command=_stub_command, ready_timeout_s=30.0, poll_s=0.1)
    monkeypatch.setattr(vm, "SERVER", server)
    try:
        yield server
    finally:
        server.stop()


def test_server_command_is_moshi_server_on_the_url_host_and_port():
    cmd = server_command("ws://127.0.0.1:9123/api/chat")
    assert cmd[1:] == ["-m", "moshi.server", "--host", "127.0.0.1", "--port", "9123"]


def test_only_loopback_urls_are_started():
    assert is_loopback("ws://127.0.0.1:8998/api/chat")
    assert is_loopback("ws://localhost:8998/api/chat")
    assert not is_loopback("ws://10.0.0.5:8998/api/chat")


def test_gate_starts_server_and_passes_when_handshake_arrives(stub_server):
    port = _closed_port()
    url = f"ws://127.0.0.1:{port}/api/chat"
    cfg = VoiceBotConfig(voice_layer="moshi", moshi_url=url, moshi_autostart=True)

    assert moshi_gate(cfg) is None
    assert stub_server.running is True

    stub_server.stop()
    assert stub_server.running is False


def test_gate_reuses_an_already_running_server(stub_server):
    port = _closed_port()
    url = f"ws://127.0.0.1:{port}/api/chat"
    cfg = VoiceBotConfig(voice_layer="moshi", moshi_url=url, moshi_autostart=True)

    assert moshi_gate(cfg) is None
    first = stub_server._proc
    assert moshi_gate(cfg) is None  # handshake already answers: no second spawn
    assert stub_server._proc is first


def test_two_sequential_open_sessions_both_connect(stub_server):
    """R37 share point (15d): back-to-back sessions on one server each get a handshake, no sleep."""
    url = f"ws://127.0.0.1:{_closed_port()}/api/chat"
    cfg = VoiceBotConfig(voice_layer="moshi", moshi_url=url, moshi_autostart=True)
    assert moshi_gate(cfg) is None  # starts the stub; the probe closes its own socket

    first = vm.open_session(url)
    first.close()
    second = vm.open_session(url)  # immediately after the first session closed
    assert first is not second
    assert second.closed is False
    second.close()


def test_child_that_exits_during_startup_is_refused(monkeypatch):
    server = MoshiServerProcess(
        command=lambda _url: [sys.executable, "-c", "import sys; sys.exit(3)"],
        ready_timeout_s=10.0,
        poll_s=0.05,
    )
    monkeypatch.setattr(vm, "SERVER", server)
    cfg = VoiceBotConfig(
        voice_layer="moshi", moshi_url=f"ws://127.0.0.1:{_closed_port()}/api/chat", moshi_autostart=True
    )
    assert moshi_gate(cfg) == "moshi_server_exited"
    assert server.running is False


def test_child_that_never_becomes_ready_times_out(monkeypatch):
    server = MoshiServerProcess(
        command=lambda _url: [sys.executable, "-c", "import time; time.sleep(60)"],
        ready_timeout_s=0.5,
        poll_s=0.1,
    )
    monkeypatch.setattr(vm, "SERVER", server)
    cfg = VoiceBotConfig(
        voice_layer="moshi", moshi_url=f"ws://127.0.0.1:{_closed_port()}/api/chat", moshi_autostart=True
    )
    try:
        assert moshi_gate(cfg) == "moshi_server_timeout"
    finally:
        server.stop()
    assert server.running is False


def test_remote_url_is_never_started(monkeypatch):
    calls: list[object] = []
    server = MoshiServerProcess(popen=lambda *a, **k: calls.append(a) or None)
    monkeypatch.setattr(vm, "SERVER", server)
    monkeypatch.setattr(vm, "open_session", _raise_unreachable)
    cfg = VoiceBotConfig(voice_layer="moshi", moshi_url="ws://10.0.0.5:8998/api/chat", moshi_autostart=True)

    assert moshi_gate(cfg) == "moshi_unreachable"
    assert calls == []


def test_autostart_off_never_starts_a_server(monkeypatch):
    calls: list[object] = []
    server = MoshiServerProcess(popen=lambda *a, **k: calls.append(a) or None)
    monkeypatch.setattr(vm, "SERVER", server)
    cfg = VoiceBotConfig(
        voice_layer="moshi", moshi_url=f"ws://127.0.0.1:{_closed_port()}/api/chat", moshi_autostart=False
    )
    assert moshi_gate(cfg) == "moshi_unreachable"
    assert calls == []


def test_missing_package_is_not_auto_fixed(monkeypatch):
    calls: list[object] = []
    server = MoshiServerProcess(popen=lambda *a, **k: calls.append(a) or None)
    monkeypatch.setattr(vm, "SERVER", server)
    monkeypatch.setattr(vm, "moshi_installed", lambda: False)
    cfg = VoiceBotConfig(voice_layer="moshi", moshi_url="ws://127.0.0.1:1/x", moshi_autostart=True)

    assert moshi_gate(cfg) == "moshi_unavailable"
    assert calls == []


def test_moshi_autostart_loads_from_repo_config_and_must_be_bool(tmp_path: Path):
    import json

    from voice_turn_support import make_repo

    import hive_planner.voice_bot as vb

    paths = make_repo(tmp_path)
    path = voice_bot_config_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"moshi_autostart": False}), encoding="utf-8")
    assert vb.load_voice_bot_config(paths).moshi_autostart is False

    with pytest.raises(VoiceBotError, match="moshi_autostart"):
        VoiceBotConfig(moshi_autostart="yes")  # type: ignore[arg-type]


Q8_KEYS = {
    "moshi_q8_weights": "C:/q8/model.q8.safetensors",
    "moshi_mimi_weights": "C:/bf16/tokenizer.safetensors",
    "moshi_tokenizer": "C:/bf16/tokenizer.model",
    "moshi_model_config": "C:/q8/config.local.json",
}


def test_q8_keys_must_be_set_together():
    with pytest.raises(VoiceBotError, match="all be set together"):
        VoiceBotConfig(moshi_q8_weights="C:/q8/model.q8.safetensors")


def test_q8_keys_all_null_keeps_bare_upstream_command():
    cfg = VoiceBotConfig(voice_layer="moshi", moshi_url="ws://127.0.0.1:8998/api/chat")
    assert cfg.moshi_q8_weights is None
    assert server_command(cfg.moshi_url)[1:3] == ["-m", "moshi.server"]


def test_q8_command_runs_the_launcher_with_all_four_paths():
    from hive_planner.voice_moshi_server import Q8_LAUNCHER, q8_server_command

    cfg = VoiceBotConfig(voice_layer="moshi", moshi_url="ws://127.0.0.1:9123/api/chat", **Q8_KEYS)
    cmd = q8_server_command(cfg.moshi_url, cfg)
    assert cmd[1] == str(Q8_LAUNCHER)
    assert Q8_LAUNCHER.is_file()
    assert cmd[cmd.index("--port") + 1] == "9123"
    assert cmd[cmd.index("--q8") + 1] == Q8_KEYS["moshi_q8_weights"]
    assert cmd[cmd.index("--mimi") + 1] == Q8_KEYS["moshi_mimi_weights"]
    assert cmd[cmd.index("--tokenizer") + 1] == Q8_KEYS["moshi_tokenizer"]
    assert cmd[cmd.index("--config") + 1] == Q8_KEYS["moshi_model_config"]


def test_gate_with_q8_keys_starts_the_q8_launcher_not_the_bare_command(monkeypatch):
    calls: list[list[str]] = []
    server = MoshiServerProcess(popen=lambda cmd, **k: calls.append(cmd) or None, ready_timeout_s=0.2, poll_s=0.05)
    monkeypatch.setattr(vm, "SERVER", server)
    cfg = VoiceBotConfig(
        voice_layer="moshi", moshi_url=f"ws://127.0.0.1:{_closed_port()}/api/chat", moshi_autostart=True, **Q8_KEYS
    )
    assert moshi_gate(cfg) == "moshi_server_exited"  # the stub child returns None and exits at once
    assert len(calls) == 1
    assert "moshi_q8_server.py" in calls[0][1]
    assert "-m" not in calls[0][:3]


def test_q8_launcher_refuses_missing_checkpoint_files(tmp_path):
    from hive_planner.voice_moshi_server import Q8_LAUNCHER

    proc = subprocess.run(
        [
            sys.executable, str(Q8_LAUNCHER), "--port", "9",
            "--q8", str(tmp_path / "missing.safetensors"),
            "--mimi", str(tmp_path / "m.safetensors"),
            "--tokenizer", str(tmp_path / "t.model"),
            "--config", str(tmp_path / "c.json"),
        ],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode != 0
    assert "q8 file not found" in proc.stderr


def moshi_gate(cfg):
    return vm.moshi_listen_gate(cfg)


@pytest.fixture
def counting_server():
    """Loopback Moshi stand-in: handshake, then hold the socket open. Counts connections."""
    from websockets.sync.server import serve

    from hive_planner.voice_moshi import KIND_HANDSHAKE

    seen: list[int] = []

    def handler(ws):
        seen.append(1)
        ws.send(bytes([KIND_HANDSHAKE]))
        for _msg in ws:
            pass

    server = serve(handler, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.socket.getsockname()[1]
    try:
        yield f"ws://127.0.0.1:{port}/api/chat", seen
    finally:
        vm._pop_held("")  # drop any socket a test left in the holder
        server.shutdown()
        thread.join(timeout=5)


def test_call_gate_hands_its_socket_to_the_next_open_session(counting_server):
    url, seen = counting_server
    cfg = VoiceBotConfig(voice_layer="moshi", moshi_url=url, moshi_autostart=False)

    assert vm.moshi_call_gate(cfg) is None
    assert len(seen) == 1  # the probe made the only connection

    session = vm.open_session(url)  # what talk() calls next
    assert len(seen) == 1  # no second connect: the held socket was handed over
    assert session.closed is False
    session.close()


def test_typed_gate_still_closes_its_probe(counting_server):
    url, seen = counting_server
    cfg = VoiceBotConfig(voice_layer="moshi", moshi_url=url, moshi_autostart=False)

    assert vm.moshi_listen_gate(cfg) is None
    assert vm._HELD is None  # nothing kept open for a later caller
    vm.open_session(url).close()
    assert len(seen) == 2


def test_held_socket_is_not_reused_for_another_url(counting_server):
    url, seen = counting_server
    cfg = VoiceBotConfig(voice_layer="moshi", moshi_url=url, moshi_autostart=False)
    assert vm.moshi_call_gate(cfg) is None

    other = url.replace("/api/chat", "/other")
    vm.open_session(other).close()  # same server, different URL: a real new connect
    assert len(seen) == 2


def test_hold_is_consumed_once(counting_server):
    url, seen = counting_server
    cfg = VoiceBotConfig(voice_layer="moshi", moshi_url=url, moshi_autostart=False)
    assert vm.moshi_call_gate(cfg) is None
    vm.open_session(url).close()
    vm.open_session(url).close()  # the slot is empty now: this one connects
    assert len(seen) == 2


def test_server_output_goes_to_the_log_file(tmp_path):
    log = tmp_path / "logs" / "moshi-server.log"
    server = MoshiServerProcess(
        command=lambda _url: [sys.executable, "-c", "import sys; print('out-line'); sys.stderr.write('err-line')"],
        ready_timeout_s=10.0,
        poll_s=0.05,
        log_path=log,
    )
    code = server.ensure("ws://127.0.0.1:1/api/chat", lambda _u: False)
    assert code == "moshi_server_exited"
    text = log.read_text(encoding="utf-8")
    assert "out-line" in text and "err-line" in text


def _raise_unreachable(*_args, **_kwargs):
    raise VoiceBotError("moshi_unreachable")

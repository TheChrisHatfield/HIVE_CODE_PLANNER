"""T017 host entry point: `voice-bot bridge` as a real child process.

The command runs until its stdin closes, so the tests stop it by closing stdin (the same signal
the extension uses). Each test checks the lifecycle on disk and over loopback HTTP, with the
production CLI, runner, and bridge. The ACP executable is never spawned: the bridge only spawns
it on submit, and these tests make no submit.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

import hive_planner
from hive_planner.config import RepoPaths
from hive_planner.voice_bridge import (
    bridge_endpoint_path,
    bridge_is_live,
    bridge_token_path,
)
from voice_turn_support import make_repo

SRC_DIR = str(Path(hive_planner.__file__).resolve().parent.parent)


@pytest.fixture
def repo(tmp_path: Path) -> RepoPaths:
    return make_repo(tmp_path)


def _spawn(repo: RepoPaths) -> subprocess.Popen:
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.Popen(
        [
            sys.executable, "-m", "hive_planner", "--root", str(repo.root),
            "voice-bot", "bridge", "--feature", "Voice_Bot", "--agent-path", "fake-agent",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def _ready(proc: subprocess.Popen) -> dict:
    line = proc.stdout.readline()
    assert line, f"bridge exited before ready; stderr={proc.stderr.read()!r}"
    return json.loads(line)


def _stop(proc: subprocess.Popen) -> int:
    proc.stdin.close()
    return proc.wait(timeout=20)


def _get(port: int, token: str | None, repo: RepoPaths) -> tuple[int, dict]:
    query = urllib.parse.urlencode({"workspace": str(repo.root)})
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/approval?{query}")
    if token is not None:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_bridge_command_serves_then_cleans_up_when_stdin_closes(repo):
    proc = _spawn(repo)
    try:
        ready = _ready(proc)
        assert ready["ok"] is True and ready["host"] == "127.0.0.1"
        token = bridge_token_path(repo).read_text(encoding="utf-8")
        assert token not in json.dumps(ready), "the token value must never be printed"


        endpoint = json.loads(bridge_endpoint_path(repo).read_text(encoding="utf-8"))
        assert endpoint["port"] == ready["port"]
        assert bridge_is_live(repo)

        assert _get(ready["port"], None, repo)[0] == 401
        status, view = _get(ready["port"], token, repo)
        assert status == 200 and view == {"pending": False}
    finally:
        code = _stop(proc)

    assert code == 0
    assert not bridge_token_path(repo).exists()
    assert not bridge_endpoint_path(repo).exists()
    assert not bridge_is_live(repo)


def test_second_bridge_is_refused_while_the_first_is_live(repo):
    first = _spawn(repo)
    try:
        _ready(first)
        second = _spawn(repo)
        try:
            assert second.wait(timeout=20) == 1
            err = second.stderr.read()
            assert "already running" in err
        finally:
            second.stdin.close()
        # The refused start must not have removed the live owner's files.
        assert bridge_is_live(repo)
    finally:
        _stop(first)


def test_stale_endpoint_from_a_dead_bridge_does_not_block_start(repo):
    endpoint = bridge_endpoint_path(repo)
    endpoint.parent.mkdir(parents=True, exist_ok=True)
    # Port 9 on loopback is not listening; the file is left over from a crashed run.
    endpoint.write_text(json.dumps({"host": "127.0.0.1", "port": 9, "started_at": "old"}), encoding="utf-8")
    assert not bridge_is_live(repo)

    proc = _spawn(repo)
    try:
        ready = _ready(proc)
        assert ready["ok"] is True
        assert bridge_is_live(repo)
    finally:
        assert _stop(proc) == 0


def test_unreadable_endpoint_counts_as_stale(repo):
    endpoint = bridge_endpoint_path(repo)
    endpoint.parent.mkdir(parents=True, exist_ok=True)
    endpoint.write_text("{not json", encoding="utf-8")
    assert not bridge_is_live(repo)

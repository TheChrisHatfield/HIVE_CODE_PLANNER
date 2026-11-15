"""H7 / H6 decisions: ACP fs/read cap comes from config (R21); restart after call end opens a new scope (R29)."""

from __future__ import annotations

import json
from pathlib import Path

from hive_planner.voice_bot import voice_bot_config_path
from voice_turn_support import make_repo, make_runner, wait_task_terminal


def _runner_with_config(tmp_path: Path, config: dict | None):
    repo = make_repo(tmp_path)
    if config is not None:
        path = voice_bot_config_path(repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config), encoding="utf-8")
    return repo, make_runner(repo)


def test_fs_read_cap_is_taken_from_snapshot_max_bytes_config(tmp_path: Path) -> None:
    repo, r = _runner_with_config(tmp_path, {"snapshot_max_bytes": 10})
    try:
        assert r.config.snapshot_max_bytes == 10
        out = r._handle_server_request("fs/read_text_file", {"path": "src/app.py"})
        assert len(out["content"].encode("utf-8")) == 10
        assert out["content"] == "def add(a,"
    finally:
        r.close()


def test_fs_read_uses_default_cap_when_config_absent(tmp_path: Path) -> None:
    repo, r = _runner_with_config(tmp_path, None)
    try:
        assert r.config.snapshot_max_bytes == 64 * 1024
        out = r._handle_server_request("fs/read_text_file", {"path": "src/app.py"})
        assert out["content"] == (repo.root / "src" / "app.py").read_bytes().decode("utf-8")
    finally:
        r.close()


def test_restart_after_call_end_opens_new_session_and_new_task(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    first = make_runner(repo)
    try:
        out = first.submit("hello", client_request_id="scope-1")
        wait_task_terminal(first, out["task_id"])
        old_session = first.session.session_id
        first.end_call()
    finally:
        first.close()

    second = make_runner(repo)
    try:
        assert second.session.session_id != old_session
        again = second.submit("hello", client_request_id="scope-1")
        assert again["task_id"] != out["task_id"]
        wait_task_terminal(second, again["task_id"])
    finally:
        second.close()

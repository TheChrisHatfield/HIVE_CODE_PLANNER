"""Start race: one runner per repo across processes (voice_lock.py, bridge and init paths).

The holder in the cross-process test is a real child process, so the lock is the OS lock,
not a Python object. Standalone turns, the bridge command, and `voice-bot init` all go
through the same lock.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import hive_planner
from hive_planner.cli import main
from hive_planner.config import RepoPaths
from hive_planner.voice_bot import load_state
from hive_planner.voice_bridge import bridge_endpoint_path, bridge_token_path
from hive_planner.voice_lock import RunnerLock, RunnerLockHeld, runner_lock_path
from voice_turn_support import make_repo, make_runner

SRC_DIR = str(Path(hive_planner.__file__).resolve().parent.parent)


@pytest.fixture
def repo(tmp_path: Path) -> RepoPaths:
    return make_repo(tmp_path)


def test_a_second_runner_for_the_same_repo_is_refused_until_the_first_closes(repo):
    first = make_runner(repo)
    try:
        with pytest.raises(RunnerLockHeld):
            make_runner(repo)
    finally:
        first.close()
    second = make_runner(repo)
    second.close()


def test_a_failed_runner_construction_releases_the_lock(repo, monkeypatch):
    import hive_planner.voice_task as voice_task

    def boom(*args, **kwargs):
        raise RuntimeError("state unreadable")

    monkeypatch.setattr(voice_task, "load_state", boom)
    with pytest.raises(RuntimeError):
        make_runner(repo)
    monkeypatch.undo()
    make_runner(repo).close()  # the lock was released on the failed path


def test_bridge_start_is_refused_while_a_standalone_runner_holds_the_repo(repo, capsys):
    holder = make_runner(repo)
    try:
        code = main([
            "--root", str(repo.root), "voice-bot", "bridge", "--feature", "Voice_Bot",
            "--agent-path", "fake-agent",
        ])
        err = capsys.readouterr().err
        assert code == 1
        assert "already running" in err
        # The refused bridge wrote no endpoint or token, so no client can reach a second writer.
        assert not bridge_endpoint_path(repo).exists()
        assert not bridge_token_path(repo).exists()
    finally:
        holder.close()


def test_init_is_refused_while_a_standalone_runner_holds_the_repo(repo, capsys):
    holder = make_runner(repo)
    try:
        session_before = holder.state.voice_session.session_id
        code = main(["--root", str(repo.root), "voice-bot", "init", "--feature", "Voice_Bot"])
        assert code == 1
        assert "already running" in capsys.readouterr().err
        assert load_state(repo).voice_session.session_id == session_before
    finally:
        holder.close()


def _holder_script() -> str:
    return (
        "import sys\n"
        "from pathlib import Path\n"
        "from hive_planner.config import RepoPaths\n"
        "from hive_planner.voice_lock import RunnerLock\n"
        "lock = RunnerLock(RepoPaths(root=Path(sys.argv[1])))\n"
        "lock.acquire()\n"
        "print('held', flush=True)\n"
        "sys.stdin.read()\n"
    )


def test_a_lock_held_by_another_process_is_refused_and_freed_when_that_process_dies(repo):
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")
    holder = subprocess.Popen(
        [sys.executable, "-c", _holder_script(), str(repo.root)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    )
    try:
        assert holder.stdout.readline().strip() == "held"
        other = RunnerLock(repo)
        with pytest.raises(RunnerLockHeld):
            other.acquire()
        assert runner_lock_path(repo).exists()
    finally:
        holder.kill()
        holder.wait(timeout=20)

    # The OS released the lock with the dead process; a stale file does not block a new runner.
    freed = RunnerLock(repo)
    freed.acquire()
    assert freed.held
    freed.release()

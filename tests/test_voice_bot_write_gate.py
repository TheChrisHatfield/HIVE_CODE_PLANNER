"""U11a: production provider writes must wait for the approval broker before touching disk.

Integrated test: `runner.submit` -> production ACP init (`VoiceTaskRunner._ensure_session`) ->
live fake child (tests/fixtures/acp_turn_server.py). The fake behaves like the R35 shape when the
client does not advertise `clientCapabilities.fs.writeTextFile`: it writes on its own with no
request to the client. Expected after the U11 fix: the write is routed as `fs/write_text_file`,
held behind a pending approval, and the file is created only if the approval is allowed.

Currently failing on purpose (U11a): production init sends writeTextFile false, so the file is
created before any approval exists.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_task import VoiceTaskRunner
from voice_turn_support import make_repo, make_runner, wait_for, wait_task_terminal

# Workspace-root probe. `.hive/` is refused for provider writes (R23: bridge token, config latch).
PROBE_REL = "u11-probe.txt"


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


@pytest.fixture
def latch_on(monkeypatch):
    # R33: the write capability is advertised only in agent mode with the edits latch on.
    import hive_planner.voice_task as voice_task

    monkeypatch.setattr(voice_task, "edits_enabled", lambda paths=None: True)


def test_provider_write_waits_for_approval_before_disk(runner: VoiceTaskRunner, repo, latch_on):
    target = repo.root / PROBE_REL
    out = runner.submit(
        f"FS_WRITE_REQUEST:{PROBE_REL} create the probe file", mode="agent", client_request_id="u11-1",
    )
    task_id = out["task_id"]

    assert wait_for(lambda: runner._pending_approval is not None, timeout=5), (
        "no approval request before the provider write; "
        f"file exists already={target.exists()}"
    )
    assert not target.exists(), "file must not exist before the approval is decided"

    assert runner.reply_approval("deny edit u11 probe")["status"] == "denied"
    assert wait_task_terminal(runner, task_id) in ("completed", "failed")
    assert not target.exists(), "denied approval must leave no file on disk"


def test_approved_provider_write_lands_on_disk(runner: VoiceTaskRunner, repo, latch_on):
    target = repo.root / PROBE_REL
    out = runner.submit(
        f"FS_WRITE_REQUEST:{PROBE_REL} create the probe file", mode="agent", client_request_id="u11-2",
    )
    task_id = out["task_id"]
    assert wait_for(lambda: runner._pending_approval is not None, timeout=5)
    assert not target.exists()

    assert runner.reply_approval("approve edit u11 probe")["status"] == "approved"
    assert wait_task_terminal(runner, task_id) in ("completed", "failed")
    assert target.read_text(encoding="utf-8") == "u11 client write"


def test_provider_write_into_hive_is_refused_without_approval(runner: VoiceTaskRunner, repo, latch_on):
    rel = ".hive/voice-bot/u11-refused.txt"
    out = runner.submit(f"FS_WRITE_REQUEST:{rel} try the config", mode="agent", client_request_id="u11-3")
    task_id = out["task_id"]
    assert wait_task_terminal(runner, task_id) in ("completed", "failed")
    assert runner._pending_approval is None
    assert not (repo.root / rel).exists()

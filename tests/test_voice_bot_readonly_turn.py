"""T004 — one HIVE-routed read-only prompt, streamed updates, stop reason, contextual follow-up.

Runs through the real runner and a real child process (fixtures/acp_turn_server.py).
This proves the protocol path only. G2 (live `agent acp` with a logged-in account) is not
proven by this file; see docs/specs/Voice_Bot/evidence-register.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.voice_task import DelegationError
from voice_turn_support import make_repo, make_runner, wait_task_state, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def test_read_only_prompt_streams_and_completes_with_stop_reason(runner):
    out = runner.submit("explain add", file_path="src/app.py", client_request_id="req-1")
    assert out["task_id"]
    assert out["state"] == "running"  # SC-007: running is reported before work completes
    assert out["spoken"] == "Task accepted, running."

    state = wait_task_terminal(runner, out["task_id"])
    task = runner.state.coding_tasks[out["task_id"]]
    assert state == "completed"
    assert task.evidence.stop_reason == "end_turn"
    assert "turn 1" in task.evidence.written_result  # streamed chunk reached the record
    assert task.raw_events, "raw provider payloads are retained on the task (R17)"
    assert task.provider_session_id.startswith("sess-")
    names = [e["name"] for e in task.events]
    assert "task.started" in names and "task.progress" in names and "task.completed" in names


def test_contextual_follow_up_reuses_the_same_provider_session(runner):
    first = runner.submit("what does add do", client_request_id="req-a")
    wait_task_terminal(runner, first["task_id"])
    second = runner.submit("and what about its return type", client_request_id="req-b")
    wait_task_terminal(runner, second["task_id"])

    t1 = runner.state.coding_tasks[first["task_id"]]
    t2 = runner.state.coding_tasks[second["task_id"]]
    assert t2.provider_session_id == t1.provider_session_id  # same owned ACP session (R4)
    assert "turn 2" in t2.evidence.written_result  # the provider saw the earlier turn


def test_provider_crash_mid_turn_is_unknown_not_completed(runner):
    out = runner.submit("CRASH_MID_TURN please", client_request_id="req-crash")
    # provider_disconnected is non-terminal (R20); the provider-lost window keeps it open.
    wait_task_state(runner, out["task_id"], "unknown")
    task = runner.state.coding_tasks[out["task_id"]]
    assert task.reason == "provider_disconnected"
    assert task.state != "completed"


def test_follow_up_blocked_by_unknown_is_queued_not_run(runner):
    crashed = runner.submit("CRASH_MID_TURN now", client_request_id="req-c")
    wait_task_state(runner, crashed["task_id"], "unknown")
    later = runner.submit("another question", client_request_id="req-d")
    assert later["status"] == "queued"  # the active slot is held by the unknown task
    assert later["task_id"] is None


def test_file_outside_workspace_is_refused_and_creates_no_task(runner):
    before = len(runner.state.coding_tasks)
    with pytest.raises(DelegationError) as exc:
        runner.submit("read it", file_path="../outside.txt", client_request_id="req-p")
    assert exc.value.code == "path_outside_workspace"
    assert len(runner.state.coding_tasks) == before


def test_agent_mode_is_refused_until_g6(runner):
    with pytest.raises(DelegationError) as exc:
        runner.submit("edit it", mode="agent", client_request_id="req-agent")
    assert exc.value.code == "agent_mode_disabled"
    assert runner.state.coding_tasks == {}


def test_submit_without_client_request_id_creates_no_task(runner):
    with pytest.raises(DelegationError) as exc:
        runner.submit("hello", client_request_id="   ")
    assert exc.value.code == "missing_client_request_id"
    assert runner.state.coding_tasks == {}


def test_instruction_limit_is_read_from_config(repo):
    cfg_dir = repo.root / ".hive" / "voice-bot"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json").write_text(json.dumps({"instruction_max_chars": 12}), encoding="utf-8")
    r = make_runner(repo)
    try:
        with pytest.raises(DelegationError) as exc:
            r.submit("this instruction is longer than twelve", client_request_id="req-long")
        assert exc.value.code == "instruction_too_long"
        assert r.state.coding_tasks == {}
    finally:
        r.close()


def test_reconnect_window_from_config_marks_provider_lost(repo):
    cfg_dir = repo.root / ".hive" / "voice-bot"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json").write_text(json.dumps({"reconnect_window_s": 1}), encoding="utf-8")
    r = make_runner(repo)
    try:
        out = r.submit("CRASH_MID_TURN lost", client_request_id="req-lost")
        # After the crash the task is unknown; the 1-second window expires to failed/provider_lost.
        wait_task_state(r, out["task_id"], "failed", timeout=15)
        task = r.state.coding_tasks[out["task_id"]]
        assert task.reason == "provider_lost"
        assert task.evidence.spoken_update  # failure is spoken from recorded evidence
    finally:
        r.close()

"""T006 — provider-neutral delegation handlers: submit, status, diff, follow-up, cancellation.

Also covers SC-012 (dedupe by client_request_id) and the R18 binding rules.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.config import RepoPaths
from hive_planner.voice_bot import TaskEvidence, voice_bot_config_path
from hive_planner.voice_task import DelegationError, cap_text
from voice_turn_support import make_repo, make_runner, wait_task_state, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def test_submit_twice_with_same_client_request_id_creates_one_task(runner):
    first = runner.submit("hello", client_request_id="dup-1")
    wait_task_terminal(runner, first["task_id"])
    again = runner.submit("hello again", client_request_id="dup-1")
    assert again["status"] == "duplicate"
    assert again["task_id"] == first["task_id"]
    assert len(runner.state.coding_tasks) == 1  # SC-012


def test_dedupe_while_queued_returns_the_queue_entry_not_a_task(runner):
    blocker = runner.submit("CANCEL_ME first", client_request_id="blk")
    wait_task_state(runner, blocker["task_id"], "running")
    queued = runner.submit("second", client_request_id="q-dup")
    assert queued["status"] == "queued" and queued["task_id"] is None
    again = runner.submit("second", client_request_id="q-dup")
    assert again["status"] == "duplicate"
    assert again["task_id"] is None
    assert len(runner.state.queue) == 1
    runner.cancel(blocker["task_id"])


def test_task_status_reports_state_transitions_and_tests(runner):
    out = runner.submit("hello", client_request_id="st-1")
    wait_task_terminal(runner, out["task_id"])
    status = runner.task_status(out["task_id"])
    assert status["state"] == "completed"
    assert status["tests_status"] == "not_run"  # no test command ran in this task (R8)
    assert [t["to"] for t in status["transitions"]] == ["running", "completed"]


def test_task_diff_for_read_only_task_has_no_diff_evidence(runner):
    out = runner.submit("hello", client_request_id="df-1")
    wait_task_terminal(runner, out["task_id"])
    diff = runner.task_diff(out["task_id"])
    assert diff == {"task_id": out["task_id"], "diff": "", "truncated": False,
                    "source": "no_diff_evidence"}


def test_diff_cap_flags_truncation_explicitly():
    text, truncated = cap_text("x" * 300, 256)
    assert truncated is True
    assert len(text) == 256
    text, truncated = cap_text("short", 256)
    assert truncated is False and text == "short"


def test_unknown_task_is_refused_on_every_task_bound_call(runner):
    with pytest.raises(DelegationError) as exc:
        runner.task_status("task_nope")
    assert exc.value.code == "unknown_task"
    with pytest.raises(DelegationError) as exc:
        runner.task_diff("task_nope")
    assert exc.value.code == "unknown_task"
    with pytest.raises(DelegationError) as exc:
        runner.cancel("task_nope")
    assert exc.value.code == "unknown_task"


def test_follow_up_bound_to_a_different_task_is_refused(runner):
    blocker = runner.submit("CANCEL_ME hold", client_request_id="fu-1")
    wait_task_state(runner, blocker["task_id"], "running")
    with pytest.raises(DelegationError) as exc:
        runner.queue_follow_up("more", task_id="task_other")
    assert exc.value.code == "task_mismatch"
    runner.cancel(blocker["task_id"])


def test_follow_up_without_active_task_is_refused(runner):
    with pytest.raises(DelegationError) as exc:
        runner.queue_follow_up("more", task_id="task_none")
    assert exc.value.code == "no_active_task"


def test_cancel_delegation_reaches_cancelled_through_the_provider(runner):
    out = runner.submit("CANCEL_ME please", client_request_id="cx-1")
    wait_task_state(runner, out["task_id"], "running")
    requested = runner.cancel(out["task_id"])
    assert requested["state"] == "cancel_requested"
    assert wait_task_terminal(runner, out["task_id"]) == "cancelled"


def _grant_r33_latch(root: Path) -> None:
    """Fixture latch on: G6 register pass plus config edits_enabled true (R33)."""
    spec = root / "docs" / "specs" / "Voice_Bot"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "evidence-register.md").write_text(
        "| Claim ID | Component | Pinned | Test | Result | Date | Notes |\n"
        "|---|---|---|---|---|---|---|\n"
        "| G6 | permissions | x | t | **pass** | 2026-11-11 | fixture |\n",
        encoding="utf-8",
    )
    cfg = voice_bot_config_path(RepoPaths(root=root))
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"edits_enabled": True}), encoding="utf-8")


def _running_task_with_write(runner, client_request_id: str, new_text: str) -> str:
    """Hold a task in `running`, then deliver a completed ACP diff write for it (T032 fixture)."""
    out = runner.submit("CANCEL_ME hold", client_request_id=client_request_id)
    wait_task_state(runner, out["task_id"], "running")
    runner._on_update({
        "sessionId": runner._acp_session_id,
        "update": {
            "sessionUpdate": "tool_call_update",
            "toolCallId": "call-w1",
            "status": "completed",
            "content": [{"type": "diff", "path": "src/app.py",
                         "oldText": "def add(a, b):\n    return a + b\n", "newText": new_text}],
        },
    })
    return out["task_id"]


def test_task_diff_is_non_stub_when_write_evidence_exists_and_latch_is_on(runner, repo):
    _grant_r33_latch(repo.root)
    new_text = "def add(a, b):\n    return a + b  # sum\n"
    task_id = _running_task_with_write(runner, "wd-1", new_text)
    try:
        diff = runner.task_diff(task_id)
        assert diff["source"] == "write_evidence"
        assert diff["truncated"] is False
        assert diff["diff"].startswith("--- a/src/app.py\n+++ b/src/app.py\n")
        assert "-    return a + b\n" in diff["diff"]
        assert "+    return a + b  # sum\n" in diff["diff"]
    finally:
        runner.cancel(task_id)


def test_task_diff_write_evidence_is_capped_with_explicit_truncation(runner, repo):
    _grant_r33_latch(repo.root)
    big = "".join(f"line {i}\n" for i in range(60_000))  # well over diff_max_bytes
    task_id = _running_task_with_write(runner, "wd-cap", big)
    try:
        diff = runner.task_diff(task_id)
        assert diff["source"] == "write_evidence"
        assert diff["truncated"] is True
        assert len(diff["diff"].encode("utf-8")) <= runner.config.diff_max_bytes
    finally:
        runner.cancel(task_id)


def test_task_diff_with_write_evidence_but_latch_off_keeps_no_diff_evidence(runner):
    task_id = _running_task_with_write(runner, "wd-off", "changed\n")
    try:
        diff = runner.task_diff(task_id)
        assert diff == {"task_id": task_id, "diff": "", "truncated": False,
                        "source": "no_diff_evidence"}
    finally:
        runner.cancel(task_id)


def test_non_completed_tool_update_records_no_write_evidence(runner, repo):
    _grant_r33_latch(repo.root)
    out = runner.submit("CANCEL_ME hold", client_request_id="wd-pending")
    wait_task_state(runner, out["task_id"], "running")
    try:
        runner._on_update({
            "sessionId": runner._acp_session_id,
            "update": {"sessionUpdate": "tool_call_update", "toolCallId": "c", "status": "in_progress",
                       "content": [{"type": "diff", "path": "a.py", "oldText": "", "newText": "x\n"}]},
        })
        assert runner.task_diff(out["task_id"])["source"] == "no_diff_evidence"
    finally:
        runner.cancel(out["task_id"])


def test_write_evidence_survives_evidence_round_trip():
    ev = TaskEvidence.from_dict({"write_diffs": [{"path": "a.py", "old_text": "1\n", "new_text": "2\n"},
                                                  "junk"]})
    assert ev.write_diffs == [{"path": "a.py", "old_text": "1\n", "new_text": "2\n"}]
    assert TaskEvidence.from_dict(ev.to_dict()).write_diffs == ev.write_diffs


def test_cancel_on_terminal_task_is_refused(runner):
    out = runner.submit("hello", client_request_id="cx-2")
    wait_task_terminal(runner, out["task_id"])
    with pytest.raises(DelegationError) as exc:
        runner.cancel(out["task_id"])
    assert exc.value.code == "task_already_terminal"


def test_queue_follow_up_on_active_task_queues_fifo_behind_the_running_task(runner):
    blocker = runner.submit("CANCEL_ME hold", client_request_id="qf-1")
    wait_task_state(runner, blocker["task_id"], "running")
    follow = runner.queue_follow_up("and then this", task_id=blocker["task_id"])
    assert follow["status"] == "queued" and follow["task_id"] is None
    queued = [e for e in runner.state.queue if e.get("state") == "queued"]
    assert len(queued) == 1 and queued[0]["text"] == "and then this"
    assert runner.state.coding_tasks[blocker["task_id"]].state == "running"
    runner.cancel(blocker["task_id"])
    wait_task_terminal(runner, blocker["task_id"])


def _mark_unknown_like_a_dropped_provider(runner, task_id: str) -> None:
    """Drive the real disconnect transition (running -> unknown, R26) without a fake shutdown."""
    with runner._lock:
        task = runner.state.coding_tasks[task_id]
        task.prior_state = task.state
        runner._transition(task, "unknown", "provider_disconnected")
        runner._settle(task)


def test_reconnect_refuses_a_task_that_is_not_unknown(runner):
    out = runner.submit("CANCEL_ME hold", client_request_id="rc-not")
    wait_task_state(runner, out["task_id"], "running")
    with pytest.raises(DelegationError) as exc:
        runner.reconnect_task(out["task_id"])
    assert exc.value.code == "not_unknown"
    runner.cancel(out["task_id"])
    wait_task_terminal(runner, out["task_id"])


def test_reconnect_restores_prior_state_when_live_acp_session_matches(runner):
    out = runner.submit("CANCEL_ME hold", client_request_id="rc-live")
    wait_task_state(runner, out["task_id"], "running")
    _mark_unknown_like_a_dropped_provider(runner, out["task_id"])
    assert runner.state.coding_tasks[out["task_id"]].state == "unknown"
    restored = runner.reconnect_task(out["task_id"])
    assert restored["task_id"] == out["task_id"]
    assert restored["state"] == "running"
    assert runner.state.coding_tasks[out["task_id"]].state == "running"
    runner.cancel(out["task_id"])
    assert wait_task_terminal(runner, out["task_id"]) == "cancelled"


def test_reconnect_refuses_when_another_task_is_active(runner):
    first = runner.submit("CANCEL_ME hold", client_request_id="rc-slot-a")
    wait_task_state(runner, first["task_id"], "running")
    with runner._lock:
        runner._recover_after_hive_restart()
    assert runner.state.coding_tasks[first["task_id"]].state == "unknown"
    second = runner.submit("CANCEL_ME hold", client_request_id="rc-slot-b")
    wait_task_state(runner, second["task_id"], "running")
    with pytest.raises(DelegationError) as exc:
        runner.reconnect_task(first["task_id"])
    assert exc.value.code == "task_slot_occupied"
    assert runner.state.coding_tasks[first["task_id"]].state == "unknown"
    assert runner.state.coding_tasks[second["task_id"]].state == "running"

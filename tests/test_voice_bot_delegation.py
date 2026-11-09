"""T006 — provider-neutral delegation handlers: submit, status, diff, follow-up, cancellation.

Also covers SC-012 (dedupe by client_request_id) and the R18 binding rules.
"""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_cancel_on_terminal_task_is_refused(runner):
    out = runner.submit("hello", client_request_id="cx-2")
    wait_task_terminal(runner, out["task_id"])
    with pytest.raises(DelegationError) as exc:
        runner.cancel(out["task_id"])
    assert exc.value.code == "task_already_terminal"

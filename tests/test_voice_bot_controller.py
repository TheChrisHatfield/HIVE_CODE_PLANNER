"""T035 — `transcript.final` voice controller: one bounded dispatch per final transcript (R18, R29).

Drives the controller entry point `invoke_controller_tool` (the only tool dispatcher the voice
layer can reach) against the real runner and a real ACP child process.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_task import DelegationError
from voice_turn_support import make_repo, make_runner, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def _names(runner, task_id: str) -> list[str]:
    return [e["name"] for e in runner.state.coding_tasks[task_id].events]


def test_one_final_transcript_dispatches_one_submit(runner):
    out = runner.invoke_controller_tool(
        "submit_coding_task",
        instruction="hello",
        mode="ask",
        client_request_id="ctl-once",
        workspace=str(runner.paths.root),
    )
    wait_task_terminal(runner, out["task_id"])
    assert len(runner.state.coding_tasks) == 1
    assert _names(runner, out["task_id"]).count("transcript.final") == 1


def test_retried_final_transcript_returns_existing_task(runner):
    first = runner.invoke_controller_tool(
        "submit_coding_task",
        instruction="hello",
        client_request_id="ctl-retry",
        workspace=str(runner.paths.root),
    )
    wait_task_terminal(runner, first["task_id"])
    again = runner.invoke_controller_tool(
        "submit_coding_task",
        instruction="hello",
        client_request_id="ctl-retry",
        workspace=str(runner.paths.root),
    )
    assert again["task_id"] == first["task_id"]
    assert len(runner.state.coding_tasks) == 1
    assert _names(runner, first["task_id"]).count("transcript.final") == 1


def test_submit_without_client_request_id_creates_no_task(runner):
    with pytest.raises(DelegationError) as exc:
        runner.invoke_controller_tool(
            "submit_coding_task",
            instruction="hello",
            workspace=str(runner.paths.root),
        )
    assert exc.value.code == "missing_client_request_id"
    assert runner.state.coding_tasks == {}
    assert runner.state.dedupe == {}


def test_unbounded_tool_name_is_refused_and_dispatches_nothing(runner):
    with pytest.raises(DelegationError) as exc:
        runner.invoke_controller_tool("shell", command="rm -rf /", workspace=str(runner.paths.root))
    assert exc.value.code == "unbounded_tool"
    assert runner.state.coding_tasks == {}

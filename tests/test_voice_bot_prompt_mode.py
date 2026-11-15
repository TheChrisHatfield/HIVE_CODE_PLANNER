"""Mode-aware ACP prompt text (Voice_Bot live G6 write blocker).

The read-only line must stay for ask and plan. Agent mode must not carry it,
because the R33 latch already allows edits and a contradicting prompt makes the
child agent refuse to write (task_51b167481545).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from voice_turn_support import make_repo, make_runner, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


INSTRUCTION = "Write the word hi to .hive/voice-bot/live-write-check.txt"


def test_ask_prompt_keeps_read_only_line(runner):
    out = runner.submit(INSTRUCTION, mode="ask", client_request_id="prompt-ask")
    task = runner.state.coding_tasks[out["task_id"]]
    prompt = runner._prompt_text(task)
    wait_task_terminal(runner, out["task_id"])
    assert "Read-only request; do not modify files." in prompt


def test_agent_prompt_drops_read_only_line(runner, monkeypatch):
    # Flip the R33 latch in-process so the agent submit gate is passed.
    import hive_planner.voice_task as vt

    monkeypatch.setattr(vt, "edits_enabled", lambda paths: True)
    out = runner.submit(INSTRUCTION, mode="agent", client_request_id="prompt-agent")
    task = runner.state.coding_tasks[out["task_id"]]
    prompt = runner._prompt_text(task)
    wait_task_terminal(runner, out["task_id"])
    assert "Read-only request" not in prompt
    assert "do not modify files" not in prompt
    assert "Mode: agent." in prompt
    assert "live-write-check.txt" in prompt

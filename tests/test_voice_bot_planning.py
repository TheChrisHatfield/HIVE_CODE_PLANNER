"""T022 — uncoded spec rows: US5 planning Q&A, R2 file content and excerpt ids, R18 bind, editor tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.voice_task import DelegationError
from voice_turn_support import make_repo, make_runner, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    paths = make_repo(tmp_path)
    spec_dir = paths.root / "docs" / "specs" / "Voice_Bot"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.md").write_text(
        "# Spec: Voice_Bot\n\n## Goal\nBuild it.\n\n"
        "## Acceptance criteria\n- Cite this row from the spec.\n\n"
        "## Risks\nDo not invent.\n",
        encoding="utf-8",
    )
    (spec_dir / "plan.md").write_text("# Plan\nUse ACP.\n", encoding="utf-8")
    (spec_dir / "tasks.md").write_text("# Tasks\n- T001\n", encoding="utf-8")
    mapping = paths.root / "cartridge" / "mappings"
    mapping.mkdir(parents=True)
    (paths.root / "cartridge" / "manifest.json").write_text(
        json.dumps({"cartridge_id": "ctx-test", "features": ["Voice_Bot"]}),
        encoding="utf-8",
    )
    (mapping / "source-map.json").write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "cartridge": "cartridge/specs/Voice_Bot.specseed.md",
                        "delta": "docs/specs/Voice_Bot/spec.md",
                        "layer": "spec_seed",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return paths


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def test_acceptance_criteria_question_cites_the_spec_file(runner):
    out = runner.submit(
        "What are the current acceptance criteria?",
        client_request_id="plan-ac",
    )
    assert out["state"] == "completed"
    task = runner.state.coding_tasks[out["task_id"]]
    written = task.evidence.written_result
    assert "docs/specs/Voice_Bot/spec.md" in written
    assert "Cite this row from the spec." in written
    assert "Do not invent." not in written
    assert task.provider_kind == "hive_spec"
    assert "tests were not run" in task.evidence.spoken_update.lower()


def test_planning_question_does_not_invent_when_the_spec_is_missing(tmp_path):
    paths = make_repo(tmp_path)
    r = make_runner(paths)
    try:
        out = r.submit("What does the spec say?", client_request_id="plan-miss")
        assert out["state"] == "completed"
        written = r.state.coding_tasks[out["task_id"]].evidence.written_result
        assert "Nothing was invented." in written
        assert "docs/specs/Voice_Bot/spec.md" in written
    finally:
        r.close()


def test_snapshot_records_file_content_excerpt_ids_and_prompt_includes_selection(runner):
    out = runner.submit(
        "explain add",
        file_path="src/app.py",
        client_request_id="sel-1",
        selection_text="def add(a, b):",
    )
    wait_task_terminal(runner, out["task_id"])
    task = runner.state.coding_tasks[out["task_id"]]
    snap = runner.state.context_snapshots[task.context_snapshot_id]
    assert "return a + b" in snap.file_content
    assert snap.selection_text == "def add(a, b):"
    assert snap.cartridge_trace is not None
    assert "spec_seed:cartridge/specs/Voice_Bot.specseed.md" in snap.cartridge_trace.source_excerpt_ids
    prompt = runner._prompt_text(task)
    assert "Selected code:\ndef add(a, b):" in prompt
    assert "File content:" in prompt
    assert "return a + b" in prompt


def test_invoke_requires_workspace_and_snapshot_after_submit(runner):
    with pytest.raises(DelegationError) as exc:
        runner.invoke_controller_tool(
            "submit_coding_task", instruction="hello", client_request_id="no-ws"
        )
    assert exc.value.code == "missing_workspace"
    named = runner.invoke_controller_tool(
        "submit_coding_task",
        instruction="hello",
        client_request_id="ok-ws",
        workspace=str(runner.paths.root),
    )
    wait_task_terminal(runner, named["task_id"])
    snap_id = named["context_snapshot_id"]
    with pytest.raises(DelegationError) as missing:
        runner.invoke_controller_tool(
            "task_status",
            task_id=named["task_id"],
            workspace=str(runner.paths.root),
        )
    assert missing.value.code == "missing_context_snapshot_id"
    status = runner.invoke_controller_tool(
        "task_status",
        task_id=named["task_id"],
        workspace=str(runner.paths.root),
        context_snapshot_id=snap_id,
    )
    assert status["task_id"] == named["task_id"]


def test_navigate_to_queues_until_the_editor_acks(runner):
    out = runner.submit("hello", file_path="src/app.py", client_request_id="nav-1")
    wait_task_terminal(runner, out["task_id"])
    nav = runner.invoke_controller_tool(
        "navigate_to",
        workspace=str(runner.paths.root),
        context_snapshot_id=out["context_snapshot_id"],
        file_path="src/app.py",
    )
    assert nav["navigated"] is False
    assert nav["queued"] is True
    pending = runner.pending_editor_action()
    assert pending["pending"] is True
    assert pending["kind"] == "navigate"
    assert pending["file_path"] == "src/app.py"
    acked = runner.ack_editor_action(nav["action_id"])
    assert acked["navigated"] is True
    assert runner.pending_editor_action()["pending"] is False


def test_show_diff_queues_truncated_text_for_the_editor(runner):
    out = runner.submit("hello", file_path="src/app.py", client_request_id="diff-1")
    wait_task_terminal(runner, out["task_id"])
    shown = runner.invoke_controller_tool(
        "show_diff",
        workspace=str(runner.paths.root),
        context_snapshot_id=out["context_snapshot_id"],
        task_id=out["task_id"],
    )
    assert shown["shown"] is False
    assert shown["queued"] is True
    pending = runner.pending_editor_action()
    assert pending["kind"] == "show_diff"
    acked = runner.ack_editor_action(shown["action_id"])
    assert acked["shown"] is True

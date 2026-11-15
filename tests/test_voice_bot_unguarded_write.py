"""R22 production gate: a write without an approved permission request fails the task.

Integrated tests: each one goes through `runner.submit` and a live fake ACP child
(tests/fixtures/acp_turn_server.py). Nothing here calls the live probe in voice_bot.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_task import VoiceTaskRunner
from voice_turn_support import make_repo, make_runner, wait_for, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def test_write_without_permission_request_fails_task_unguarded_write(runner: VoiceTaskRunner):
    out = runner.submit(
        "WRITE_DIFF_UNGUARDED change the add function",
        client_request_id="unguarded-1",
    )
    task_id = out["task_id"]

    assert wait_task_terminal(runner, task_id) == "failed"
    with runner._lock:
        task = runner.state.coding_tasks[task_id]
        assert task.reason == "unguarded_write"
        assert task.evidence.write_diffs, "the write must be recorded as evidence"
        assert task.approvals == []
        assert "unguarded_write" in task.evidence.spoken_update
        assert any(e["name"] == "write.unguarded" for e in task.events)
        assert not any(e["name"] == "task.completed" for e in task.events)


def test_no_diff_write_without_permission_request_fails_unguarded(runner: VoiceTaskRunner):
    # U6 gap 1: the provider writes but sends no diff content and no permission request.
    out = runner.submit("WRITE_NO_DIFF_UNGUARDED change the add function", client_request_id="nodiff-1")
    task_id = out["task_id"]

    assert wait_task_terminal(runner, task_id) == "failed"
    with runner._lock:
        task = runner.state.coding_tasks[task_id]
        assert task.reason == "unguarded_write"
        assert task.evidence.write_diffs == [], "this write carries no diff"
        assert task.evidence.write_events, "the no-diff write must still be counted"
        assert task.approvals == []
        assert not any(e["name"] == "task.completed" for e in task.events)


def test_execute_shell_write_without_permission_fails_unguarded(runner: VoiceTaskRunner):
    # U10: an `execute` tool call that writes a file (shell redirect) is a write, not a read.
    out = runner.submit("WRITE_EXEC_UNGUARDED tidy the file", client_request_id="exec-1")
    task_id = out["task_id"]

    assert wait_task_terminal(runner, task_id) == "failed"
    with runner._lock:
        task = runner.state.coding_tasks[task_id]
        assert task.reason == "unguarded_write"
        assert len(task.evidence.write_events) == 1
        assert task.approvals == []
        assert not any(e["name"] == "task.completed" for e in task.events)


def test_execute_write_on_tool_call_update_only_fails_unguarded(runner: VoiceTaskRunner):
    # Kind and command can arrive on tool_call_update; that must still count as a write.
    out = runner.submit("WRITE_EXEC_UPDATE_ONLY tidy the file", client_request_id="exec-upd-1")
    task_id = out["task_id"]

    assert wait_task_terminal(runner, task_id) == "failed"
    with runner._lock:
        task = runner.state.coding_tasks[task_id]
        assert task.reason == "unguarded_write"
        assert len(task.evidence.write_events) == 1
        assert task.approvals == []
        rows = task.evidence.tool_calls
    assert len(rows) == 1
    assert rows[0]["kind"] == "execute"
    assert "echo changed" in rows[0]["command"]


def test_interpreter_write_without_permission_fails_unguarded(runner: VoiceTaskRunner):
    # H1: `python -c open(...,'w').write(...)` is an execute call that writes a file.
    out = runner.submit("WRITE_PY_EXEC_UNGUARDED tidy the file", client_request_id="pyexec-1")
    task_id = out["task_id"]

    assert wait_task_terminal(runner, task_id) == "failed"
    with runner._lock:
        task = runner.state.coding_tasks[task_id]
    assert task.reason == "unguarded_write"
    assert len(task.evidence.write_events) == 1
    assert task.approvals == []
    assert not any(e["name"] == "task.completed" for e in task.events)


@pytest.mark.parametrize("command", [
    "python -c \"open('src/app.py','w').write('x')\"",
    "python -c \"open('src/app.py', 'ab').write(b'x')\"",
    "python -c \"open('src/app.py','wt').write('x')\"",
    "python foo.py 2>err.txt",
    "python foo.py 1>out.txt",
    "python -c \"from pathlib import Path; Path('a.txt').write_text('x')\"",
    "node -e \"require('fs').writeFileSync('a.txt','x')\"",
    "python -c \"import shutil; shutil.rmtree('build')\"",
    "python -c \"import os; os.remove('a.txt')\"",
    "git checkout -- src/app.py",
    "git restore src/app.py",
    "patch -p1 < changes.diff",
    # U12 second pass: file-changing commands the first regex missed.
    "touch src/new.py",
    "truncate -s 0 src/app.py",
    "chmod +x scripts/run.sh",
    "ln -s target link",
    "dd if=/dev/zero of=out.bin count=1",
    "python -c \"open('src/app.py', 'r+').write('x')\"",
    "python -c \"open('src/app.py', 'rb+')\"",
    "python -c \"open('src/app.py', 'w+')\"",
    "powershell -c \"Rename-Item a.txt b.txt\"",
    "powershell -c \"Clear-Content a.txt\"",
    "powershell -c \"Set-Item a.txt x\"",
    "powershell -c \"Expand-Archive a.zip out\"",
    "powershell -c \"[IO.File]::WriteAllText('a.txt','x')\"",
    "powershell -c \"[System.IO.File]::AppendAllText('a.txt','x')\"",
])
def test_interpreter_write_commands_are_detected(command: str):
    assert VoiceTaskRunner._is_write_call("execute", command) is True


@pytest.mark.parametrize("command", [
    "pytest -q",
    "ruff check src/",
    "python -c \"print(open('src/app.py').read())\"",
    "python -c \"from pathlib import Path; print(Path('a.txt').read_text())\"",
    "python -c \"import os; print(os.path.exists('a.txt'))\"",
    "node -e \"console.log(require('fs').readFileSync('a.txt','utf8'))\"",
    "git status",
    "git diff",
    # U12: read modes and read cmdlets must stay reads after the regex widening.
    "python -c \"open('a.txt', 'r').read()\"",
    "python -c \"open('a.txt', 'rb').read()\"",
    "powershell -c \"Get-Content a.txt\"",
    "ls -la",
    "pytest tests/test_touch_screen.py -q",
])
def test_read_only_execute_commands_are_not_writes(command: str):
    assert VoiceTaskRunner._is_write_call("execute", command) is False


@pytest.mark.parametrize("command", [
    "python foo.py 2>&1",
    "pytest -q >&2",
])
def test_fd_merge_redirects_are_not_file_writes(command: str):
    assert VoiceTaskRunner._is_write_call("execute", command) is False


def test_empty_tool_call_id_edit_fails_unguarded(runner: VoiceTaskRunner):
    out = runner.submit("WRITE_EMPTY_ID_UNGUARDED change the add function", client_request_id="empty-id-1")
    task_id = out["task_id"]

    assert wait_task_terminal(runner, task_id) == "failed"
    with runner._lock:
        task = runner.state.coding_tasks[task_id]
        assert task.reason == "unguarded_write"
        assert len(task.evidence.write_events) == 1
        assert task.evidence.write_events[0].startswith("anon_")
        assert task.approvals == []


def test_unguarded_write_then_provider_crash_fails_unguarded(runner: VoiceTaskRunner):
    out = runner.submit("WRITE_THEN_CRASH change the add function", client_request_id="crash-write-1")
    task_id = out["task_id"]

    assert wait_task_terminal(runner, task_id) == "failed"
    with runner._lock:
        task = runner.state.coding_tasks[task_id]
        assert task.reason == "unguarded_write"
        assert task.evidence.write_events
        assert any(e["name"] == "write.unguarded" for e in task.events)


def test_write_kind_is_a_write():
    assert VoiceTaskRunner._is_write_call("write", None) is True


def test_empty_tool_call_ids_count_as_separate_writes():
    # Fail closed: without an id, two writes cannot be told apart, so each counts (R22).
    from hive_planner.voice_bot import CodingTask, TaskEvidence

    task = CodingTask(task_id="t", voice_session_id="v", context_snapshot_id="s", state="running")
    task.evidence = TaskEvidence()
    VoiceTaskRunner._record_write_event(task, "")
    VoiceTaskRunner._record_write_event(task, "")
    assert len(task.evidence.write_events) == 2
    assert len(set(task.evidence.write_events)) == 2


def test_one_approval_covers_only_one_write(runner: VoiceTaskRunner):
    # U6 gap 2: one approval, then two writes in the same turn. The second write is unguarded.
    out = runner.submit(
        "WRITE_TWICE NEEDS_APPROVAL:edit src/app.py",
        client_request_id="twice-1",
    )
    task_id = out["task_id"]

    assert wait_for(lambda: runner._pending_approval is not None), "permission request never arrived"
    assert runner.reply_approval("approve edit src/app.py")["status"] == "approved"

    assert wait_task_terminal(runner, task_id) == "failed"
    with runner._lock:
        task = runner.state.coding_tasks[task_id]
        assert task.reason == "unguarded_write"
        assert len(task.evidence.write_events) == 2
        assert [a["status"] for a in task.approvals] == ["approved"]
        assert any(e["name"] == "write.unguarded" for e in task.events)


def test_approved_exec_does_not_guard_later_unapproved_edit(runner: VoiceTaskRunner):
    # R22 approval-to-write matching: an allowed `npm test` execute approval covers no file write.
    out = runner.submit(
        "WRITE_AFTER_EXEC_APPROVAL NEEDS_EXEC_APPROVAL:npm test",
        client_request_id="exec-approval-1",
    )
    task_id = out["task_id"]

    assert wait_for(lambda: runner._pending_approval is not None), "permission request never arrived"
    assert runner.reply_approval("approve npm test")["status"] == "approved"

    assert wait_task_terminal(runner, task_id) == "failed"
    with runner._lock:
        task = runner.state.coding_tasks[task_id]
        assert task.reason == "unguarded_write"
        assert [a["status"] for a in task.approvals] == ["approved"]
        assert task.approvals[0]["tool_kind"] == "execute"
        assert any(e["name"] == "write.unguarded" for e in task.events)


def test_approved_edit_does_not_guard_unapproved_shell_write(runner: VoiceTaskRunner):
    # R22 tool-call-id matching: an approved edit for src/app.py covers only that tool call.
    # A later shell write (a different tool call id) has no approval and must fail unguarded.
    out = runner.submit(
        "WRITE_SHELL_AFTER_EDIT_APPROVAL NEEDS_APPROVAL:edit src/app.py",
        client_request_id="shell-after-edit-1",
    )
    task_id = out["task_id"]

    assert wait_for(lambda: runner._pending_approval is not None), "permission request never arrived"
    assert runner.reply_approval("approve edit src/app.py")["status"] == "approved"

    assert wait_task_terminal(runner, task_id) == "failed"
    with runner._lock:
        task = runner.state.coding_tasks[task_id]
        assert task.reason == "unguarded_write"
        assert task.approvals[0]["tool_call_id"].startswith("tc-perm-")
        assert any(e["name"] == "write.unguarded" for e in task.events)


def test_write_after_allowed_permission_request_completes(runner: VoiceTaskRunner):
    out = runner.submit(
        "WRITE_DIFF NEEDS_APPROVAL:edit src/app.py",
        client_request_id="guarded-1",
    )
    task_id = out["task_id"]

    assert wait_for(lambda: runner._pending_approval is not None), "permission request never arrived"
    reply = runner.reply_approval("approve edit src/app.py")
    assert reply["status"] == "approved"

    assert wait_task_terminal(runner, task_id) == "completed"
    with runner._lock:
        task = runner.state.coding_tasks[task_id]
        assert task.reason == "end_turn"
        assert task.evidence.write_diffs, "approved write is still recorded as evidence"
        assert [a["status"] for a in task.approvals] == ["approved"]
        assert not any(e["name"] == "write.unguarded" for e in task.events)


def test_write_after_denied_permission_request_fails_unguarded(runner: VoiceTaskRunner):
    # The provider only writes when allowed, so a denial leaves no diff and the turn completes.
    # The predicate is what matters here: a denied approval never counts as a guard.
    out = runner.submit(
        "WRITE_DIFF NEEDS_APPROVAL:edit src/app.py",
        client_request_id="denied-1",
    )
    task_id = out["task_id"]

    assert wait_for(lambda: runner._pending_approval is not None), "permission request never arrived"
    assert runner.reply_approval("deny edit src/app.py")["status"] == "denied"

    assert wait_task_terminal(runner, task_id) == "completed"
    with runner._lock:
        task = runner.state.coding_tasks[task_id]
        assert task.evidence.write_diffs == []
        assert not runner._has_unguarded_write(task)


def test_has_unguarded_write_requires_approved_write_permission():
    from hive_planner.voice_bot import CodingTask, TaskEvidence

    task = CodingTask(task_id="t", voice_session_id="v", context_snapshot_id="s", state="running")
    task.evidence = TaskEvidence()
    assert VoiceTaskRunner._has_unguarded_write(task) is False  # no writes at all

    task.evidence.write_diffs.append({"path": "a.py", "old_text": "1\n", "new_text": "2\n"})
    task.evidence.write_events.append("w1")
    assert VoiceTaskRunner._has_unguarded_write(task) is True  # write, no approval

    task.approvals.append({"kind": "write_or_command", "status": "denied"})
    assert VoiceTaskRunner._has_unguarded_write(task) is True  # denial is not a guard

    task.approvals.append({"kind": "plan", "status": "approved"})
    assert VoiceTaskRunner._has_unguarded_write(task) is True  # plan approval is not a write guard

    task.approvals.append({"kind": "write_or_command", "status": "approved", "tool_kind": "edit",
                           "tool_call_id": "w1"})
    assert VoiceTaskRunner._has_unguarded_write(task) is False  # approval with the write's id guards it


def test_approved_execute_approval_does_not_guard_a_file_write():
    from hive_planner.voice_bot import CodingTask, TaskEvidence

    task = CodingTask(task_id="t", voice_session_id="v", context_snapshot_id="s", state="running")
    task.evidence = TaskEvidence()
    VoiceTaskRunner._record_write_event(task, "w1")
    task.approvals.append({"kind": "write_or_command", "status": "approved", "tool_kind": "execute",
                           "tool_call_id": "npm-1"})
    assert VoiceTaskRunner._has_unguarded_write(task) is True  # approved npm test, unapproved edit
    task.approvals.append({"kind": "write_or_command", "status": "approved", "tool_kind": "edit",
                           "tool_call_id": "w1"})
    assert VoiceTaskRunner._has_unguarded_write(task) is False  # the edit approval guards it


def test_approval_for_other_call_id_does_not_guard_write():
    from hive_planner.voice_bot import CodingTask, TaskEvidence

    task = CodingTask(task_id="t", voice_session_id="v", context_snapshot_id="s", state="running")
    task.evidence = TaskEvidence()
    VoiceTaskRunner._record_write_event(task, "w-shell")
    task.approvals.append({"kind": "write_or_command", "status": "approved", "tool_kind": "edit",
                           "tool_call_id": "tc-perm-1"})
    assert VoiceTaskRunner._has_unguarded_write(task) is True  # same kind, different call id


def test_no_diff_write_event_counts_as_a_write():
    from hive_planner.voice_bot import CodingTask, TaskEvidence

    task = CodingTask(task_id="t", voice_session_id="v", context_snapshot_id="s", state="running")
    task.evidence = TaskEvidence()
    VoiceTaskRunner._record_write_event(task, "w-nodiff")
    VoiceTaskRunner._record_write_event(task, "w-nodiff")  # same tool call id: counted once
    assert task.evidence.write_events == ["w-nodiff"]
    assert task.evidence.write_diffs == []
    assert VoiceTaskRunner._has_unguarded_write(task) is True  # no diff, still a write

    task.approvals.append({"kind": "write_or_command", "status": "approved", "tool_kind": "edit",
                           "tool_call_id": "w-nodiff"})
    assert VoiceTaskRunner._has_unguarded_write(task) is False


def test_two_writes_with_one_approval_is_unguarded():
    from hive_planner.voice_bot import CodingTask, TaskEvidence

    task = CodingTask(task_id="t", voice_session_id="v", context_snapshot_id="s", state="running")
    task.evidence = TaskEvidence()
    VoiceTaskRunner._record_write_event(task, "w1")
    VoiceTaskRunner._record_write_event(task, "w2")
    task.approvals.append({"kind": "write_or_command", "status": "approved", "tool_kind": "edit",
                           "tool_call_id": "w1"})
    assert VoiceTaskRunner._has_unguarded_write(task) is True  # 2 writes, 1 approval (w2 unguarded)

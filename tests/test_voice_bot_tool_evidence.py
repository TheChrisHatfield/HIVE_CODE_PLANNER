"""F3: tool-call evidence. Each ingested tool call gets a normalized row with kind, a redacted
truncated command, and its tool call id. Integrated tests run through `runner.submit` and the
live fake ACP child (tests/fixtures/acp_turn_server.py), not through helpers alone.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.voice_task import TOOL_COMMAND_MAX_CHARS, VoiceTaskRunner, redact_command
from voice_turn_support import make_repo, make_runner, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


def test_redact_command_masks_credentials_and_keeps_safe_args():
    out = redact_command("curl -H 'Authorization: Bearer abc.DEF-123' --token=TESTSECRET123 -p hunter2 sk-abcdef123456 ok")
    assert "abc.DEF-123" not in out
    assert "TESTSECRET123" not in out
    assert "sk-abcdef123456" not in out
    assert "curl" in out and "ok" in out
    assert "<redacted>" in out


def test_redact_command_masks_short_p_flag_value():
    out = redact_command("mysql -u root -p hunter2 db")
    assert "hunter2" not in out
    assert "-p <redacted>" in out
    assert "mysql -u root" in out and "db" in out
    # Hyphenated names and long flags are not treated as the short credential flag.
    assert redact_command("pytest --p plug") == "pytest --p plug"


def test_redact_command_truncates_after_masking():
    long = "pytest " + ("x" * 500)
    out = redact_command(long)
    assert len(out) == TOOL_COMMAND_MAX_CHARS
    assert out.endswith("...")
    assert redact_command("ruff check") == "ruff check"


def test_execute_tool_call_records_kind_redacted_command_and_id(runner: VoiceTaskRunner):
    out = runner.submit("EXEC_SECRET lint the module", client_request_id="f3-exec-1")
    task_id = out["task_id"]

    assert wait_task_terminal(runner, task_id) == "completed"
    with runner._lock:
        rows = runner.state.coding_tasks[task_id].evidence.tool_calls

    assert len(rows) == 1
    row = rows[0]
    assert row["tool_call_id"] == "s1"
    assert row["kind"] == "execute"
    assert row["status"] == "completed"
    assert row["command"].startswith("ruff check")
    assert "TESTSECRET123" not in row["command"]
    assert "hunter2" not in row["command"]
    assert "<redacted>" in row["command"]


def test_raw_events_are_redacted_before_they_persist(runner: VoiceTaskRunner):
    """Open gap (deployment-gaps.md): raw ACP payloads are persisted in state.json, so the
    secret in the tool command must not survive there either."""
    out = runner.submit("EXEC_SECRET lint the module", client_request_id="f3-raw-1")
    task_id = out["task_id"]

    assert wait_task_terminal(runner, task_id) == "completed"
    with runner._lock:
        raw = runner.state.coding_tasks[task_id].raw_events
        blob = repr(raw)

    assert raw, "raw provider payloads are still retained (R17)"
    assert "TESTSECRET123" not in blob
    assert "hunter2" not in blob


def test_tool_call_rows_survive_evidence_round_trip():
    from hive_planner.voice_bot import TaskEvidence

    ev = TaskEvidence(tool_calls=[{"tool_call_id": "c1", "kind": "execute",
                                   "command": "pytest -q", "status": "completed"}])
    again = TaskEvidence.from_dict(ev.to_dict())
    assert again.tool_calls == ev.tool_calls
    assert TaskEvidence.from_dict({}).tool_calls == []

"""T026 / R34 — live G6 permission probe. Fixture paths and logged-out CLI never write pass."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import hive_planner.voice_acp as voice_acp
from hive_planner.cli import main
from hive_planner.config import RepoPaths
from hive_planner.voice_acp import AcpClient
from hive_planner.voice_bot import (
    apply_g6_register_result,
    is_fixture_agent_path,
    live_permission,
    permission_shape_ok,
    reject_permission_result,
    summarize_permission_params,
)

TURN_SERVER = Path(__file__).parent / "fixtures" / "acp_turn_server.py"

G6_REGISTER = """# Evidence

| Claim ID | Component | Pinned version | Test | Result | Date | Notes |
|---|---|---|---|---|---|---|
| G2 | Cursor ACP | cli | live-prompt | **pass** | 2026-11-10 | live prompt |
| G6 | Permission | cli | live-permission | **partial** | 2026-11-10 | fixture only |

## Gate closure status

| Gate | Closed? | Rationale |
|---|---|---|
| G6 | No | Fixture only. |
"""


@pytest.fixture
def repo(tmp_path: Path) -> RepoPaths:
    (tmp_path / "AGENTS.md").write_text(
        "## Active feature\n\n- **Voice_Bot** — listed lane.\n", encoding="utf-8"
    )
    register = tmp_path / "docs" / "specs" / "Voice_Bot"
    register.mkdir(parents=True)
    (register / "evidence-register.md").write_text(G6_REGISTER, encoding="utf-8")
    return RepoPaths(root=tmp_path)


def _g6_cell(paths: RepoPaths) -> str:
    for line in (paths.root / "docs" / "specs" / "Voice_Bot" / "evidence-register.md").read_text(
        encoding="utf-8"
    ).splitlines():
        if line.startswith("| G6 |"):
            return line.split("|")[5] if len(line.split("|")) >= 8 else line
    raise AssertionError("G6 row missing")


def test_fixture_path_is_detected():
    assert is_fixture_agent_path(str(TURN_SERVER)) is True


def test_reject_permission_selects_live_reject_option():
    result = reject_permission_result(
        {
            "options": [
                {"optionId": "allow-once", "kind": "allow_once"},
                {"optionId": "reject-once", "kind": "reject_once"},
            ]
        }
    )
    assert result == {"outcome": {"outcome": "selected", "optionId": "reject-once"}}
    assert reject_permission_result({}) == {"outcome": {"outcome": "cancelled"}}


def test_permission_shape_requires_options_or_tool_call():
    ok = summarize_permission_params(
        {"sessionId": "s", "options": [{"kind": "allow_once"}], "toolCall": {"kind": "edit"}}
    )
    ok["method"] = "session/request_permission"
    assert permission_shape_ok(ok)
    assert permission_shape_ok(summarize_permission_params({"toolCall": {"kind": "execute"}}))
    assert permission_shape_ok({"method": "fs/write_text_file", "param_keys": ["path"]})
    assert not permission_shape_ok(summarize_permission_params({"sessionId": "s"}))


def test_logged_out_records_blocked_and_does_not_write_pass(repo):
    result = live_permission(
        repo,
        "Voice_Bot",
        agent_path=r"C:\cursor-agent\agent.cmd",
        record=True,
        env={},
    )
    assert result["g6"] == "blocked"
    assert result["reason"] == "not_logged_in"
    assert result["ok"] is False
    assert result["wrote"] is False
    assert "**pass**" not in _g6_cell(repo)
    assert "**blocked**" in _g6_cell(repo)


def test_fixture_agent_never_writes_pass_even_with_api_key(repo, monkeypatch):
    def fake_open(agent_path, *, cwd=None, server_request_handler=None):
        return AcpClient([sys.executable, str(TURN_SERVER)], cwd=cwd, server_request_handler=server_request_handler)

    monkeypatch.setattr(voice_acp, "open_agent_acp", fake_open)
    result = live_permission(
        repo,
        "Voice_Bot",
        agent_path=str(TURN_SERVER),
        record=True,
        env={"CURSOR_API_KEY": "test-key"},
        instruction="NEEDS_APPROVAL:edit probe",
    )
    assert result["fixture"] is True
    assert result["g6"] == "blocked"
    assert result["reason"] == "fixture_agent"
    assert "**pass**" not in _g6_cell(repo)


def test_logged_in_live_permission_against_turn_server_can_record_pass(repo, monkeypatch):
    def fake_open(agent_path, *, cwd=None, server_request_handler=None):
        return AcpClient([sys.executable, str(TURN_SERVER)], cwd=cwd, server_request_handler=server_request_handler)

    monkeypatch.setattr(voice_acp, "open_agent_acp", fake_open)
    result = live_permission(
        repo,
        "Voice_Bot",
        agent_path=r"C:\cursor-agent\agent.cmd",
        record=True,
        env={"CURSOR_API_KEY": "test-key"},
        timeout=20.0,
        instruction="NEEDS_APPROVAL:edit probe",
    )
    assert result["fixture"] is False
    assert result["g6"] == "pass"
    assert result["ok"] is True
    assert result["wrote"] is False
    assert result["permissions"]
    result["permissions"][0].setdefault("method", "session/request_permission")
    assert permission_shape_ok(result["permissions"][0])
    assert "**pass**" in _g6_cell(repo)
    text = (repo.root / "docs" / "specs" / "Voice_Bot" / "evidence-register.md").read_text(encoding="utf-8")
    assert "| G2 |" in text and "**pass**" in text.split("| G2 |", 1)[1].splitlines()[0]


def test_logged_in_write_after_reject_is_stopped_before_probe_file(repo, monkeypatch):
    def fake_open(agent_path, *, cwd=None, server_request_handler=None):
        return AcpClient([sys.executable, str(TURN_SERVER)], cwd=cwd, server_request_handler=server_request_handler)

    monkeypatch.setattr(voice_acp, "open_agent_acp", fake_open)
    result = live_permission(
        repo,
        "Voice_Bot",
        agent_path=r"C:\cursor-agent\agent.cmd",
        record=True,
        env={"CURSOR_API_KEY": "test-key"},
        timeout=20.0,
        instruction="G6_WRITE_UNLESS_CANCEL",
    )
    assert result["g6"] == "pass"
    assert result["wrote"] is False
    assert not (repo.root / ".hive" / "voice-bot" / "g6-live-probe.tmp").is_file()
    assert "**pass**" in _g6_cell(repo)


def test_logged_in_without_permission_request_is_fail(repo, monkeypatch):
    def fake_open(agent_path, *, cwd=None, server_request_handler=None):
        return AcpClient([sys.executable, str(TURN_SERVER)], cwd=cwd, server_request_handler=server_request_handler)

    monkeypatch.setattr(voice_acp, "open_agent_acp", fake_open)
    result = live_permission(
        repo,
        "Voice_Bot",
        agent_path=r"C:\cursor-agent\agent.cmd",
        record=True,
        env={"CURSOR_API_KEY": "test-key"},
        timeout=20.0,
        instruction="hello read-only",
    )
    assert result["g6"] == "fail"
    assert result["reason"] == "no_permission_request"
    assert "**pass**" not in _g6_cell(repo)
    assert "**fail**" in _g6_cell(repo)


def test_apply_g6_register_leaves_other_rows():
    updated = apply_g6_register_result(G6_REGISTER, "fail", "2026-11-10", "boom")
    assert "**fail**" in updated
    g2 = updated.split("| G2 |", 1)[1].splitlines()[0]
    assert "**pass**" in g2


def test_cli_live_permission_logged_out_exits_zero_with_blocked(repo, monkeypatch, capsys):
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    code = main(
        [
            "--root",
            str(repo.root),
            "voice-bot",
            "live-permission",
            "--feature",
            "Voice_Bot",
            "--agent-path",
            r"C:\cursor-agent\agent.cmd",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert '"g6": "blocked"' in out
    assert '"reason": "not_logged_in"' in out

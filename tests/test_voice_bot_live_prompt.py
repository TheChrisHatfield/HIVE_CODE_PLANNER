"""T023 / R31 — live G2 probe. Fixture paths and logged-out CLI never write pass."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import hive_planner.voice_acp as voice_acp
from hive_planner.cli import main
from hive_planner.config import RepoPaths
from hive_planner.voice_acp import AcpClient
from hive_planner.voice_bot import (
    apply_g2_register_result,
    is_fixture_agent_path,
    live_prompt,
)

TURN_SERVER = Path(__file__).parent / "fixtures" / "acp_turn_server.py"

G2_REGISTER = """# Evidence

| Claim ID | Component | Pinned version | Test | Result | Date | Notes |
|---|---|---|---|---|---|---|
| G1 | Native | x | t | **blocked** | 2026-11-09 | n |
| G2 | Cursor ACP | cli | live-prompt | **blocked** | 2026-11-09 | fixture only |
| G3 | Moshi | x | t | **blocked** | 2026-11-09 | n |
"""


@pytest.fixture
def repo(tmp_path: Path) -> RepoPaths:
    (tmp_path / "AGENTS.md").write_text(
        "## Active feature\n\n- **Voice_Bot** — listed lane.\n", encoding="utf-8"
    )
    register = tmp_path / "docs" / "specs" / "Voice_Bot"
    register.mkdir(parents=True)
    (register / "evidence-register.md").write_text(G2_REGISTER, encoding="utf-8")
    return RepoPaths(root=tmp_path)


def _g2_cell(paths: RepoPaths) -> str:
    for line in (paths.root / "docs" / "specs" / "Voice_Bot" / "evidence-register.md").read_text(
        encoding="utf-8"
    ).splitlines():
        if line.startswith("| G2 |"):
            return line.split("|")[5]
    raise AssertionError("G2 row missing")


def test_fixture_path_is_detected():
    assert is_fixture_agent_path(str(TURN_SERVER)) is True
    assert is_fixture_agent_path(r"C:\Users\x\cursor-agent\agent.cmd") is False


def test_logged_out_records_blocked_and_does_not_write_pass(repo):
    result = live_prompt(
        repo,
        "Voice_Bot",
        agent_path=r"C:\cursor-agent\agent.cmd",
        record=True,
        env={},
    )
    assert result["g2"] == "blocked"
    assert result["reason"] == "not_logged_in"
    assert result["ok"] is False
    assert "**pass**" not in _g2_cell(repo)
    assert "**blocked**" in _g2_cell(repo)


def test_fixture_agent_never_writes_pass_even_with_api_key(repo, monkeypatch):
    def fake_open(agent_path, *, cwd=None, server_request_handler=None):
        return AcpClient([sys.executable, str(TURN_SERVER)], cwd=cwd, server_request_handler=server_request_handler)

    monkeypatch.setattr(voice_acp, "open_agent_acp", fake_open)
    result = live_prompt(
        repo,
        "Voice_Bot",
        agent_path=str(TURN_SERVER),
        record=True,
        env={"CURSOR_API_KEY": "test-key"},
    )
    assert result["fixture"] is True
    assert result["g2"] == "blocked"
    assert result["reason"] == "fixture_agent"
    assert "**pass**" not in _g2_cell(repo)


def test_logged_in_live_prompt_against_turn_server_can_record_pass(repo, monkeypatch):
    def fake_open(agent_path, *, cwd=None, server_request_handler=None):
        return AcpClient([sys.executable, str(TURN_SERVER)], cwd=cwd, server_request_handler=server_request_handler)

    monkeypatch.setattr(voice_acp, "open_agent_acp", fake_open)
    result = live_prompt(
        repo,
        "Voice_Bot",
        agent_path=r"C:\cursor-agent\agent.cmd",
        record=True,
        env={"CURSOR_API_KEY": "test-key"},
        timeout=20.0,
    )
    assert result["fixture"] is False
    assert result["g2"] == "pass"
    assert result["ok"] is True
    assert result["stop_reason"]
    assert "**pass**" in _g2_cell(repo)
    assert "| G1 |" in (repo.root / "docs" / "specs" / "Voice_Bot" / "evidence-register.md").read_text(
        encoding="utf-8"
    )


def test_apply_g2_register_leaves_other_rows():
    updated = apply_g2_register_result(G2_REGISTER, "fail", "2026-11-10", "boom")
    assert "**fail**" in updated
    assert "| G1 |" in updated and "**blocked**" in updated.split("| G1 |", 1)[1].splitlines()[0]


def test_cli_live_prompt_logged_out_exits_zero_with_blocked(repo, monkeypatch, capsys):
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    code = main(
        [
            "--root",
            str(repo.root),
            "voice-bot",
            "live-prompt",
            "--feature",
            "Voice_Bot",
            "--agent-path",
            r"C:\cursor-agent\agent.cmd",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert '"g2": "blocked"' in out
    assert '"reason": "not_logged_in"' in out

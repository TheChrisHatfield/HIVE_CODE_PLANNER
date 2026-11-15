"""T047 / R35 — live allowed-write probe. Blocked paths, fake-ACP pass, and no_write."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import hive_planner.voice_acp as voice_acp
from hive_planner.cli import main
from hive_planner.config import RepoPaths
from hive_planner.voice_acp import AcpClient
from hive_planner.voice_bot import allow_permission_result, live_write

FAKE_SERVER = Path(__file__).parent / "fixtures" / "acp_live_write_server.py"
AGENT = r"C:\cursor-agent\agent.cmd"

G6_PASS = """# Evidence

| Claim ID | Component | Pinned version | Test | Result | Date | Notes |
|---|---|---|---|---|---|---|
| G6 | Permission | cli | live-permission | **pass** | 2026-11-12 | live gate |
"""


@pytest.fixture
def repo(tmp_path: Path) -> RepoPaths:
    (tmp_path / "AGENTS.md").write_text(
        "## Active feature\n\n- **Voice_Bot** — listed lane.\n", encoding="utf-8"
    )
    register = tmp_path / "docs" / "specs" / "Voice_Bot"
    register.mkdir(parents=True)
    (register / "evidence-register.md").write_text(G6_PASS, encoding="utf-8")
    return RepoPaths(root=tmp_path)


def _enable_latch(paths: RepoPaths) -> None:
    cfg = paths.root / ".hive" / "voice-bot" / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"edits_enabled": True}), encoding="utf-8")


def _fake_open(monkeypatch):
    def fake_open(agent_path, *, cwd=None, server_request_handler=None):
        return AcpClient(
            [sys.executable, str(FAKE_SERVER)],
            cwd=cwd,
            server_request_handler=server_request_handler,
        )

    monkeypatch.setattr(voice_acp, "open_agent_acp", fake_open)


def test_allow_permission_selects_allow_option_only():
    picked = allow_permission_result(
        {"options": [{"optionId": "reject-once", "kind": "reject_once"}, {"optionId": "allow-once", "kind": "allow_once"}]}
    )
    assert picked == {"outcome": {"outcome": "selected", "optionId": "allow-once"}}
    assert allow_permission_result({"options": [{"optionId": "reject-once", "kind": "reject_once"}]}) == {
        "outcome": {"outcome": "cancelled"}
    }


def test_logged_out_is_blocked_and_writes_nothing(repo):
    _enable_latch(repo)
    result = live_write(repo, "Voice_Bot", agent_path=AGENT, env={})
    assert result["r35"] == "blocked"
    assert result["reason"] == "not_logged_in"
    assert not (repo.root / ".hive" / "voice-bot" / "live-write-check.txt").exists()


def test_edits_disabled_is_blocked_before_any_session(repo, monkeypatch):
    called = []
    monkeypatch.setattr(voice_acp, "open_agent_acp", lambda *a, **k: called.append(1))
    result = live_write(repo, "Voice_Bot", agent_path=AGENT, env={"CURSOR_API_KEY": "k"})
    assert result["r35"] == "blocked"
    assert result["reason"] == "edits_disabled"
    assert called == []


def test_g6_not_pass_is_blocked(repo, monkeypatch):
    _enable_latch(repo)
    reg = repo.root / "docs" / "specs" / "Voice_Bot" / "evidence-register.md"
    reg.write_text(G6_PASS.replace("**pass**", "**blocked**"), encoding="utf-8")
    result = live_write(repo, "Voice_Bot", agent_path=AGENT, env={"CURSOR_API_KEY": "k"})
    assert result["r35"] == "blocked"
    assert result["reason"] == "g6_not_pass"


def test_fixture_agent_is_refused(repo):
    _enable_latch(repo)
    result = live_write(repo, "Voice_Bot", agent_path=str(FAKE_SERVER), env={"CURSOR_API_KEY": "k"})
    assert result["r35"] == "blocked"
    assert result["reason"] == "fixture_agent"


def test_allowed_agent_write_passes_with_nonce_on_disk(repo, monkeypatch):
    _enable_latch(repo)
    _fake_open(monkeypatch)
    result = live_write(repo, "Voice_Bot", agent_path=AGENT, env={"CURSOR_API_KEY": "k"}, timeout=20.0)
    assert result["r35"] == "pass", result
    assert result["ok"] is True
    assert result["file_present"] is True and result["nonce_match"] is True
    assert result["permissions"] and result["permissions"][0]["method"] == "session/request_permission"
    assert result["mode"] == "agent"
    assert len(result["nonce_hash"]) == 16
    body = (repo.root / ".hive" / "voice-bot" / "live-write-check.txt").read_text(encoding="utf-8")
    assert body.startswith("HIVE_LIVE_WRITE_NONCE=")


def test_agent_that_never_writes_is_no_write(repo, monkeypatch):
    _enable_latch(repo)
    _fake_open(monkeypatch)
    result = live_write(
        repo,
        "Voice_Bot",
        agent_path=AGENT,
        env={"CURSOR_API_KEY": "k"},
        timeout=20.0,
        instruction_suffix=" SKIP_WRITE",
    )
    assert result["r35"] == "no_write"
    assert result["reason"] == "file_missing"
    assert result["file_present"] is False
    assert result["permissions"] == []


def test_g6_row_and_config_are_not_modified_by_live_write(repo, monkeypatch):
    _enable_latch(repo)
    _fake_open(monkeypatch)
    reg = repo.root / "docs" / "specs" / "Voice_Bot" / "evidence-register.md"
    before_reg = reg.read_text(encoding="utf-8")
    before_cfg = (repo.root / ".hive" / "voice-bot" / "config.json").read_text(encoding="utf-8")
    live_write(repo, "Voice_Bot", agent_path=AGENT, env={"CURSOR_API_KEY": "k"}, timeout=20.0)
    assert reg.read_text(encoding="utf-8") == before_reg
    assert (repo.root / ".hive" / "voice-bot" / "config.json").read_text(encoding="utf-8") == before_cfg


def test_cli_live_write_logged_out_exits_zero_blocked(repo, monkeypatch, capsys):
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    code = main(
        ["--root", str(repo.root), "voice-bot", "live-write", "--feature", "Voice_Bot", "--agent-path", AGENT]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert '"r35": "blocked"' in out

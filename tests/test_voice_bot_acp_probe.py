"""T003 wiring — `voice-bot acp-probe` drives the ACP adapter through the HIVE entry point.

The child process is a real subprocess (fake ACP server or a process that exits
immediately). Only the executable path is swapped; the adapter, the probe, and the
failure mapping are the production code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import hive_planner.voice_acp as voice_acp
from hive_planner.cli import main
from hive_planner.config import RepoPaths
from hive_planner.voice_acp import AcpClient
from hive_planner.voice_bot import VoiceBotError, acp_probe

FAKE_SERVER = Path(__file__).parent / "fixtures" / "acp_fake_server.py"


@pytest.fixture
def repo(tmp_path: Path) -> RepoPaths:
    (tmp_path / "AGENTS.md").write_text(
        "## Active feature\n\n- **Voice_Bot** — listed lane.\n", encoding="utf-8"
    )
    return RepoPaths(root=tmp_path)


def _swap_child(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    """Route open_agent_acp to a real child process with the given argv."""

    def fake_open(agent_path, *, cwd=None, server_request_handler=None):
        return AcpClient(argv, cwd=cwd, server_request_handler=server_request_handler)

    monkeypatch.setattr(voice_acp, "open_agent_acp", fake_open)


def test_probe_initializes_over_real_child_process(repo, monkeypatch):
    _swap_child(monkeypatch, [sys.executable, str(FAKE_SERVER)])
    result = acp_probe(repo, "Voice_Bot", agent_path="agent", timeout=10.0)
    assert result["ok"] is True
    assert result["feature"] == "Voice_Bot"
    assert isinstance(result["pid"], int)
    assert result["protocol_version"] is not None


def test_probe_maps_disconnect_to_voice_bot_error(repo, monkeypatch):
    _swap_child(monkeypatch, [sys.executable, "-c", "import sys; sys.exit(0)"])
    with pytest.raises(VoiceBotError, match="ACP probe failed"):
        acp_probe(repo, "Voice_Bot", agent_path="agent", timeout=10.0)


def test_probe_without_cli_fails_loudly(repo, monkeypatch):
    monkeypatch.setattr(
        "hive_planner.voice_bot.resolve_cursor_agent_cli",
        lambda: {"available": False, "path": None},
    )
    with pytest.raises(VoiceBotError, match="Cursor Agent CLI not found"):
        acp_probe(repo, "Voice_Bot")


def test_cli_acp_probe_exit_code_reflects_failure(repo, monkeypatch, capsys):
    _swap_child(monkeypatch, [sys.executable, "-c", "import sys; sys.exit(0)"])
    code = main(
        ["--root", str(repo.root), "voice-bot", "acp-probe", "--feature", "Voice_Bot", "--agent-path", "agent"]
    )
    assert code == 1
    assert "ACP probe failed" in capsys.readouterr().err


def test_cli_acp_probe_success_prints_json(repo, monkeypatch, capsys):
    _swap_child(monkeypatch, [sys.executable, str(FAKE_SERVER)])
    code = main(
        ["--root", str(repo.root), "voice-bot", "acp-probe", "--feature", "Voice_Bot", "--agent-path", "agent"]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out.split("\n", 1)[1])
    assert payload["ok"] is True

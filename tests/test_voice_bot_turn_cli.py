"""Wiring: `voice-bot turn` drives CLI -> VoiceTaskRunner -> AcpClient -> child agent -> task evidence.

Integrated path (wiring audit, T004/T011). Only the executable is swapped to the fixture server.
The exit code must reflect the task outcome, never just that a submit happened.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import hive_planner.voice_task as voice_task
from hive_planner.cli import main
from hive_planner.config import RepoPaths
from hive_planner.voice_acp import AcpClient
from voice_turn_support import TURN_SERVER, make_repo


@pytest.fixture
def repo(tmp_path: Path) -> RepoPaths:
    return make_repo(tmp_path)


def _swap_agent_to_turn_server(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_open(agent_path, *, cwd=None, server_request_handler=None):
        return AcpClient(
            [sys.executable, str(TURN_SERVER)], cwd=cwd, server_request_handler=server_request_handler
        )

    monkeypatch.setattr(voice_task, "open_agent_acp", fake_open)


def _payload(out: str) -> dict:
    return json.loads(out.split("\n", 1)[1])


def test_cli_turn_completes_and_prints_spoken_and_written_results(repo, monkeypatch, capsys):
    _swap_agent_to_turn_server(monkeypatch)
    code = main([
        "--root", str(repo.root), "voice-bot", "turn", "RUN_TESTS_PASS explain add",
        "--feature", "Voice_Bot", "--file", "src/app.py", "--client-request-id", "cli-1",
        "--agent-path", "agent", "--timeout", "20",
    ])
    assert code == 0
    payload = _payload(capsys.readouterr().out)
    assert payload["state"] == "completed"
    assert payload["tests_status"] == "passed"
    assert payload["spoken"].startswith("Tests passed.")
    assert "ran tests, exit 0" in payload["written"]


def test_cli_turn_exit_code_reflects_a_failed_task(repo, monkeypatch, capsys):
    _swap_agent_to_turn_server(monkeypatch)
    code = main([
        "--root", str(repo.root), "voice-bot", "turn", "CRASH_MID_TURN now",
        "--feature", "Voice_Bot", "--client-request-id", "cli-2",
        "--agent-path", "agent", "--timeout", "5",
    ])
    assert code == 1  # unknown is not success
    payload = _payload(capsys.readouterr().out)
    assert payload["state"] == "unknown"
    assert payload["reason"] == "provider_disconnected"


def test_cli_turn_refuses_agent_mode_with_exit_1(repo, monkeypatch, capsys):
    _swap_agent_to_turn_server(monkeypatch)
    # argparse rejects `agent` (choices ask/plan) before any runner exists: no task can be created.
    with pytest.raises(SystemExit) as exc:
        main([
            "--root", str(repo.root), "voice-bot", "turn", "edit it",
            "--feature", "Voice_Bot", "--mode", "agent", "--client-request-id", "cli-3",
            "--agent-path", "agent",
        ])
    assert exc.value.code == 2
    assert not (repo.root / ".hive" / "voice-bot" / "state.json").exists()


def test_cli_turn_without_client_request_id_creates_no_task(repo, monkeypatch, capsys):
    _swap_agent_to_turn_server(monkeypatch)
    code = main([
        "--root", str(repo.root), "voice-bot", "turn", "hello",
        "--feature", "Voice_Bot", "--agent-path", "agent",
    ])
    assert code == 1
    assert "missing_client_request_id" in capsys.readouterr().err
    from hive_planner.voice_bot import load_state

    assert load_state(repo).coding_tasks == {}


def test_missing_agent_binary_is_recorded_as_coding_unavailable(repo, capsys):
    code = main([
        "--root", str(repo.root), "voice-bot", "turn", "hello",
        "--feature", "Voice_Bot", "--client-request-id", "cli-4",
        "--agent-path", str(repo.root / "no-such-agent.exe"), "--timeout", "5",
    ])
    assert code == 1
    payload = _payload(capsys.readouterr().out)
    assert payload["state"] == "failed"
    assert payload["reason"].startswith("coding_unavailable")

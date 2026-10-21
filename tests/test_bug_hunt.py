from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from hive_planner.bug_hunt import (
    BugHuntError,
    install_bug_hunt,
    is_bug_hunt_request,
    render_agent_prompt,
    render_cursor_rule,
)
from hive_planner.cli import main


@pytest.mark.parametrize(
    "text",
    [
        "bug hunt",
        "do a bug hunt",
        "do a bung hunt",
        "bug hun",
        "please hunt for bugs",
        "start hunting bugs",
        "run a bug-hunt",
        "/bug-hunt",
        "Can you bughunt the launcher?",
        "perform a bug hunt on Home",
        "start bug hunting",
        "run some bug-hunting",
        "do bug hunts",
        "please hunt for any bugs",
    ],
)
def test_is_bug_hunt_request_starts_the_loop(text: str) -> None:
    assert is_bug_hunt_request(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "fix the login button",
        "how does bug hunt work",
        "where is the bug-hunt command",
        "what is a bug hunt",
        "does bug hunt install files",
        "how do I install bug hunt",
    ],
)
def test_is_bug_hunt_request_rejects_docs_and_noise(text: str) -> None:
    assert is_bug_hunt_request(text) is False


def test_cursor_rule_matches_derivative_phrases() -> None:
    rule = render_cursor_rule()
    assert "alwaysApply: true" in rule
    assert "hunt for bugs" in rule
    assert "Match intent" in rule
    assert "how to install" in rule
    assert "Do not stop after one bug" in rule


def test_prompt_keeps_the_loop_moving() -> None:
    text = render_agent_prompt(50)
    assert "50-iteration" in text
    assert "without waiting for the user" in text
    assert "repeat the process autonomously" in text
    assert "Do not ask the user whether to continue" in text
    assert "Do not push" in text
    assert "Wiring audit" in text


def test_install_writes_command_and_packet(tmp_path: Path) -> None:
    result = install_bug_hunt(tmp_path, iterations=50)
    command = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    packet = (tmp_path / ".hive" / "bug-hunt" / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    rule = (tmp_path / ".cursor" / "rules" / "bug-hunt.mdc").read_text(encoding="utf-8")
    scripts = (tmp_path / "scripts" / "bug-hunt.md").read_text(encoding="utf-8")
    assert command.startswith("---\n")
    assert "50-iteration" in command
    assert "50-iteration" in packet
    assert "50-iteration" in scripts
    assert "alwaysApply: true" in rule
    assert "bug hunt" in rule
    assert "bug hun" in rule
    assert "bung hunt" in rule
    assert "do a bug hunt" in rule
    assert "do a bung hunt" in rule
    assert "hunt for bugs" in rule
    assert "dual-lane" not in command
    assert result.command_path.is_file()
    assert result.rule_path.is_file()
    assert result.packet_path.is_file()
    assert ".cursor/commands/bug-hunt.md" in result.files_written
    assert "bung hunt" in command
    assert "do a bug hunt" in command


def test_install_appends_repo_overlay(tmp_path: Path) -> None:
    overlay = tmp_path / ".hive" / "bug-hunt" / "repo-overlay.md"
    overlay.parent.mkdir(parents=True)
    overlay.write_text("## This repo\n\nRun coco_bug_hunt_audit.py after each fix.\n", encoding="utf-8")
    result = install_bug_hunt(tmp_path, iterations=8)
    command = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    scripts = (tmp_path / "scripts" / "bug-hunt.md").read_text(encoding="utf-8")
    assert "coco_bug_hunt_audit.py" in command
    assert "coco_bug_hunt_audit.py" in scripts
    assert command.count("coco_bug_hunt_audit.py") == 1
    assert ".cursor/commands/bug-hunt.md" in result.files_written
    install_bug_hunt(tmp_path, iterations=8)
    again = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert again.count("coco_bug_hunt_audit.py") == 1


def test_install_skips_existing_when_not_forced(tmp_path: Path) -> None:
    first = install_bug_hunt(tmp_path, iterations=10)
    assert first.files_written
    command = tmp_path / ".cursor" / "commands" / "bug-hunt.md"
    command.write_text("custom\n", encoding="utf-8")
    second = install_bug_hunt(tmp_path, iterations=20, force=False)
    assert second.files_written == []
    assert command.read_text(encoding="utf-8") == "custom\n"


def test_install_appends_dual_lane_when_rule_present(tmp_path: Path) -> None:
    dual = tmp_path / ".cursor" / "rules" / "bug-hunt-dual-lane.mdc"
    dual.parent.mkdir(parents=True)
    dual.write_text("---\nalwaysApply: true\n---\n# dual\n", encoding="utf-8")
    install_bug_hunt(tmp_path, iterations=10)
    command = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert "10-iteration" in command
    assert "dual-lane" in command
    assert "bug-hunt-dual-lane.mdc" in command


def test_iterations_out_of_range(tmp_path: Path) -> None:
    with pytest.raises(BugHuntError):
        install_bug_hunt(tmp_path, iterations=0)


def test_cli_print_does_not_write(tmp_path: Path) -> None:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = main(["--root", str(tmp_path), "bug-hunt", "--print"])
    assert code == 0
    assert "50-iteration" in stdout.getvalue()
    assert not (tmp_path / ".cursor" / "commands" / "bug-hunt.md").exists()


def test_cli_installs_into_root(tmp_path: Path) -> None:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = main(["--root", str(tmp_path), "bug-hunt", "--iterations", "12"])
    assert code == 0
    text = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert "12-iteration" in text
    assert "command" in stdout.getvalue()

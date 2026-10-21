from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from hive_planner.bug_hunt import BugHuntError, install_bug_hunt, render_agent_prompt
from hive_planner.cli import main


def test_prompt_keeps_the_loop_moving() -> None:
    text = render_agent_prompt(50)
    assert "50-iteration" in text
    assert "without waiting for the user" in text
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
    assert "dual-lane" not in command
    assert result.command_path.is_file()
    assert result.rule_path.is_file()
    assert result.packet_path.is_file()


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

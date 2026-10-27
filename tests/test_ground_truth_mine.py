from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from hive_planner.cli import main
from hive_planner.ground_truth_mine import (
    install_ground_truth_mine,
    is_ground_truth_mine_request,
    missing_ground_truth_mine_artifacts,
    preview_agent_prompt,
    render_cursor_rule,
)


@pytest.mark.parametrize(
    "text",
    [
        "okay runner ground truth on mine",
        "ok runner ground truth on mine",
        "runner ground truth on mine",
        "ground truth on mine",
        "run the ground truth mine",
        "runner ground truth mine",
        "/ground-truth-on-mine",
        "/runner-ground-truth-on-mine",
        "okay, runner, ground truth on mine for the denoiser width",
    ],
)
def test_is_ground_truth_mine_request_starts_the_mine(text: str) -> None:
    assert is_ground_truth_mine_request(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "Table 1 ground truth is 0.22",
        "how does ground truth on mine work",
        "where is the ground-truth-on-mine command",
        "what is ground truth on mine",
        "does ground truth on mine write files",
    ],
)
def test_is_ground_truth_mine_request_rejects_docs_and_paper_mentions(text: str) -> None:
    assert is_ground_truth_mine_request(text) is False


def test_cursor_rule_names_the_call_and_the_command() -> None:
    rule = render_cursor_rule()
    assert "alwaysApply: true" in rule
    assert "okay runner ground truth on mine" in rule
    assert ".cursor/commands/ground-truth-on-mine.md" in rule
    assert "scripts/ground-truth-on-mine.md" in rule
    assert "how to call it" in rule


def test_install_leaves_no_tmp_ground_truth_files(tmp_path: Path) -> None:
    install_ground_truth_mine(tmp_path)
    leftovers = [path for path in tmp_path.rglob("*.tmp") if path.is_file()]
    assert leftovers == []
    assert (tmp_path / ".cursor" / "commands" / "ground-truth-on-mine.md").is_file()


def test_install_writes_hive_packet_and_keeps_overlay(tmp_path: Path) -> None:
    overlay = tmp_path / ".hive" / "ground-truth-on-mine" / "repo-overlay.md"
    overlay.parent.mkdir(parents=True)
    overlay.write_text("## This repo\n\nseam_flow.pdf pins the paper.\n", encoding="utf-8")
    result = install_ground_truth_mine(tmp_path)
    command = (tmp_path / ".cursor" / "commands" / "ground-truth-on-mine.md").read_text(encoding="utf-8")
    packet = (tmp_path / ".hive" / "ground-truth-on-mine" / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    scripts = (tmp_path / "scripts" / "ground-truth-on-mine.md").read_text(encoding="utf-8")
    assert command.startswith("---\n")
    assert "temporary ground truth" in command
    assert "seam_flow.pdf pins the paper." in command
    assert packet == scripts
    assert "seam_flow.pdf pins the paper." in packet
    assert overlay.read_text(encoding="utf-8").startswith("## This repo")
    assert ".hive/ground-truth-on-mine/AGENT_PROMPT.md" in result.files_written
    assert missing_ground_truth_mine_artifacts(tmp_path) == []
    assert preview_agent_prompt(tmp_path).count("seam_flow.pdf pins the paper.") == 1


def test_cli_print_does_not_write(tmp_path: Path) -> None:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = main(["--root", str(tmp_path), "ground-truth-on-mine", "--print"])
    assert code == 0
    assert "temporary ground truth" in stdout.getvalue()
    assert not (tmp_path / ".cursor" / "commands" / "ground-truth-on-mine.md").exists()


def test_hive_prompt_template_points_at_the_installed_command() -> None:
    from hive_planner.launcher.agent_prompt_templates import get_agent_prompt_template

    found = get_agent_prompt_template("research.ground_truth_mine")
    assert found is not None
    assert found.prompt.lstrip().startswith("okay runner ground truth on mine")
    assert "@.cursor/commands/ground-truth-on-mine.md" in found.prompt


def test_cli_install_writes_the_packet(tmp_path: Path) -> None:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = main(["--root", str(tmp_path), "ground-truth-on-mine"])
    assert code == 0
    assert "AGENT_PROMPT.md" in stdout.getvalue()
    assert (tmp_path / ".hive" / "ground-truth-on-mine" / "AGENT_PROMPT.md").is_file()
    assert (tmp_path / ".cursor" / "rules" / "ground-truth-on-mine.mdc").is_file()

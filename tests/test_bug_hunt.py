from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from hive_planner.bug_hunt import (
    BugHuntError,
    install_bug_hunt,
    is_bug_hunt_request,
    missing_bug_hunt_artifacts,
    preview_agent_prompt,
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
        "use this prompt to check you implenationtat of the bug hunt script",
        "Execute a continuous 50-iteration bug-hunting and wiring verification loop",
        "hunt some bugs",
        "please hunting for more bugs",
        "bu hunt",
        "run another loop to fix bugs",
        "loop to fix bugs",
        "please run another loop to fix bugs",
        "end to end bug hunt",
        "run an end to end bug hunt",
        "don't wait, start a bug hunt",
        "stop explaining and run a bug hunt",
        "cancel that and start a bug hunt",
        "read the bug hunt command and start a bug hunt",
        "look at the script and then run a bug hunt",
        "this bug hunt",
        "please start this bug hunt",
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
        "please tell me how does bug hunt work",
        "how to run a bug hunt",
        "Can you tell me where is the bug-hunt command",
        "review the bug hunt script for bugs",
        "check the bug hunt script for errors",
        "look at the bug hunt script",
        "summarize the bug hunt script",
        "audit the bug hunt script",
        "describe the bug hunt flow",
        "explain bug hunting",
        "tell me about bug hunts",
        "walk me through the bug hunt",
        "do not run the bug hunt",
        "don't start the bug hunt",
        "do not start a bug hunt",
        "never run the bug hunt",
        "stop the bug hunt",
        "cancel the bug hunt",
        "wait for the bug hunt to finish",
        "the bug hunts of yesterday",
        "skip the bug hunt",
        "disable the bug hunt",
        "turn off the bug hunt",
        "kill the bug hunt",
        "never bug hunt",
        "please never bug hunt",
        "I do not want a bug hunt",
        "without running a bug hunt",
        "do not loop to fix bugs",
        "don't loop to fix bugs",
    ],
)
def test_is_bug_hunt_request_rejects_docs_and_noise(text: str) -> None:
    assert is_bug_hunt_request(text) is False


def test_cursor_rule_matches_derivative_phrases() -> None:
    rule = render_cursor_rule()
    assert "alwaysApply: true" in rule
    assert "hunt for bugs" in rule
    assert "run another loop to fix bugs" in rule
    assert "Match intent" in rule
    assert "how to install" in rule
    assert "Do not stop after one bug" in rule
    assert "A request to stop, cancel, pause, skip, disable, or wait for the hunt is not a start signal" in rule
    assert "end to end bug hunt" in rule


def test_prompt_keeps_the_loop_moving() -> None:
    text = render_agent_prompt(50)
    assert "50-iteration" in text
    assert "Do not ask the user whether to continue" in text
    assert "not skippable" in text
    assert "10 seconds" in text
    assert "continue.json" in text
    assert "not a wait between passes" in text
    assert "Pause on this step" not in text
    assert "Do not end the hunt here" not in text
    assert "repeat across separate inference passes" in text
    assert "Do not ask the user whether to continue" in text
    assert "Do not push" in text
    assert "Wiring audit" in text
    assert "Potential:" in text
    assert "two readers of the same fact" in text
    assert "neither a confirmed bug nor a potential bug" in text
    assert "I did not reproduce it this session" in text
    assert "Where to look" in text
    assert "0.35" in text
    assert "logistic regression" in text
    assert "recorded and skipped" in text
    assert "not a quota" in text
    assert "reverted commit" in text
    assert "record-and-skip" in text
    assert "Fit a classifier only after at least 30 completed rows" in text
    assert "do not invent a probability" in text
    assert "keep the weighted sum and treat any signal as qualifying" in text
    assert "when the regression cannot be fit, qualifying means any weighted-sum signal" in text
    assert "when the regression is fit" in text
    assert "once the location model exists" not in text
    assert "Rank which tests to run" in text
    assert "The weighted sum is not a probability" in text
    assert "An unopened location is not an empty search" in text
    assert "do not run the self-review" in text
    assert "A confirmed bug that meets the step 1 bar is **fix**" in text
    assert "0.65" in text
    assert "at least 30 completed rows" in text
    assert "restore only this iteration's uncommitted edits" in text
    assert "A failed review is not an empty search" in text
    assert "If that commit fails, restore only this iteration's uncommitted edits and use `review-failed` instead." in text
    assert "review-failed" in text
    assert "written once, after the outcome is known" in text
    assert "Do not append a second row for the same location in this run" in text
    assert "Do not end the hunt here" not in text
    assert "Before those 30 rows exist, there is no floor" in text
    assert ".hive/bug-hunt/rank-rows.jsonl" in text
    assert "Leave locations under that floor unopened" in text
    assert "Logic-error rotation" in text
    assert "including when the harness is missing" in text
    assert "mark this run's opened set" in text
    assert "A hunt starts after `active` was written false for a stop condition" in text


def test_pause_zero_skips_the_wait() -> None:
    text = render_agent_prompt(50, pause_seconds=0)
    assert "pause is 0 seconds" in text
    assert "do not wait between passes" in text
    assert "The hook waits, then" not in text
    assert "The hook sets active to false, then starts the next inference pass." in text
    assert "not skippable" not in text
    assert "Do not ask the user whether to continue" in text
    assert "two consecutive empty searches" in text


def test_pause_blank_is_ten_and_a_positive_number_is_the_wait() -> None:
    from hive_planner.bug_hunt import parse_pause_seconds, validate_pause_seconds

    assert validate_pause_seconds(None) == 10
    assert parse_pause_seconds("") == 10
    assert parse_pause_seconds("  ") == 10
    assert parse_pause_seconds("0") == 0
    assert parse_pause_seconds("0.0") == 0
    assert parse_pause_seconds("15") == 15
    assert parse_pause_seconds("10.0") == 10
    with pytest.raises(BugHuntError):
        parse_pause_seconds("-1")
    with pytest.raises(BugHuntError):
        parse_pause_seconds("soon")
    with pytest.raises(BugHuntError):
        parse_pause_seconds("9223372037")
    text = render_agent_prompt(4, pause_seconds=15)
    assert "15 seconds" in text
    assert "not skippable" in text


def test_cli_pause_accepts_a_whole_decimal(tmp_path: Path) -> None:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = main(["--root", str(tmp_path), "bug-hunt", "--print", "--pause-seconds", "10.0"])
    assert code == 0
    assert "pause is 10 seconds" in stdout.getvalue()
    assert not (tmp_path / ".cursor" / "commands" / "bug-hunt.md").exists()


def test_cli_iterations_accepts_a_whole_decimal(tmp_path: Path) -> None:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = main(["--root", str(tmp_path), "bug-hunt", "--print", "--iterations", "50.0"])
    assert code == 0
    assert "50 committed fixes is the ceiling" in stdout.getvalue()


def test_install_writes_the_pause_into_the_script(tmp_path: Path) -> None:
    result = install_bug_hunt(tmp_path, iterations=4, pause_seconds=0)
    command = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert result.pause_seconds == 0
    assert "pause is 0 seconds" in command
    assert "do not wait between passes" in command
    assert result.to_dict()["pause_seconds"] == 0


def test_continue_hook_waits_then_starts_the_next_pass(tmp_path: Path) -> None:
    import json
    import time

    from hive_planner.bug_hunt_continue import apply_continue, plan_continue

    waited: list[int] = []
    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"active": True, "pause_seconds": 10}), encoding="utf-8")
    payload = apply_continue(tmp_path, sleep=lambda seconds: waited.append(seconds))
    assert waited == [10]
    assert "followup_message" in payload
    assert "next inference pass" in payload["followup_message"]
    assert "consecutive-empty count named in that script" in payload["followup_message"]
    assert "pause_seconds\": 0" not in payload["followup_message"]
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False
    assert apply_continue(tmp_path, sleep=lambda seconds: waited.append(seconds)) == {}
    assert plan_continue({"active": 1, "pause_seconds": "10.0"})[0] == 10
    assert plan_continue({"active": "true", "pause_seconds": "0"})[1]["followup_message"]
    assert plan_continue({"active": True, "pause_seconds": 0})[0] == 0
    assert plan_continue({"active": True, "pause_seconds": "10"})[0] == 10
    assert plan_continue({"active": True, "pause_seconds": 10.0})[0] == 10
    assert plan_continue({"active": False, "pause_seconds": 10})[1] == {}
    state_path.write_text(
        json.dumps({"active": True, "pause_seconds": "soon"}),
        encoding="utf-8",
    )
    assert apply_continue(tmp_path, sleep=lambda seconds: waited.append(seconds)) == {}
    assert waited == [10]
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False
    assert not (state_path.with_name(state_path.name + ".tmp")).exists()


def test_continue_hook_zero_does_not_wait_and_abort_consumes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    from hive_planner.bug_hunt_continue import main

    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"active": True, "pause_seconds": 0}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin.read", lambda: '{"status":"completed"}')
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main() == 0
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False

    state_path.write_text(json.dumps({"active": True, "pause_seconds": 10}), encoding="utf-8")
    slept: list[int] = []
    monkeypatch.setattr("hive_planner.bug_hunt_continue.time.sleep", lambda seconds: slept.append(seconds))
    monkeypatch.setattr("sys.stdin.read", lambda: '{"status":"aborted"}')
    assert main() == 0
    assert slept == []
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False


def test_pause_beyond_the_sleep_limit_falls_back_to_the_script(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt_continue import apply_continue

    command = tmp_path / ".cursor" / "commands" / "bug-hunt.md"
    command.parent.mkdir(parents=True)
    command.write_text("This run's pause is 10 seconds.\n", encoding="utf-8")
    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text('{"active": true, "pause_seconds": 100000000000000000000}', encoding="utf-8")
    slept: list[int] = []
    payload = apply_continue(tmp_path, sleep=lambda seconds: slept.append(seconds))
    assert slept == [10]
    assert "followup_message" in payload
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False


def test_missing_pause_uses_the_script_not_the_ten_second_default(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt_continue import apply_continue

    command = tmp_path / ".cursor" / "commands" / "bug-hunt.md"
    command.parent.mkdir(parents=True)
    command.write_text("This run's pause is 0 seconds.\n", encoding="utf-8")
    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text('{"active": true}', encoding="utf-8")
    slept: list[int] = []
    payload = apply_continue(tmp_path, sleep=lambda seconds: slept.append(seconds))
    assert slept == []
    assert "followup_message" in payload
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False


def test_continue_hook_finds_the_file_above_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from hive_planner.bug_hunt_continue import main

    repo = tmp_path / "repo"
    sub = repo / "src"
    sub.mkdir(parents=True)
    state_path = repo / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"active": True, "pause_seconds": 0}), encoding="utf-8")
    monkeypatch.chdir(sub)
    monkeypatch.setattr("sys.stdin.read", lambda: '{"status":"completed"}')
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main() == 0
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False


def test_continue_hook_honors_state_counters_when_active_was_left_true(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt_continue import apply_continue

    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        '{"active": true, "pause_seconds": 0, "ceiling": 50, "committed": 50, "consecutive_empty": 0}',
        encoding="utf-8",
    )
    slept: list[int] = []
    payload = apply_continue(tmp_path, sleep=lambda seconds: slept.append(seconds))
    assert payload == {}
    assert slept == []
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False

    state_path.write_text(
        '{"active": true, "pause_seconds": 0, "ceiling": 50, "committed": 3, "consecutive_empty": 2}',
        encoding="utf-8",
    )
    payload = apply_continue(tmp_path, sleep=lambda seconds: slept.append(seconds))
    assert payload == {}
    assert slept == []
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False

    state_path.write_text(
        '{"active": true, "pause_seconds": 0, "stop": 1}',
        encoding="utf-8",
    )
    payload = apply_continue(tmp_path, sleep=lambda seconds: slept.append(seconds))
    assert payload == {}
    assert slept == []
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False


def test_continue_hook_does_not_use_a_parent_projects_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from hive_planner.bug_hunt_continue import main

    outer = tmp_path / "outer"
    child = outer / "child"
    (child / "src").mkdir(parents=True)
    (child / ".git").mkdir()
    state_path = outer / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"active": True, "pause_seconds": 0}), encoding="utf-8")
    monkeypatch.chdir(child / "src")
    monkeypatch.setattr("sys.stdin.read", lambda: '{"status":"completed"}')
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main() == 0
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is True


def test_render_continue_hook_reads_packaged_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.bug_hunt import render_continue_hook

    packaged = tmp_path / "hive_planner" / "bug_hunt_continue.py"
    packaged.parent.mkdir(parents=True)
    packaged.write_text("# packaged hook\n", encoding="utf-8")
    monkeypatch.setattr("hive_planner.bug_hunt.__file__", str(tmp_path / "missing" / "bug_hunt.py"))
    monkeypatch.setattr("hive_planner.bug_hunt.sys._MEIPASS", str(tmp_path), raising=False)
    assert render_continue_hook() == "# packaged hook\n"


def test_install_registers_continue_hook_and_keeps_other_events(tmp_path: Path) -> None:
    import json

    hooks = tmp_path / ".cursor" / "hooks.json"
    hooks.parent.mkdir(parents=True)
    hooks.write_text(
        json.dumps({"version": 1, "hooks": {"workspaceOpen": [{"command": "py -3.11 keep.py"}]}}),
        encoding="utf-8",
    )
    install_bug_hunt(tmp_path, iterations=50, pause_seconds=10)
    command = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert "50 committed fixes is the ceiling" in command
    assert "50-iteration ceiling" in command
    data = json.loads(hooks.read_text(encoding="utf-8"))
    assert data["hooks"]["workspaceOpen"][0]["command"] == "py -3.11 keep.py"
    stop = data["hooks"]["stop"]
    assert any(item["command"] == "py -3.11 .cursor/hooks/bug_hunt_continue.py" for item in stop)
    assert stop[-1]["timeout"] == 86400
    assert (tmp_path / ".cursor" / "hooks" / "bug_hunt_continue.py").is_file()
    assert missing_bug_hunt_artifacts(tmp_path) == []
    install_bug_hunt(tmp_path, iterations=50, pause_seconds=100000)
    data = json.loads(hooks.read_text(encoding="utf-8"))
    assert data["hooks"]["workspaceOpen"][0]["command"] == "py -3.11 keep.py"
    assert data["hooks"]["stop"][-1]["timeout"] == 100030


def test_install_does_not_replace_broken_hooks_json(tmp_path: Path) -> None:
    hooks = tmp_path / ".cursor" / "hooks.json"
    hooks.parent.mkdir(parents=True)
    original = '{"version": 1, "hooks": {"workspaceOpen": [}'
    hooks.write_text(original, encoding="utf-8")
    with pytest.raises(BugHuntError, match="not valid JSON"):
        install_bug_hunt(tmp_path, iterations=50)
    assert hooks.read_text(encoding="utf-8") == original
    assert not (tmp_path / ".cursor" / "commands" / "bug-hunt.md").exists()


def test_install_merges_a_hooks_file_with_a_bom_or_utf16(tmp_path: Path) -> None:
    import json

    original = {"version": 1, "hooks": {"workspaceOpen": [{"command": "py -3.11 keep.py"}]}}
    payload = json.dumps(original)
    for encoding, write in (
        ("utf-8-sig", lambda path: path.write_bytes(b"\xef\xbb\xbf" + payload.encode("utf-8"))),
        ("utf-16", lambda path: path.write_text(payload, encoding="utf-16")),
    ):
        project = tmp_path / encoding
        hooks = project / ".cursor" / "hooks.json"
        hooks.parent.mkdir(parents=True)
        write(hooks)
        install_bug_hunt(project, iterations=50, pause_seconds=10)
        data = json.loads(hooks.read_text(encoding="utf-8"))
        assert data["hooks"]["workspaceOpen"][0]["command"] == "py -3.11 keep.py"
        assert any(
            item["command"] == "py -3.11 .cursor/hooks/bug_hunt_continue.py"
            for item in data["hooks"]["stop"]
        )
        assert missing_bug_hunt_artifacts(project) == []


def test_install_leaves_no_tmp_bug_hunt_files(tmp_path: Path) -> None:
    install_bug_hunt(tmp_path, iterations=50)
    leftovers = [path for path in tmp_path.rglob("*.tmp") if path.is_file()]
    assert leftovers == []
    assert (tmp_path / ".cursor" / "commands" / "bug-hunt.md").is_file()


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


def test_install_skips_unreadable_overlay(tmp_path: Path) -> None:
    overlay = tmp_path / ".hive" / "bug-hunt" / "repo-overlay.md"
    overlay.parent.mkdir(parents=True)
    overlay.write_bytes(b"\xff\xfe\x00\x00")
    result = install_bug_hunt(tmp_path, iterations=4)
    command = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert "4-iteration" in command
    assert result.command_path.is_file()
    assert preview_agent_prompt(tmp_path, 4).count("4-iteration") == 1


def test_install_skips_existing_when_not_forced(tmp_path: Path) -> None:
    first = install_bug_hunt(tmp_path, iterations=10)
    assert first.files_written
    command = tmp_path / ".cursor" / "commands" / "bug-hunt.md"
    command.write_text("custom\n", encoding="utf-8")
    second = install_bug_hunt(tmp_path, iterations=20, force=False)
    assert second.files_written == []
    assert command.read_text(encoding="utf-8") == "custom\n"


def test_install_force_does_not_report_unchanged_files(tmp_path: Path) -> None:
    first = install_bug_hunt(tmp_path, iterations=10, pause_seconds=10)
    assert ".cursor/commands/bug-hunt.md" in first.files_written
    second = install_bug_hunt(tmp_path, iterations=10, pause_seconds=10)
    assert second.files_written == []


def test_install_appends_dual_lane_when_rule_present(tmp_path: Path) -> None:
    dual = tmp_path / ".cursor" / "rules" / "bug-hunt-dual-lane.mdc"
    dual.parent.mkdir(parents=True)
    dual.write_text("---\nalwaysApply: true\n---\n# dual\n", encoding="utf-8")
    install_bug_hunt(tmp_path, iterations=10)
    command = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert "10-iteration" in command
    assert "dual-lane" in command
    assert "bug-hunt-dual-lane.mdc" in command
    assert "One location per iteration still holds" in command
    assert "Batch related findings" not in command


def test_install_resolves_code_workspace_to_folder(tmp_path: Path) -> None:
    import json

    folder = tmp_path / "app"
    folder.mkdir()
    (folder / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    workspace = tmp_path / "hive.code-workspace"
    workspace.write_text(json.dumps({"folders": [{"path": "app"}]}), encoding="utf-8")
    result = install_bug_hunt(workspace, iterations=3)
    assert result.root == folder.resolve()
    assert (folder / ".cursor" / "commands" / "bug-hunt.md").is_file()
    assert missing_bug_hunt_artifacts(workspace) == []
    overlay = folder / ".hive" / "bug-hunt" / "repo-overlay.md"
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.write_text("workspace-overlay-token\n", encoding="utf-8")
    assert "workspace-overlay-token" in preview_agent_prompt(workspace, 3)


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


def test_cli_print_includes_repo_overlay(tmp_path: Path) -> None:
    overlay = tmp_path / ".hive" / "bug-hunt" / "repo-overlay.md"
    overlay.parent.mkdir(parents=True)
    overlay.write_text("## This repo\n\nRun coco_bug_hunt_audit.py after each fix.\n", encoding="utf-8")
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = main(["--root", str(tmp_path), "bug-hunt", "--print", "--iterations", "8"])
    assert code == 0
    text = stdout.getvalue()
    assert "8-iteration" in text
    assert "coco_bug_hunt_audit.py" in text
    assert preview_agent_prompt(tmp_path, 8).count("coco_bug_hunt_audit.py") == 1
    assert not (tmp_path / ".cursor" / "commands" / "bug-hunt.md").exists()


def test_missing_bug_hunt_artifacts_lists_absent_files(tmp_path: Path) -> None:
    assert missing_bug_hunt_artifacts(tmp_path) == [
        ".cursor/commands/bug-hunt.md",
        ".cursor/rules/bug-hunt.mdc",
        ".hive/bug-hunt/AGENT_PROMPT.md",
        "scripts/bug-hunt.md",
        ".cursor/hooks/bug_hunt_continue.py",
        ".cursor/hooks.json#stop:py -3.11 .cursor/hooks/bug_hunt_continue.py",
    ]
    install_bug_hunt(tmp_path, iterations=4)
    assert missing_bug_hunt_artifacts(tmp_path) == []
    (tmp_path / ".cursor" / "rules" / "bug-hunt.mdc").unlink()
    assert missing_bug_hunt_artifacts(tmp_path) == [".cursor/rules/bug-hunt.mdc"]


def test_preview_and_install_accept_str_root(tmp_path: Path) -> None:
    overlay = tmp_path / ".hive" / "bug-hunt" / "repo-overlay.md"
    overlay.parent.mkdir(parents=True)
    overlay.write_text("Run coco_bug_hunt_audit.py after each fix.\n", encoding="utf-8")
    text = preview_agent_prompt(str(tmp_path), 7)
    assert "7-iteration" in text
    assert "coco_bug_hunt_audit.py" in text
    result = install_bug_hunt(str(tmp_path), iterations=7)
    assert result.command_path.is_file()
    assert missing_bug_hunt_artifacts(str(tmp_path)) == []


def test_cli_installs_into_workspace_folder(tmp_path: Path) -> None:
    import json

    folder = tmp_path / "app"
    folder.mkdir()
    (folder / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    workspace = tmp_path / "hive.code-workspace"
    workspace.write_text(json.dumps({"folders": [{"path": "app"}]}), encoding="utf-8")
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = main(["--root", str(workspace), "bug-hunt", "--iterations", "5"])
    assert code == 0
    assert (folder / ".cursor" / "commands" / "bug-hunt.md").is_file()
    assert "5-iteration" in (folder / ".cursor" / "commands" / "bug-hunt.md").read_text(
        encoding="utf-8"
    )
    out = stdout.getvalue()
    assert str(folder.resolve()) in out
    assert f"Root: {workspace}" not in out


def test_cli_reports_oserror_instead_of_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(_root, **_kwargs):
        raise OSError("Permission denied")

    monkeypatch.setattr("hive_planner.bug_hunt.install_bug_hunt", _boom)
    stderr = io.StringIO()
    stdout = io.StringIO()
    from contextlib import redirect_stderr

    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(["--root", str(tmp_path), "bug-hunt"])
    assert code == 1
    assert "Permission denied" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()
    assert "Traceback" not in stdout.getvalue()


def test_cli_installs_into_root(tmp_path: Path) -> None:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = main(["--root", str(tmp_path), "bug-hunt", "--iterations", "12"])
    assert code == 0
    text = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert "12-iteration" in text
    assert "command" in stdout.getvalue()

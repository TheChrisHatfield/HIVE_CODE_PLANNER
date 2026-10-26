"""Tests for Python implementation-loop coordinator gates."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from hive_planner.implementation_loop import (
    GIT_IDENTITY,
    PACK_1,
    PACK_4,
    CoordinatorError,
    _check_off_task,
    _last_outcome,
    coordinator_accept,
    coordinator_commit,
    coordinator_handoff,
    coordinator_start,
    install_implementation_loop,
    parse_result_entries,
    render_cursor_command,
    render_role_coordinator,
)


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(GIT_IDENTITY)
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
        check=check,
    )


@pytest.fixture()
def loop_root(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / ".hive").mkdir()
    (root / ".hive" / "project.json").write_text(json.dumps({"project_name": "proj"}), encoding="utf-8")
    (root / "docs" / "specs" / "feature-x").mkdir(parents=True)
    (root / "docs" / "delta" / "20_micro").mkdir(parents=True)
    (root / "docs" / "delta" / "20_micro" / "feature-x.md").write_text("# micro\n", encoding="utf-8")
    (root / "docs" / "specs" / "feature-x" / "spec.md").write_text("# spec\n", encoding="utf-8")
    (root / "docs" / "specs" / "feature-x" / "plan.md").write_text("# plan\n", encoding="utf-8")
    (root / "docs" / "specs" / "feature-x" / "tasks.md").write_text(
        "# tasks\n\n## Slice\n\n- [ ] T001 do the thing\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "proj"\n\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
        encoding="utf-8",
    )
    _git(root, "init")
    _git(root, "checkout", "-b", "feature-x")
    (root / "README.md").write_text("ok\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    return root


def _install_ready(root: Path, pack: str = PACK_4) -> None:
    install_implementation_loop(root, pack)
    commands_path = root / ".hive/implementation-loop/commands.json"
    commands = json.loads(commands_path.read_text(encoding="utf-8"))
    gate = 'py -3.11 -c "raise SystemExit(0)"'
    commands["build"] = gate
    commands["test:quick"] = gate
    commands["test:full"] = gate
    commands["push"] = False
    commands_path.write_text(json.dumps(commands), encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "install loop")


def _write_result(root: Path, task: str, role: str, outcome: str) -> None:
    path = root / ".hive/implementation-loop/result.md"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    existing += f"\n- task: {task}\n  role: {role}\n  outcome: {outcome}\n  evidence: test\n"
    path.write_text(existing, encoding="utf-8")


def test_start_blocks_unrelated_dirty(loop_root: Path) -> None:
    _install_ready(loop_root)
    (loop_root / "notes.txt").write_text("dirt\n", encoding="utf-8")
    with pytest.raises(CoordinatorError, match="unrelated dirty") as exc:
        coordinator_start(loop_root, "feature-x")
    assert "notes.txt" in exc.value.fields.get("dirty", [])


def test_start_allow_dirty_and_handoff_cap(loop_root: Path) -> None:
    _install_ready(loop_root)
    (loop_root / "notes.txt").write_text("dirt\n", encoding="utf-8")
    started = coordinator_start(loop_root, "feature-x", allow_dirty=True)
    assert started.ok is True
    assert started.task == "T001"
    coordinator_handoff(loop_root, "coder")
    state_path = loop_root / ".hive/implementation-loop/state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["round_trips"] = 10
    state_path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(CoordinatorError, match="round_trips"):
        coordinator_handoff(loop_root, "coder")
    again = coordinator_handoff(loop_root, "coder", continue_after_cap=True)
    assert again.round_trips == 11


def test_commit_refuses_without_reviewer_pass(loop_root: Path) -> None:
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    coordinator_handoff(loop_root, "coder")
    _write_result(loop_root, "T001", "coder", "pass")
    coordinator_accept(loop_root, "coder")
    coordinator_handoff(loop_root, "checker")
    _write_result(loop_root, "T001", "checker", "pass")
    coordinator_accept(loop_root, "checker")
    with pytest.raises(CoordinatorError, match="reviewer"):
        coordinator_commit(loop_root)


def test_commit_skips_pytest_cache(loop_root: Path) -> None:
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    cache = loop_root / ".pytest_cache" / "v"
    cache.mkdir(parents=True)
    (cache / "cache").write_text("x\n", encoding="utf-8")
    (loop_root / "src").mkdir()
    (loop_root / "src" / "ok.py").write_text("x = 1\n", encoding="utf-8")
    coordinator_handoff(loop_root, "coder")
    _write_result(loop_root, "T001", "coder", "pass")
    coordinator_accept(loop_root, "coder")
    coordinator_handoff(loop_root, "checker")
    _write_result(loop_root, "T001", "checker", "pass")
    coordinator_accept(loop_root, "checker")
    coordinator_handoff(loop_root, "reviewer")
    _write_result(loop_root, "T001", "reviewer", "pass")
    coordinator_accept(loop_root, "reviewer")
    report = coordinator_commit(loop_root)
    assert report.ok is True
    show = _git(loop_root, "show", "--name-only", "--pretty=format:", "HEAD")
    names = {line.replace("\\", "/") for line in show.stdout.splitlines() if line.strip()}
    assert not any(".pytest_cache" in name for name in names)
    assert "src/ok.py" in names


def test_commit_skips_dirty_paths_from_start(loop_root: Path) -> None:
    _install_ready(loop_root)
    (loop_root / "notes.txt").write_text("leftover\n", encoding="utf-8")
    coordinator_start(loop_root, "feature-x", allow_dirty=True)
    (loop_root / "src").mkdir()
    (loop_root / "src" / "ok.py").write_text("x = 1\n", encoding="utf-8")
    coordinator_handoff(loop_root, "coder")
    _write_result(loop_root, "T001", "coder", "pass")
    coordinator_accept(loop_root, "coder")
    coordinator_handoff(loop_root, "checker")
    _write_result(loop_root, "T001", "checker", "pass")
    coordinator_accept(loop_root, "checker")
    coordinator_handoff(loop_root, "reviewer")
    _write_result(loop_root, "T001", "reviewer", "pass")
    coordinator_accept(loop_root, "reviewer")
    report = coordinator_commit(loop_root)
    assert report.ok is True
    show = _git(loop_root, "show", "--name-only", "--pretty=format:", "HEAD")
    names = {line.replace("\\", "/") for line in show.stdout.splitlines() if line.strip()}
    assert "notes.txt" not in names
    assert "src/ok.py" in names
    assert (loop_root / "notes.txt").is_file()


def test_commit_checks_off_task_and_leaves_hive_unstaged(loop_root: Path) -> None:
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    (loop_root / "src").mkdir()
    (loop_root / "src" / "ok.py").write_text("x = 1\n", encoding="utf-8")
    coordinator_handoff(loop_root, "coder")
    _write_result(loop_root, "T001", "coder", "pass")
    coordinator_accept(loop_root, "coder")
    coordinator_handoff(loop_root, "checker")
    _write_result(loop_root, "T001", "checker", "pass")
    coordinator_accept(loop_root, "checker")
    coordinator_handoff(loop_root, "reviewer")
    _write_result(loop_root, "T001", "reviewer", "pass")
    coordinator_accept(loop_root, "reviewer")
    report = coordinator_commit(loop_root)
    assert report.ok is True
    assert report.commit
    tasks = (loop_root / "docs/specs/feature-x/tasks.md").read_text(encoding="utf-8")
    assert "- [x] T001 do the thing" in tasks
    show = _git(loop_root, "show", "--name-only", "--pretty=format:", "HEAD")
    names = {line.replace("\\", "/") for line in show.stdout.splitlines() if line.strip()}
    assert not any(name.startswith(".hive/") for name in names)
    assert "docs/specs/feature-x/tasks.md" in names
    assert "src/ok.py" in names


def test_1pack_rejects_coder_handoff(loop_root: Path) -> None:
    _install_ready(loop_root, PACK_1)
    coordinator_start(loop_root, "feature-x")
    with pytest.raises(CoordinatorError, match="not valid for 1-pack"):
        coordinator_handoff(loop_root, "coder")
    handed = coordinator_handoff(loop_root, "coordinator")
    assert handed.ok is True


def test_task_id_is_not_a_prefix_of_a_longer_id() -> None:
    entries = parse_result_entries(
        "- task: T0010\n  role: reviewer\n  outcome: pass\n"
    )
    assert _last_outcome(entries, "T001", "reviewer") is None
    assert _last_outcome(entries, "T0010", "reviewer") == "pass"
    text = "# tasks\n\n- [ ] T0010 longer\n- [ ] T001 short\n"
    checked = _check_off_task(text, "T001", "T001 short")
    assert "- [x] T001 short" in checked
    assert "- [ ] T0010 longer" in checked


def test_cli_start_subcommand_is_wired(loop_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from hive_planner.cli import main

    code = main(
        ["--root", str(loop_root), "implementation-loop", "start", "--feature", "feature-x"]
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert "state.json" in payload["blocked_reason"] or payload.get("action") == "start"


def test_installed_text_calls_python_gates() -> None:
    command = render_cursor_command(PACK_4)
    coordinator = render_role_coordinator(PACK_4)
    assert "implementation-loop start --feature" in command
    assert "implementation-loop start --feature" in coordinator
    assert "implementation-loop commit" in coordinator
    assert "Do not `git commit`" in command or "Do not `git commit`" in coordinator

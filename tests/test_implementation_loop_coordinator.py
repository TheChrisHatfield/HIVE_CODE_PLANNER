"""Tests for Python implementation-loop coordinator gates."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hive_planner.implementation_loop import (
    GIT_IDENTITY,
    PACK_1,
    PACK_4,
    RETROSPECTIVE_HEADER,
    CoordinatorError,
    LoopState,
    _append_retrospective,
    _ensure_proposal_stub,
    _open_or_reuse_pull_request,
    _retrospective_due,
    _check_off_task,
    _last_outcome,
    _push_enabled,
    _run_named_command,
    coordinator_accept,
    coordinator_check,
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


def _write_result(root: Path, task: str, role: str, outcome: str, question: str = "") -> None:
    path = root / ".hive/implementation-loop/result.md"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    existing += f"\n- task: {task}\n  role: {role}\n  outcome: {outcome}\n  evidence: test\n"
    if question:
        existing += f"  question: {question}\n"
    path.write_text(existing, encoding="utf-8")


def _pass_roles_to_reviewer(root: Path, task: str = "T001") -> None:
    coordinator_handoff(root, "coder")
    _write_result(root, task, "coder", "pass")
    coordinator_accept(root, "coder")
    coordinator_handoff(root, "checker")
    _write_result(root, task, "checker", "pass")
    coordinator_accept(root, "checker")
    coordinator_handoff(root, "reviewer")


def test_handoff_and_accept_normalize_role_case(loop_root: Path) -> None:
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    handed = coordinator_handoff(loop_root, "Coder")
    assert handed.ok is True
    assert handed.role == "coder"
    _write_result(loop_root, "T001", "coder", "pass")
    accepted = coordinator_accept(loop_root, "CODER")
    assert accepted.ok is True
    assert accepted.role == "coder"


def test_start_rejects_invalid_feature_id(loop_root: Path) -> None:
    _install_ready(loop_root)
    with pytest.raises(CoordinatorError, match="invalid feature id"):
        coordinator_start(loop_root, "../secret")


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


def test_start_force_feature_resets_result_when_task_id_matches(loop_root: Path) -> None:
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    coordinator_handoff(loop_root, "coder")
    _write_result(loop_root, "T001", "coder", "pass")
    spec = loop_root / "docs" / "specs" / "feature-y"
    spec.mkdir(parents=True)
    (spec / "spec.md").write_text("# spec\n", encoding="utf-8")
    (spec / "plan.md").write_text("# plan\n", encoding="utf-8")
    (spec / "tasks.md").write_text("# tasks\n\n## Slice\n\n- [ ] T001 other work\n", encoding="utf-8")
    (loop_root / "docs" / "delta" / "20_micro" / "feature-y.md").write_text("# micro\n", encoding="utf-8")
    started = coordinator_start(loop_root, "feature-y", allow_dirty=True, force_feature=True)
    assert started.ok is True
    assert started.round_trips == 0
    result = (loop_root / ".hive/implementation-loop/result.md").read_text(encoding="utf-8")
    assert "outcome: pass" not in result
    assert "feature-y" in result or "T001" in result
    state = json.loads((loop_root / ".hive/implementation-loop/state.json").read_text(encoding="utf-8"))
    assert state["feature"] == "feature-y"
    assert state["round_trips"] == 0


def test_handoff_refuses_when_current_task_already_checked(loop_root: Path) -> None:
    tasks = loop_root / "docs/specs/feature-x/tasks.md"
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    tasks.write_text("# tasks\n\n## Slice\n\n- [x] T001 do the thing\n- [ ] T002 later\n", encoding="utf-8")
    with pytest.raises(CoordinatorError, match="not an open checkbox") as exc:
        coordinator_handoff(loop_root, "coder")
    assert exc.value.fields.get("task") == "T001"


def test_commit_refuses_when_current_task_already_checked(loop_root: Path) -> None:
    tasks = loop_root / "docs/specs/feature-x/tasks.md"
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
    tasks.write_text("# tasks\n\n## Slice\n\n- [x] T001 do the thing\n- [ ] T002 later\n", encoding="utf-8")
    with pytest.raises(CoordinatorError, match="not an open checkbox"):
        coordinator_commit(loop_root)
    assert "- [ ] T002 later" in tasks.read_text(encoding="utf-8")


def test_commit_checks_off_current_task_not_first_open(loop_root: Path) -> None:
    tasks = loop_root / "docs/specs/feature-x/tasks.md"
    tasks.write_text("# tasks\n\n## Slice\n\n- [ ] T001 do the thing\n- [ ] T002 later\n", encoding="utf-8")
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    tasks.write_text(
        "# tasks\n\n## Slice\n\n- [ ] T000 inserted first\n- [ ] T001 do the thing\n- [ ] T002 later\n",
        encoding="utf-8",
    )
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
    text = tasks.read_text(encoding="utf-8")
    assert "- [ ] T000 inserted first" in text
    assert "- [x] T001 do the thing" in text
    assert "- [ ] T002 later" in text


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


def test_4pack_accept_rejects_coordinator_role(loop_root: Path) -> None:
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    with pytest.raises(CoordinatorError, match="not valid for 4-pack"):
        coordinator_accept(loop_root, "coordinator")


def test_1pack_rejects_coder_handoff(loop_root: Path) -> None:
    _install_ready(loop_root, PACK_1)
    coordinator_start(loop_root, "feature-x")
    with pytest.raises(CoordinatorError, match="not valid for 1-pack"):
        coordinator_handoff(loop_root, "coder")
    handed = coordinator_handoff(loop_root, "coordinator")
    assert handed.ok is True


def test_1pack_commit_does_not_require_coder_result(loop_root: Path) -> None:
    _install_ready(loop_root, PACK_1)
    coordinator_start(loop_root, "feature-x")
    (loop_root / "src").mkdir()
    (loop_root / "src" / "ok.py").write_text("x = 1\n", encoding="utf-8")
    coordinator_handoff(loop_root, "coordinator")
    _write_result(loop_root, "T001", "checker", "pass")
    coordinator_accept(loop_root, "checker")
    _write_result(loop_root, "T001", "reviewer", "pass")
    coordinator_accept(loop_root, "reviewer")
    report = coordinator_commit(loop_root)
    assert report.ok is True
    assert "- [x] T001 do the thing" in (
        loop_root / "docs/specs/feature-x/tasks.md"
    ).read_text(encoding="utf-8")


def test_fifth_completed_feature_writes_proposal_stub(tmp_path: Path) -> None:
    loop = tmp_path / ".hive" / "implementation-loop"
    loop.mkdir(parents=True)
    lines = [RETROSPECTIVE_HEADER]
    for i in range(1, 5):
        lines.append(f"2026-01-0{i} | completed={i} | feat-{i}\n")
    (loop / "retrospective.log").write_text("".join(lines), encoding="utf-8")
    completed = _append_retrospective(tmp_path, "feat-5")
    assert completed == 5
    assert _retrospective_due(completed, 0) is True
    assert _retrospective_due(6, 0) is True
    assert _retrospective_due(10, 5) is True
    assert _retrospective_due(6, 5) is False
    assert _retrospective_due(5, 5) is False
    _ensure_proposal_stub(tmp_path)
    text = (tmp_path / "docs/proposals/implementation-loop-candidates.md").read_text(encoding="utf-8")
    assert "# operational" in text
    assert "# behavioral" in text


def test_open_or_reuse_pull_request(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_gh(_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, stdout="https://github.com/org/repo/pull/9\n", stderr="")

    monkeypatch.setattr("hive_planner.implementation_loop._gh", fake_gh)
    state = LoopState()
    url = _open_or_reuse_pull_request(tmp_path, state, "feature-x")
    assert url == "https://github.com/org/repo/pull/9"
    state.pr_url = url
    assert _open_or_reuse_pull_request(tmp_path, state, "feature-x") == url


def test_open_or_reuse_pull_request_reads_url_from_stderr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_gh(_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args, 0, stdout="Opening...\n", stderr="https://github.com/org/repo/pull/11\n"
        )

    monkeypatch.setattr("hive_planner.implementation_loop._gh", fake_gh)
    assert _open_or_reuse_pull_request(tmp_path, LoopState(), "feature-x") == (
        "https://github.com/org/repo/pull/11"
    )


def test_check_off_preserves_indent() -> None:
    text = "# tasks\n\n## Slice\n\n  - [ ] T001 do the thing\n"
    checked = _check_off_task(text, "T001", "T001 do the thing")
    assert "  - [x] T001 do the thing" in checked


def test_loop_state_round_trips_survives_bad_json_values() -> None:
    assert LoopState.from_dict({"round_trips": ""}).round_trips == 0
    assert LoopState.from_dict({"round_trips": None}).round_trips == 0
    assert LoopState.from_dict({"round_trips": "7"}).round_trips == 7
    assert LoopState.from_dict({"round_trips": "nope"}).round_trips == 0
    assert LoopState.from_dict({"round_trips": -3}).round_trips == 0


def test_push_enabled_accepts_json_and_string_true() -> None:
    assert _push_enabled({"push": True}) is True
    assert _push_enabled({"push": "true"}) is True
    assert _push_enabled({"push": "True"}) is True
    assert _push_enabled({"push": False}) is False
    assert _push_enabled({"push": "false"}) is False
    assert _push_enabled({}) is False


def test_result_entries_normalize_role_and_outcome() -> None:
    entries = parse_result_entries(
        "- task: T001\n  role: Reviewer\n  outcome: PASS\n"
    )
    assert _last_outcome(entries, "T001", "reviewer") == "pass"


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


def test_commit_refuses_trunk_branch(loop_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hive_planner.implementation_loop as mod

    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    coordinator_handoff(loop_root, "coder")
    _write_result(loop_root, "T001", "coder", "pass")
    coordinator_accept(loop_root, "coder")
    coordinator_handoff(loop_root, "checker")
    _write_result(loop_root, "T001", "checker", "pass")
    coordinator_accept(loop_root, "checker")
    coordinator_handoff(loop_root, "reviewer")
    _write_result(loop_root, "T001", "reviewer", "pass")
    coordinator_accept(loop_root, "reviewer")
    monkeypatch.setattr(mod, "_current_branch", lambda root: "main")
    monkeypatch.setattr(mod, "_resolve_trunk", lambda root: "main")
    with pytest.raises(CoordinatorError, match="trunk"):
        coordinator_commit(loop_root)


def test_handoff_describes_current_task_not_first_open(loop_root: Path) -> None:
    tasks = loop_root / "docs/specs/feature-x/tasks.md"
    tasks.write_text("# tasks\n\n## Slice\n\n- [ ] T001 do the thing\n- [ ] T002 later\n", encoding="utf-8")
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    tasks.write_text(
        "# tasks\n\n## Slice\n\n- [ ] T000 inserted first\n- [ ] T001 do the thing\n- [ ] T002 later\n",
        encoding="utf-8",
    )
    coordinator_handoff(loop_root, "coder")
    text = (loop_root / ".hive/implementation-loop/handoff.md").read_text(encoding="utf-8")
    assert "task: T001" in text
    assert "T001 do the thing" in text
    assert "T000" not in text


def test_reviewer_fail_returns_to_coder(loop_root: Path) -> None:
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    _pass_roles_to_reviewer(loop_root)
    _write_result(loop_root, "T001", "reviewer", "fail")
    accepted = coordinator_accept(loop_root, "reviewer")
    assert accepted.next_role == "coder"
    with pytest.raises(CoordinatorError, match="returns to coder"):
        coordinator_handoff(loop_root, "reviewer")
    with pytest.raises(CoordinatorError, match="returns to coder"):
        coordinator_handoff(loop_root, "checker")
    again = coordinator_handoff(loop_root, "coder")
    assert again.ok is True
    _write_result(loop_root, "T001", "coder", "pass")
    coordinator_accept(loop_root, "coder")
    with pytest.raises(CoordinatorError, match="checker pass after the last coder"):
        coordinator_handoff(loop_root, "reviewer")
    checker = coordinator_handoff(loop_root, "checker")
    assert checker.ok is True
    _write_result(loop_root, "T001", "checker", "pass")
    coordinator_accept(loop_root, "checker")
    reviewer = coordinator_handoff(loop_root, "reviewer")
    assert reviewer.ok is True


def test_commit_refuses_reviewer_pass_before_new_checker(loop_root: Path) -> None:
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    (loop_root / "src").mkdir()
    (loop_root / "src" / "ok.py").write_text("x = 1\n", encoding="utf-8")
    _pass_roles_to_reviewer(loop_root)
    _write_result(loop_root, "T001", "reviewer", "fail")
    coordinator_accept(loop_root, "reviewer")
    coordinator_handoff(loop_root, "coder")
    _write_result(loop_root, "T001", "coder", "pass")
    coordinator_accept(loop_root, "coder")
    _write_result(loop_root, "T001", "reviewer", "pass")
    coordinator_accept(loop_root, "reviewer")
    with pytest.raises(CoordinatorError, match="checker pass after the last coder"):
        coordinator_commit(loop_root)


def test_checker_fail_returns_to_coder(loop_root: Path) -> None:
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    coordinator_handoff(loop_root, "coder")
    _write_result(loop_root, "T001", "coder", "pass")
    coordinator_accept(loop_root, "coder")
    coordinator_handoff(loop_root, "checker")
    _write_result(loop_root, "T001", "checker", "fail")
    accepted = coordinator_accept(loop_root, "checker")
    assert accepted.next_role == "coder"
    with pytest.raises(CoordinatorError, match="checker fail returns to coder"):
        coordinator_handoff(loop_root, "checker")
    with pytest.raises(CoordinatorError, match="checker fail returns to coder"):
        coordinator_handoff(loop_root, "reviewer")
    again = coordinator_handoff(loop_root, "coder")
    assert again.ok is True
    _write_result(loop_root, "T001", "coder", "pass")
    coordinator_accept(loop_root, "coder")
    checker = coordinator_handoff(loop_root, "checker")
    assert checker.ok is True


def test_reviewer_fail_with_question_rehands_reviewer(loop_root: Path) -> None:
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    _pass_roles_to_reviewer(loop_root)
    _write_result(loop_root, "T001", "reviewer", "fail", question="Need a spec decision")
    accepted = coordinator_accept(loop_root, "reviewer")
    assert accepted.next_role == "reviewer"
    handed = coordinator_handoff(loop_root, "reviewer")
    assert handed.ok is True


def test_handoff_requires_loop_branch(loop_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hive_planner.implementation_loop as mod

    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    monkeypatch.setattr(mod, "_current_branch", lambda _root: "other-branch")
    with pytest.raises(CoordinatorError, match="loop branch"):
        coordinator_handoff(loop_root, "coder")


def test_commit_restores_tasks_when_git_commit_fails(loop_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hive_planner.implementation_loop as mod

    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    (loop_root / "src").mkdir()
    (loop_root / "src" / "ok.py").write_text("x = 1\n", encoding="utf-8")
    _pass_roles_to_reviewer(loop_root)
    _write_result(loop_root, "T001", "reviewer", "pass")
    coordinator_accept(loop_root, "reviewer")
    real_git = mod._git

    def fake_git(root: Path, *args: str, extra_env: dict[str, str] | None = None):
        if args and args[0] == "commit":
            return subprocess.CompletedProcess(["git", *args], 1, stdout="", stderr="boom")
        return real_git(root, *args, extra_env=extra_env)

    monkeypatch.setattr(mod, "_git", fake_git)
    with pytest.raises(CoordinatorError, match="boom"):
        coordinator_commit(loop_root)
    tasks = (loop_root / "docs/specs/feature-x/tasks.md").read_text(encoding="utf-8")
    assert "- [ ] T001 do the thing" in tasks


def test_test_full_failure_does_not_advance_task(
    loop_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hive_planner.implementation_loop as mod

    tasks = loop_root / "docs/specs/feature-x/tasks.md"
    tasks.write_text(
        "# tasks\n\n## Slice A\n\n- [ ] T001 do the thing\n\n## Slice B\n\n- [ ] T002 later\n",
        encoding="utf-8",
    )
    _install_ready(loop_root)

    def fail_full(_root: Path, key: str) -> subprocess.CompletedProcess[str]:
        if key == "test:full":
            return subprocess.CompletedProcess(["test:full"], 1, stdout="", stderr="test:full failed")
        return subprocess.CompletedProcess([key], 0, stdout="", stderr="")

    monkeypatch.setattr(mod, "_run_named_command", fail_full)
    coordinator_start(loop_root, "feature-x")
    (loop_root / "src").mkdir()
    (loop_root / "src" / "ok.py").write_text("x = 1\n", encoding="utf-8")
    _pass_roles_to_reviewer(loop_root)
    _write_result(loop_root, "T001", "reviewer", "pass")
    coordinator_accept(loop_root, "reviewer")
    report = coordinator_commit(loop_root)
    assert report.ok is False
    assert "test:full" in report.blocked_reason
    state = json.loads((loop_root / ".hive/implementation-loop/state.json").read_text(encoding="utf-8"))
    assert state["status"] == "blocked"
    assert state["current_task"] == "T001"
    text = tasks.read_text(encoding="utf-8")
    assert "- [x] T001 do the thing" in text
    assert "- [ ] T002 later" in text
    log = (loop_root / ".hive/implementation-loop/retrospective.log").read_text(encoding="utf-8")
    assert "feature-x" not in log
    with pytest.raises(CoordinatorError, match="loop is blocked"):
        coordinator_start(loop_root, "feature-x")
    resumed = coordinator_start(loop_root, "feature-x", force_feature=True)
    assert resumed.ok is True
    assert resumed.task == "T002"


def test_commit_refuses_detached_head(loop_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hive_planner.implementation_loop as mod

    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    (loop_root / "src").mkdir()
    (loop_root / "src" / "ok.py").write_text("x = 1\n", encoding="utf-8")
    _pass_roles_to_reviewer(loop_root)
    _write_result(loop_root, "T001", "reviewer", "pass")
    coordinator_accept(loop_root, "reviewer")
    monkeypatch.setattr(mod, "_current_branch", lambda _root: "HEAD")
    with pytest.raises(CoordinatorError, match="no current git branch"):
        coordinator_commit(loop_root)


def test_checker_needs_sign_off_blocks_coder(loop_root: Path) -> None:
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    coordinator_handoff(loop_root, "coder")
    _write_result(loop_root, "T001", "coder", "pass")
    coordinator_accept(loop_root, "coder")
    coordinator_handoff(loop_root, "checker")
    _write_result(loop_root, "T001", "checker", "needs-sign-off")
    coordinator_accept(loop_root, "checker")
    with pytest.raises(CoordinatorError, match="needs-sign-off"):
        coordinator_handoff(loop_root, "coder")


def test_missing_test_full_binary_blocks_without_crash(loop_root: Path) -> None:
    tasks = loop_root / "docs/specs/feature-x/tasks.md"
    tasks.write_text(
        "# tasks\n\n## Slice A\n\n- [ ] T001 do the thing\n\n## Slice B\n\n- [ ] T002 later\n",
        encoding="utf-8",
    )
    _install_ready(loop_root)
    commands_path = loop_root / ".hive/implementation-loop/commands.json"
    commands = json.loads(commands_path.read_text(encoding="utf-8"))
    commands["test:full"] = "hive-missing-test-full-binary"
    commands_path.write_text(json.dumps(commands), encoding="utf-8")
    coordinator_start(loop_root, "feature-x")
    (loop_root / "src").mkdir()
    (loop_root / "src" / "ok.py").write_text("x = 1\n", encoding="utf-8")
    _pass_roles_to_reviewer(loop_root)
    _write_result(loop_root, "T001", "reviewer", "pass")
    coordinator_accept(loop_root, "reviewer")
    report = coordinator_commit(loop_root)
    assert report.ok is False
    assert "not found" in report.blocked_reason
    state = json.loads((loop_root / ".hive/implementation-loop/state.json").read_text(encoding="utf-8"))
    assert state["status"] == "blocked"
    assert state["current_task"] == "T001"


def test_run_named_command_preserves_windows_exe_path(loop_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if sys.platform != "win32":
        pytest.skip("Windows command splitting")
    import hive_planner.implementation_loop as mod

    _install_ready(loop_root)
    captured: dict[str, object] = {}

    def fake_run(args, **_kwargs):  # type: ignore[no-untyped-def]
        captured["args"] = list(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    commands_path = loop_root / ".hive/implementation-loop/commands.json"
    commands = json.loads(commands_path.read_text(encoding="utf-8"))
    commands["test:full"] = r"C:\Python311\python.exe -m pytest"
    commands_path.write_text(json.dumps(commands), encoding="utf-8")
    proc = _run_named_command(loop_root, "test:full")
    assert proc.returncode == 0
    assert captured["args"] == [r"C:\Python311\python.exe", "-m", "pytest"]


def test_run_named_command_unbalanced_quotes_do_not_raise(loop_root: Path) -> None:
    _install_ready(loop_root)
    commands_path = loop_root / ".hive/implementation-loop/commands.json"
    commands = json.loads(commands_path.read_text(encoding="utf-8"))
    commands["test:full"] = 'echo "unterminated'
    commands_path.write_text(json.dumps(commands), encoding="utf-8")
    proc = _run_named_command(loop_root, "test:full")
    assert proc.returncode == 127
    assert proc.stderr


def test_missing_gh_leaves_pr_url_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hive_planner.implementation_loop as mod

    def fake_run(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError("gh")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    state = LoopState(feature="feature-x")
    assert _open_or_reuse_pull_request(tmp_path, state, "feature-x") == ""


def test_needs_sign_off_blocks_commit_and_coder(loop_root: Path) -> None:
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    coordinator_handoff(loop_root, "coder")
    _write_result(loop_root, "T001", "coder", "pass")
    coordinator_accept(loop_root, "coder")
    coordinator_handoff(loop_root, "checker")
    _write_result(loop_root, "T001", "checker", "pass")
    coordinator_accept(loop_root, "checker")
    coordinator_handoff(loop_root, "reviewer")
    _write_result(loop_root, "T001", "reviewer", "needs-sign-off")
    accepted = coordinator_accept(loop_root, "reviewer")
    assert accepted.blocked_reason == "needs-sign-off"
    with pytest.raises(CoordinatorError, match="needs-sign-off"):
        coordinator_commit(loop_root)
    with pytest.raises(CoordinatorError, match="needs-sign-off"):
        coordinator_handoff(loop_root, "coder")


def test_check_requires_coder_pass(loop_root: Path) -> None:
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    with pytest.raises(CoordinatorError, match="last coder"):
        coordinator_check(loop_root)


def test_check_appends_pass_without_incrementing_round_trips(loop_root: Path) -> None:
    _install_ready(loop_root)
    coordinator_start(loop_root, "feature-x")
    coordinator_handoff(loop_root, "coder")
    _write_result(loop_root, "T001", "coder", "pass")
    coordinator_accept(loop_root, "coder")
    before = json.loads((loop_root / ".hive/implementation-loop/state.json").read_text(encoding="utf-8"))
    report = coordinator_check(loop_root)
    assert report.ok is True
    assert report.role == "checker"
    assert report.blocked_reason == ""
    assert report.round_trips == before["round_trips"]
    text = (loop_root / ".hive/implementation-loop/result.md").read_text(encoding="utf-8")
    assert "role: checker" in text
    assert "outcome: pass" in text
    accepted = coordinator_accept(loop_root, "checker")
    assert accepted.ok is True


def test_check_appends_fail_when_build_exits_nonzero(loop_root: Path) -> None:
    _install_ready(loop_root)
    commands_path = loop_root / ".hive/implementation-loop/commands.json"
    commands = json.loads(commands_path.read_text(encoding="utf-8"))
    commands["build"] = "hive-missing-check-build"
    commands_path.write_text(json.dumps(commands), encoding="utf-8")
    coordinator_start(loop_root, "feature-x")
    coordinator_handoff(loop_root, "coder")
    _write_result(loop_root, "T001", "coder", "pass")
    coordinator_accept(loop_root, "coder")
    report = coordinator_check(loop_root)
    assert report.ok is False
    assert report.blocked_reason == "fail"
    assert report.next_role == "coder"
    entries = parse_result_entries(
        (loop_root / ".hive/implementation-loop/result.md").read_text(encoding="utf-8")
    )
    assert _last_outcome(entries, "T001", "checker") == "fail"


def test_cli_check_exits_2_when_checker_fails(loop_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from hive_planner.cli import main

    _install_ready(loop_root)
    commands_path = loop_root / ".hive/implementation-loop/commands.json"
    commands = json.loads(commands_path.read_text(encoding="utf-8"))
    commands["build"] = "hive-missing-check-build"
    commands_path.write_text(json.dumps(commands), encoding="utf-8")
    coordinator_start(loop_root, "feature-x")
    coordinator_handoff(loop_root, "coder")
    _write_result(loop_root, "T001", "coder", "pass")
    coordinator_accept(loop_root, "coder")
    code = main(["--root", str(loop_root), "implementation-loop", "check"])
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["blocked_reason"] == "fail"


def test_check_1pack_runs_without_coder_result(loop_root: Path) -> None:
    _install_ready(loop_root, PACK_1)
    coordinator_start(loop_root, "feature-x")
    coordinator_handoff(loop_root, "coordinator")
    report = coordinator_check(loop_root)
    assert report.ok is True
    assert report.role == "checker"


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
    assert "implementation-loop check" in command
    assert "implementation-loop check" in coordinator
    assert "implementation-loop commit" in coordinator
    assert "Do not `git commit`" in command or "Do not `git commit`" in coordinator
    assert "bug hunt" in command.lower()
    assert "then checker, then reviewer" in coordinator

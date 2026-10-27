"""Tests for the implementation-loop installer and readiness gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.implementation_loop import (
    PACK_1,
    PACK_4,
    _normalize_git_branch,
    assess_implementation_readiness,
    install_implementation_loop,
    is_implementation_loop_request,
    preview_agent_prompt,
    render_cursor_rule,
)


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
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
        "# tasks\n\n- [ ] T001 do the thing\n", encoding="utf-8"
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "proj"\n\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
        encoding="utf-8",
    )
    return root


def test_normalize_git_branch_strips_origin_prefix() -> None:
    assert _normalize_git_branch("origin/main") == "main"
    assert _normalize_git_branch("origin/master") == "master"
    assert _normalize_git_branch("main") == "main"


def test_trigger_phrases() -> None:
    assert is_implementation_loop_request("implementation loop")
    assert is_implementation_loop_request("implement the spec")
    assert is_implementation_loop_request("run the implementation loop")
    assert is_implementation_loop_request("start the implementation loop")
    assert is_implementation_loop_request("/implementation-loop")
    assert not is_implementation_loop_request("what is the implementation loop")
    assert not is_implementation_loop_request("tell me what the implementation loop is")
    assert not is_implementation_loop_request("how do I install it")
    assert not is_implementation_loop_request("bug hunt")
    assert not is_implementation_loop_request("hunt for bugs")
    assert is_implementation_loop_request("please run the implementation loop")


def test_render_cursor_rule_mentions_command_and_questions() -> None:
    text = render_cursor_rule()
    assert ".cursor/commands/implementation-loop.md" in text
    assert "question" in text.lower()
    assert "bug-hunt" in text.lower()
    assert "several features" in text.lower()
    assert "exactly one feature" in text.lower()
    assert "none are ready" in text.lower()


def test_install_4pack_writes_all_files(project_root: Path) -> None:
    written = install_implementation_loop(project_root, PACK_4)
    rels = set(written)
    expected = {
        ".cursor/commands/implementation-loop.md",
        ".cursor/rules/implementation-loop.mdc",
        ".hive/implementation-loop/roles/coordinator.md",
        ".hive/implementation-loop/roles/coder.md",
        ".hive/implementation-loop/roles/checker.md",
        ".hive/implementation-loop/roles/reviewer.md",
        ".hive/implementation-loop/NOTICE",
        ".hive/implementation-loop/commands.json",
        ".hive/implementation-loop/state.json",
        ".hive/implementation-loop/retrospective.log",
        ".hive/implementation-loop/retrospective.md",
    }
    for rel in expected:
        assert rel in rels, f"missing {rel}"

    state = json.loads((project_root / ".hive/implementation-loop/state.json").read_text(encoding="utf-8"))
    assert state["pack"] == PACK_4
    assert state["status"] == "idle"
    assert state["round_trips"] == 0

    commands = json.loads((project_root / ".hive/implementation-loop/commands.json").read_text(encoding="utf-8"))
    assert commands["test:quick"] == "py -3.11 -m pytest"
    # This fixture is not a Hive project, so ci-check is not discovered.
    assert commands["test:full"] == ""


def test_install_overwrites_non_utf8_command_file(project_root: Path) -> None:
    target = project_root / ".cursor" / "commands" / "implementation-loop.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"\xff\xfe not utf-8")
    written = install_implementation_loop(project_root, PACK_4)
    assert ".cursor/commands/implementation-loop.md" in written
    text = target.read_text(encoding="utf-8")
    assert "implementation-loop" in text


def test_install_1pack_removes_delegated_roles(project_root: Path) -> None:
    install_implementation_loop(project_root, PACK_4)
    install_implementation_loop(project_root, PACK_1, force_pack=True)
    role_dir = project_root / ".hive/implementation-loop/roles"
    assert (role_dir / "coordinator.md").is_file()
    assert not (role_dir / "coder.md").exists()
    assert not (role_dir / "checker.md").exists()
    assert not (role_dir / "reviewer.md").exists()
    state = json.loads((project_root / ".hive/implementation-loop/state.json").read_text(encoding="utf-8"))
    assert state["pack"] == PACK_1


def test_reinstall_preserves_commands_and_state(project_root: Path) -> None:
    install_implementation_loop(project_root, PACK_4)
    commands_path = project_root / ".hive/implementation-loop/commands.json"
    commands = json.loads(commands_path.read_text(encoding="utf-8"))
    commands["build"] = "echo build"
    commands_path.write_text(json.dumps(commands), encoding="utf-8")
    state_path = project_root / ".hive/implementation-loop/state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["round_trips"] = 7
    state_path.write_text(json.dumps(state), encoding="utf-8")
    install_implementation_loop(project_root, PACK_4)
    assert json.loads(commands_path.read_text(encoding="utf-8"))["build"] == "echo build"
    assert json.loads(state_path.read_text(encoding="utf-8"))["round_trips"] == 7


def test_install_rejects_corrupt_state_json(project_root: Path) -> None:
    install_implementation_loop(project_root, PACK_4)
    (project_root / ".hive/implementation-loop/state.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="state.json is not valid JSON"):
        install_implementation_loop(project_root, PACK_4)
    assert (project_root / ".hive/implementation-loop/state.json").read_text(encoding="utf-8") == "{not json"


def test_force_pack_required_for_pack_change(project_root: Path) -> None:
    install_implementation_loop(project_root, PACK_4)
    with pytest.raises(ValueError, match="force-pack"):
        install_implementation_loop(project_root, PACK_1)


def test_readiness_ready(project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hive_planner.implementation_loop as mod

    monkeypatch.setattr(mod, "_current_branch", lambda root: "feature-x")
    monkeypatch.setattr(mod, "_resolve_trunk", lambda root: "main")
    install_implementation_loop(project_root, PACK_4)
    commands_path = project_root / ".hive/implementation-loop/commands.json"
    commands = json.loads(commands_path.read_text(encoding="utf-8"))
    commands["build"] = "echo build"
    commands["test:full"] = "echo test-full"
    commands_path.write_text(json.dumps(commands), encoding="utf-8")
    report = assess_implementation_readiness(project_root, "feature-x")
    assert report.ready is True
    assert report.missing == []
    assert report.round_trips == 0
    assert report.pack == PACK_4
    assert "round_trips" in report.to_dict()


def test_readiness_missing_tasks(project_root: Path) -> None:
    (project_root / "docs" / "specs" / "feature-x" / "tasks.md").write_text("# tasks\n\n- [x] done\n", encoding="utf-8")
    install_implementation_loop(project_root, PACK_4)
    report = assess_implementation_readiness(project_root, "feature-x")
    assert report.ready is False
    assert any("no open task" in m for m in report.missing)


def test_readiness_missing_commands(project_root: Path) -> None:
    install_implementation_loop(project_root, PACK_4)
    commands_path = project_root / ".hive/implementation-loop/commands.json"
    commands = json.loads(commands_path.read_text(encoding="utf-8"))
    commands["build"] = ""
    commands_path.write_text(json.dumps(commands), encoding="utf-8")
    report = assess_implementation_readiness(project_root, "feature-x")
    assert report.ready is False
    assert any("build" in m for m in report.missing)


def test_readiness_missing_spec(project_root: Path) -> None:
    (project_root / "docs" / "specs" / "feature-x" / "spec.md").unlink()
    install_implementation_loop(project_root, PACK_4)
    report = assess_implementation_readiness(project_root, "feature-x")
    assert report.ready is False
    assert any("spec.md" in m for m in report.missing)


def test_readiness_trunk_branch(project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_implementation_loop(project_root, PACK_4)
    import hive_planner.implementation_loop as mod

    monkeypatch.setattr(mod, "_current_branch", lambda root: "main")
    monkeypatch.setattr(mod, "_resolve_trunk", lambda root: "main")
    report = assess_implementation_readiness(project_root, "feature-x")
    assert report.ready is False
    assert any("trunk" in m for m in report.missing)


def test_preview_agent_prompt_1pack() -> None:
    text = preview_agent_prompt(PACK_1)
    assert "1-pack" in text
    assert "do not delegate" in text.lower()


def test_preview_agent_prompt_4pack() -> None:
    text = preview_agent_prompt(PACK_4)
    assert "4-pack" in text
    assert "delegate" in text.lower()


def test_invalid_pack() -> None:
    with pytest.raises(ValueError):
        install_implementation_loop(Path("dummy"), "5-pack")


def test_installed_text_forbids_merge_deploy_and_agents_md(project_root: Path) -> None:
    install_implementation_loop(project_root, PACK_4)
    command = (project_root / ".cursor/commands/implementation-loop.md").read_text(encoding="utf-8")
    coordinator = (project_root / ".hive/implementation-loop/roles/coordinator.md").read_text(encoding="utf-8")
    coder = (project_root / ".hive/implementation-loop/roles/coder.md").read_text(encoding="utf-8")
    checker = (project_root / ".hive/implementation-loop/roles/checker.md").read_text(encoding="utf-8")
    reviewer = (project_root / ".hive/implementation-loop/roles/reviewer.md").read_text(encoding="utf-8")
    retro = (project_root / ".hive/implementation-loop/retrospective.md").read_text(encoding="utf-8")
    assert "do not merge" in command.lower()
    assert "do not merge" in coordinator.lower()
    assert "deploy" in command.lower()
    assert "deploy" in coder.lower()
    assert "Do not commit" in coder
    assert "Do not commit" in checker
    assert "implementation-loop check" in checker
    assert "Do not commit" in reviewer
    assert "force-push" in command.lower() or "force-push" in coordinator
    assert "Do not edit `AGENTS.md`" in coordinator
    assert "Do not edit `AGENTS.md`" in coder
    assert "Do not edit `AGENTS.md` directly" in retro
    assert "Unrelated dirty paths" in coordinator
    assert "6–10 word slug" in coordinator
    assert "test:full" in coordinator
    assert "Each `##` section that contains a checkbox" in coordinator
    assert "grown by 5" in coordinator
    assert "bug hunt" in command.lower()


def test_reinstall_fills_empty_commands_and_refreshes_retrospective(project_root: Path) -> None:
    install_implementation_loop(project_root, PACK_4)
    commands_path = project_root / ".hive/implementation-loop/commands.json"
    commands = json.loads(commands_path.read_text(encoding="utf-8"))
    commands["test:quick"] = ""
    commands["build"] = "keep-me"
    commands_path.write_text(json.dumps(commands), encoding="utf-8")
    retro_path = project_root / ".hive/implementation-loop/retrospective.md"
    retro_path.write_text("stale retro\n", encoding="utf-8")
    install_implementation_loop(project_root, PACK_4)
    refreshed = json.loads(commands_path.read_text(encoding="utf-8"))
    assert refreshed["build"] == "keep-me"
    assert refreshed["test:quick"] == "py -3.11 -m pytest"
    assert "stale retro" not in retro_path.read_text(encoding="utf-8")
    assert "agents-propose" in retro_path.read_text(encoding="utf-8")


def test_readiness_complete_without_state_flag(project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hive_planner.implementation_loop as mod

    monkeypatch.setattr(mod, "_current_branch", lambda root: "main")
    monkeypatch.setattr(mod, "_resolve_trunk", lambda root: "main")
    install_implementation_loop(project_root, PACK_4)
    commands_path = project_root / ".hive/implementation-loop/commands.json"
    commands = json.loads(commands_path.read_text(encoding="utf-8"))
    commands["build"] = "echo build"
    commands["test:full"] = "echo test-full"
    commands_path.write_text(json.dumps(commands), encoding="utf-8")
    (project_root / "docs/specs/feature-x/tasks.md").write_text("# tasks\n\n- [x] T001 done\n", encoding="utf-8")
    report = assess_implementation_readiness(project_root, "feature-x")
    assert report.ready is True
    assert report.blocked_reason == "complete"
    assert report.missing == []


def test_readiness_complete_is_exit_ready(project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hive_planner.implementation_loop as mod

    monkeypatch.setattr(mod, "_current_branch", lambda root: "feature-x")
    monkeypatch.setattr(mod, "_resolve_trunk", lambda root: "main")
    install_implementation_loop(project_root, PACK_4)
    commands_path = project_root / ".hive/implementation-loop/commands.json"
    commands = json.loads(commands_path.read_text(encoding="utf-8"))
    commands["build"] = "echo build"
    commands["test:full"] = "echo test-full"
    commands_path.write_text(json.dumps(commands), encoding="utf-8")
    (project_root / "docs/specs/feature-x/tasks.md").write_text("# tasks\n\n- [x] T001 done\n", encoding="utf-8")
    state_path = project_root / ".hive/implementation-loop/state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["feature"] = "feature-x"
    state["status"] = "complete"
    state["round_trips"] = 3
    state["current_task"] = "T001"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    report = assess_implementation_readiness(project_root, "feature-x")
    assert report.ready is True
    assert report.blocked_reason == "complete"
    assert report.round_trips == 3
    payload = report.to_dict()
    assert payload["round_trips"] == 3
    assert payload["state_status"] == "complete"
    assert payload["current_task"] == "T001"
    assert payload["pack"] == PACK_4


def test_init_without_pack_skips_loop(tmp_path: Path) -> None:
    from hive_planner.bootstrap import init_project
    from hive_planner.config import RepoPaths

    source_root = tmp_path / "hive-planner"
    kit = source_root / "starter-kit"
    rules = source_root / ".cursor" / "rules"
    rules.mkdir(parents=True)
    kit.mkdir(parents=True)
    (rules / "architecture.mdc").write_text("# Architecture\n", encoding="utf-8")
    (rules / "task-execution.mdc").write_text("# Task Execution\n", encoding="utf-8")
    (rules / "validation.mdc").write_text("# Validation\n", encoding="utf-8")
    (kit / "spec-kit-agent-integration.md").write_text("# Spec Kit\n", encoding="utf-8")
    target = tmp_path / "new-project"
    init_project(RepoPaths(root=source_root), target)
    assert not (target / ".cursor" / "commands" / "implementation-loop.md").exists()
    assert not (target / ".hive" / "implementation-loop").exists()


def test_discover_does_not_overwrite_pytest_with_makefile(project_root: Path) -> None:
    (project_root / "Makefile").write_text("test:\n\tpytest\n", encoding="utf-8")
    install_implementation_loop(project_root, PACK_4)
    commands = json.loads(
        (project_root / ".hive/implementation-loop/commands.json").read_text(encoding="utf-8")
    )
    assert commands["test:quick"] == "py -3.11 -m pytest"


def test_discover_build_from_justfile(project_root: Path) -> None:
    (project_root / "Justfile").write_text("build:\n\techo ok\n", encoding="utf-8")
    install_implementation_loop(project_root, PACK_4)
    commands = json.loads(
        (project_root / ".hive/implementation-loop/commands.json").read_text(encoding="utf-8")
    )
    assert commands["build"] == "just build"


def test_discover_build_from_taskfile(project_root: Path) -> None:
    (project_root / "Taskfile.yml").write_text("tasks:\n    build:\n      cmds: [echo ok]\n", encoding="utf-8")
    install_implementation_loop(project_root, PACK_4)
    commands = json.loads(
        (project_root / ".hive/implementation-loop/commands.json").read_text(encoding="utf-8")
    )
    assert commands["build"] == "task build"


def test_discover_test_full_from_yaml_workflow(project_root: Path) -> None:
    wf = project_root / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yaml").write_text("run: hive_planner ci-check\n", encoding="utf-8")
    install_implementation_loop(project_root, PACK_4)
    commands = json.loads(
        (project_root / ".hive/implementation-loop/commands.json").read_text(encoding="utf-8")
    )
    assert commands["test:full"] == "py -3.11 -m hive_planner ci-check"


def test_discover_build_from_src_and_setuptools(project_root: Path) -> None:
    (project_root / "src").mkdir()
    (project_root / "src" / "pkg").mkdir()
    (project_root / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    pyproject = project_root / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8") + '\n[build-system]\nrequires = ["setuptools>=61"]\n',
        encoding="utf-8",
    )
    install_implementation_loop(project_root, PACK_4)
    commands = json.loads(
        (project_root / ".hive/implementation-loop/commands.json").read_text(encoding="utf-8")
    )
    assert commands["build"] == "py -3.11 -m compileall -q src"


def test_init_pack_failure_is_bootstrap_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.bootstrap import BootstrapError, init_project
    from hive_planner.config import RepoPaths

    source_root = tmp_path / "hive-planner"
    kit = source_root / "starter-kit"
    rules = source_root / ".cursor" / "rules"
    rules.mkdir(parents=True)
    kit.mkdir(parents=True)
    (rules / "architecture.mdc").write_text("# Architecture\n", encoding="utf-8")
    (rules / "task-execution.mdc").write_text("# Task Execution\n", encoding="utf-8")
    (rules / "validation.mdc").write_text("# Validation\n", encoding="utf-8")
    (kit / "spec-kit-agent-integration.md").write_text("# Spec Kit\n", encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise ValueError("disk full")

    monkeypatch.setattr("hive_planner.implementation_loop.install_implementation_loop", boom)
    with pytest.raises(BootstrapError, match="Implementation-loop install failed"):
        init_project(RepoPaths(root=source_root), tmp_path / "new-project", implementation_loop_pack=PACK_4)


def test_init_with_pack_installs_loop(tmp_path: Path) -> None:
    from hive_planner.bootstrap import init_project
    from hive_planner.config import RepoPaths

    source_root = tmp_path / "hive-planner"
    kit = source_root / "starter-kit"
    rules = source_root / ".cursor" / "rules"
    rules.mkdir(parents=True)
    kit.mkdir(parents=True)
    (rules / "architecture.mdc").write_text("# Architecture\n", encoding="utf-8")
    (rules / "task-execution.mdc").write_text("# Task Execution\n", encoding="utf-8")
    (rules / "validation.mdc").write_text("# Validation\n", encoding="utf-8")
    (kit / "spec-kit-agent-integration.md").write_text("# Spec Kit\n", encoding="utf-8")
    target = tmp_path / "new-project"
    init_project(RepoPaths(root=source_root), target, implementation_loop_pack=PACK_1)
    assert (target / ".cursor" / "commands" / "implementation-loop.md").is_file()
    assert (target / ".hive" / "implementation-loop" / "roles" / "coordinator.md").is_file()
    assert not (target / ".hive" / "implementation-loop" / "roles" / "coder.md").exists()

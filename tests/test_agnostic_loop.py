"""Tests for the hive-loop-kit chooser (catalog is replaceable)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.agnostic_loop import (
    arm,
    begin,
    choose,
    default_catalog_dict,
    install_agnostic_loop,
    is_agnostic_loop_request,
    missing_agnostic_loop_artifacts,
    observe,
    parse_open,
    render_kit_entry,
    review,
    reward_tables,
    rewards,
    status,
)


SEAMFLOW_IDS = (
    "host.contract",
    "fill.residual",
    "infer.flow_path",
    "train.loop",
    "outcome.muon",
)

SOURCE_KIT_IDS = (
    "boundary",
    "fill-unknown",
    "train-script",
    "methodology",
    "outcome-infer",
    "outcome-growth",
    "infer-gap",
)

HIVE_WORK_IDS = (
    "spec-gap",
    "plan-gap",
    "task-open",
    "implement",
    "check",
    "review",
    "bug-hunt",
    "wiring",
)

SOURCE_PHRASES = (
    "reconstruction",
    "launch a run",
    "Mine only",
    "cascading methodology",
    "cited source",
)


def test_catalog_is_generic_not_source_repo_or_hive_work() -> None:
    names = rewards()
    assert "inspect" in names
    assert "fill" in names
    assert "script" in names
    blob = json.dumps(default_catalog_dict())
    for item in SEAMFLOW_IDS + SOURCE_KIT_IDS:
        assert item not in names
        assert item not in blob
    for item in HIVE_WORK_IDS:
        assert item not in names
    lowered = blob.lower()
    for phrase in SOURCE_PHRASES:
        assert phrase.lower() not in lowered


def test_arm_begin_review_cycle(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    payload, code = arm(root, "inspect", 2)
    assert code == 0
    assert payload["ok"] is True
    assert payload["hook"] == reward_tables()["inspect"][0][0]
    started, code = begin(root)
    assert code == 0
    assert started["action"] == "begin"
    again, code = begin(root)
    assert code == 3
    paused, code = review(root, "one tick")
    assert code == 0
    assert paused["action"] == "pause"
    assert (root / ".hive/agnostic-loop/reviews/cycle-001.md").is_file()
    report = status(root)
    assert report["status"] == "paused"
    assert report["completed"] == 1


def test_save_state_leaves_valid_json_without_tmp(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    payload, code = arm(root, "inspect", 1)
    assert code == 0
    assert payload["ok"] is True
    folder = root / ".hive" / "agnostic-loop"
    state_path = folder / "state.json"
    assert json.loads(state_path.read_text(encoding="utf-8"))["reward"] == "inspect"
    assert not (folder / "state.json.tmp").exists()
    observe(root, "inspect", True)
    assert json.loads((folder / "policy.json").read_text(encoding="utf-8"))["observations"] == 1
    assert not (folder / "policy.json.tmp").exists()


def test_arm_unknown_reward(tmp_path: Path) -> None:
    payload, code = arm(tmp_path, "spec-gap", 1)
    assert code == 3
    assert payload["ok"] is False


def test_corrupt_state_does_not_crash_status(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    folder = root / ".hive" / "agnostic-loop"
    folder.mkdir(parents=True)
    (folder / "state.json").write_text("{not json", encoding="utf-8")
    report = status(root)
    assert report["ok"] is True
    assert report["status"] == "paused"
    payload, code = arm(root, "inspect", 1)
    assert code == 0
    assert payload["ok"] is True


def test_corrupt_policy_does_not_crash_choose(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    folder = root / ".hive" / "agnostic-loop"
    folder.mkdir(parents=True)
    (folder / "policy.json").write_text("[]", encoding="utf-8")
    names = rewards(root)
    opens = parse_open(None, names)
    payload, code = choose(root, opens, sims=8, horizon=2, seed=1)
    assert code == 0
    assert payload["ok"] is True


def test_observe_and_choose_seed(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    hit, code = observe(root, "inspect", True)
    assert code == 0
    assert hit["arm"]["alpha"] == 2.0
    names = rewards()
    opens = parse_open("inspect=2,fill=1", names)
    assert opens is not None
    assert opens["inspect"] == 2
    assert opens["extend"] == 0
    first, code = choose(root, opens, sims=16, horizon=3, seed=7)
    assert code == 0
    second, code = choose(root, opens, sims=16, horizon=3, seed=7)
    assert first["reward"] == second["reward"]
    assert first["plan"] == second["plan"]


def test_choose_arm_writes_state(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    names = rewards()
    opens = parse_open(None, names)
    payload, code = choose(root, opens, sims=8, horizon=2, seed=1, do_arm=True, cycles=1)
    assert code == 0
    assert payload["arm"]["action"] == "arm"
    assert (root / ".hive/agnostic-loop/state.json").is_file()


def test_trigger_phrases() -> None:
    assert is_agnostic_loop_request("run the agnostic loop")
    assert is_agnostic_loop_request("hive loop kit")
    assert is_agnostic_loop_request("/agnostic-loop")
    assert not is_agnostic_loop_request("what is the agnostic loop")
    assert not is_agnostic_loop_request("is the agnostic loop enabled")
    assert not is_agnostic_loop_request("whether the hive loop kit is installed")
    assert is_agnostic_loop_request("start the agnostic loop")
    assert not is_agnostic_loop_request("implementation loop")
    assert not is_agnostic_loop_request("run a bug hunt")


def test_render_kit_entry_reads_packaged_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    packaged = tmp_path / "hive_planner" / "agnostic_loop.py"
    packaged.parent.mkdir(parents=True)
    packaged.write_text("# packaged kit\n", encoding="utf-8")
    monkeypatch.setattr("hive_planner.agnostic_loop.__file__", str(tmp_path / "missing" / "agnostic_loop.py"))
    monkeypatch.setattr("hive_planner.agnostic_loop.sys._MEIPASS", str(tmp_path), raising=False)
    assert render_kit_entry() == "# packaged kit\n"


def test_install_repairs_unusable_catalog(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    folder = root / ".hive" / "agnostic-loop"
    folder.mkdir(parents=True)
    (folder / "catalog.json").write_text("[]", encoding="utf-8")
    written = install_agnostic_loop(root)
    assert ".hive/agnostic-loop/catalog.json" in written
    catalog = json.loads((folder / "catalog.json").read_text(encoding="utf-8"))
    assert "inspect" in catalog["rewards"]
    payload, code = arm(root, "inspect", 1)
    assert code == 0
    assert payload["ok"] is True


def test_install_keeps_valid_custom_catalog(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    install_agnostic_loop(root)
    path = root / ".hive" / "agnostic-loop" / "catalog.json"
    custom = {
        "rewards": {"custom": {"hooks": ["custom.00"], "rule": "One tick."}},
        "refill": {"custom": {}},
        "chain": {"custom": ["custom"]},
    }
    path.write_text(json.dumps(custom), encoding="utf-8")
    written = install_agnostic_loop(root)
    assert ".hive/agnostic-loop/catalog.json" not in written
    assert json.loads(path.read_text(encoding="utf-8"))["rewards"]["custom"]["hooks"] == ["custom.00"]


def test_install_leaves_no_tmp_kit_files(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    install_agnostic_loop(root)
    leftovers = [path for path in root.rglob("*.tmp") if path.is_file()]
    assert leftovers == []
    assert (root / "scripts" / "agnostic_loop.py").is_file()


def test_install_overwrites_non_utf8_kit_file(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    target = root / "scripts" / "agnostic_loop.py"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"\xff\xfe not utf-8")
    written = install_agnostic_loop(root)
    assert "scripts/agnostic_loop.py" in written
    text = target.read_text(encoding="utf-8")
    assert "def arm(" in text


def test_install_writes_full_kit(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    written = install_agnostic_loop(root)
    assert missing_agnostic_loop_artifacts(root) == []
    for rel in (
        "scripts/agnostic_loop.py",
        "scripts/trajectory_remap.py",
        "scripts/trajectory-loop.md",
        "skills/lay-footnote/SKILL.md",
        ".hive/agnostic-loop/catalog.json",
        ".hive/agnostic-loop/README.md",
        ".cursor/commands/agnostic-loop.md",
    ):
        assert (root / rel).is_file()
    assert "scripts/agnostic_loop.py" in written
    catalog = json.loads((root / ".hive/agnostic-loop/catalog.json").read_text(encoding="utf-8"))
    assert "inspect" in catalog["rewards"]
    assert "fill-unknown" not in catalog["rewards"]
    text = (root / ".cursor/commands/agnostic-loop.md").read_text(encoding="utf-8")
    assert "scripts/agnostic_loop.py" in text
    assert "implementation loop" in text.lower()
    engine = (root / "scripts/agnostic_loop.py").read_text(encoding="utf-8")
    assert "def arm(" in engine
    assert "hive_planner is required" not in engine


def test_malformed_refill_keeps_valid_rewards(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    folder = root / ".hive" / "agnostic-loop"
    folder.mkdir(parents=True)
    (folder / "catalog.json").write_text(
        json.dumps({"rewards": {"inspect": {"hooks": ["inspect.00"]}}, "refill": [], "chain": "nope"}),
        encoding="utf-8",
    )
    names = rewards(root)
    assert "inspect" in names
    payload, code = arm(root, "inspect", 1)
    assert code == 0


def test_cli_choose_invalid_catalog_not_invalid_open(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from hive_planner.cli import main

    root = tmp_path / "proj"
    root.mkdir()
    folder = root / ".hive" / "agnostic-loop"
    folder.mkdir(parents=True)
    (folder / "catalog.json").write_text("[]", encoding="utf-8")
    code = main(["--root", str(root), "agnostic-loop", "choose", "--open", "custom=1"])
    assert code == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert "catalog.json" in payload["blocked_reason"]
    assert payload["action"] == "choose"


def test_invalid_catalog_refuses_arm(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    folder = root / ".hive" / "agnostic-loop"
    folder.mkdir(parents=True)
    (folder / "catalog.json").write_text("[]", encoding="utf-8")
    payload, code = arm(root, "inspect", 1)
    assert code == 3
    assert payload["ok"] is False
    assert "catalog.json" in payload["blocked_reason"]


def test_replaced_catalog_is_used(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    install_agnostic_loop(root)
    path = root / ".hive/agnostic-loop/catalog.json"
    path.write_text(
        json.dumps(
            {
                "rewards": {"custom": {"hooks": ["custom.00"], "rule": "One tick."}},
                "refill": {"custom": {}},
                "chain": {"custom": ["custom"]},
            }
        ),
        encoding="utf-8",
    )
    assert rewards(root) == ("custom",)
    payload, code = arm(root, "custom", 1)
    assert code == 0
    assert payload["hook"] == "custom.00"


def test_cli_arm_oserror_returns_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from hive_planner.cli import main

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("hive_planner.agnostic_loop.arm", boom)
    code = main(["--root", str(tmp_path), "agnostic-loop", "arm", "--reward", "inspect", "--cycles", "1"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["action"] == "arm"
    assert "disk full" in payload["blocked_reason"]


def test_cli_rewards_and_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from hive_planner.cli import main

    root = tmp_path / "proj"
    root.mkdir()
    code = main(["--root", str(root), "agnostic-loop", "rewards"])
    assert code == 0
    names = json.loads(capsys.readouterr().out)
    assert "inspect" in names
    code = main(["--root", str(root), "agnostic-loop", "arm", "--reward", "fill", "--cycles", "1"])
    assert code == 0
    code = main(["--root", str(root), "agnostic-loop", "begin"])
    assert code == 0
    code = main(["--root", str(root), "agnostic-loop", "review", "--note", "ok"])
    assert code == 2


def test_kit_main_arm_oserror_returns_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from hive_planner import agnostic_loop as engine

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(engine, "arm", boom)
    code = engine.main(["arm", "--reward", "inspect", "--cycles", "1"], root=tmp_path)
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["action"] == "arm"
    assert "disk full" in payload["blocked_reason"]


def test_installed_kit_script_runs(tmp_path: Path) -> None:
    import subprocess
    import sys

    root = tmp_path / "proj"
    root.mkdir()
    install_agnostic_loop(root)
    script = root / "scripts" / "agnostic_loop.py"
    proc = subprocess.run(
        [sys.executable, str(script), "rewards"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "inspect" in proc.stdout


def _tiny_hive_source(tmp_path: Path) -> Path:
    source_root = tmp_path / "hive-planner"
    kit = source_root / "starter-kit"
    rules = source_root / ".cursor" / "rules"
    rules.mkdir(parents=True)
    kit.mkdir(parents=True)
    (rules / "architecture.mdc").write_text("# Architecture\n", encoding="utf-8")
    (rules / "task-execution.mdc").write_text("# Task Execution\n", encoding="utf-8")
    (rules / "validation.mdc").write_text("# Validation\n", encoding="utf-8")
    (kit / "spec-kit-agent-integration.md").write_text("# Spec Kit\n", encoding="utf-8")
    return source_root


def test_init_without_flag_skips_agnostic_loop(tmp_path: Path) -> None:
    from hive_planner.bootstrap import init_project
    from hive_planner.config import RepoPaths

    target = tmp_path / "new-project"
    init_project(RepoPaths(root=_tiny_hive_source(tmp_path)), target)
    assert not (target / ".cursor" / "commands" / "agnostic-loop.md").exists()


def test_init_with_flag_installs_agnostic_loop(tmp_path: Path) -> None:
    from hive_planner.bootstrap import init_project
    from hive_planner.config import RepoPaths

    target = tmp_path / "new-project"
    init_project(RepoPaths(root=_tiny_hive_source(tmp_path)), target, agnostic_loop=True)
    assert (target / ".cursor" / "commands" / "agnostic-loop.md").is_file()
    assert (target / "scripts" / "agnostic_loop.py").is_file()
    assert (target / ".hive" / "agnostic-loop" / "catalog.json").is_file()
    assert (target / "skills" / "lay-footnote" / "SKILL.md").is_file()


def test_home_install_wrapper_fails_when_kit_incomplete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.launcher.service import run_project_agnostic_loop_install

    root = tmp_path / "proj"
    root.mkdir()
    monkeypatch.setattr("hive_planner.agnostic_loop.install_agnostic_loop", lambda target: [])
    monkeypatch.setattr(
        "hive_planner.agnostic_loop.missing_agnostic_loop_artifacts",
        lambda target: ["scripts/agnostic_loop.py"],
    )
    result = run_project_agnostic_loop_install(root)
    assert result["ok"] is False
    assert "incomplete" in result["error"]


def test_home_install_wrapper_writes_kit(tmp_path: Path) -> None:
    from hive_planner.agnostic_loop import missing_agnostic_loop_artifacts
    from hive_planner.launcher.service import run_project_agnostic_loop_install

    root = tmp_path / "proj"
    root.mkdir()
    result = run_project_agnostic_loop_install(root)
    assert result["ok"] is True
    assert missing_agnostic_loop_artifacts(root) == []


def test_init_with_flag_fails_when_agnostic_install_incomplete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.bootstrap import BootstrapError, init_project
    from hive_planner.config import RepoPaths

    monkeypatch.setattr("hive_planner.agnostic_loop.install_agnostic_loop", lambda target: [])
    monkeypatch.setattr(
        "hive_planner.agnostic_loop.missing_agnostic_loop_artifacts",
        lambda target: ["scripts/agnostic_loop.py"],
    )
    target = tmp_path / "new-project"
    with pytest.raises(BootstrapError, match="Agnostic-loop install incomplete"):
        init_project(RepoPaths(root=_tiny_hive_source(tmp_path)), target, agnostic_loop=True)

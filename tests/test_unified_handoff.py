from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.bootstrap import init_project
from hive_planner.ci_handoff import run_ci_check
from hive_planner.config import RepoPaths
from hive_planner.vendor_sync import (
    MANIFEST_SCHEMA,
    VendorSyncError,
    check_vendor_manifest,
    load_manifest,
    project_pins_match,
    resolve_manifest_path,
    unified_verify,
    vendor_sync_apply,
    write_project_pins,
)


def _hive_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _deploy_unified_overlays(source: Path, target: Path) -> None:
    from hive_planner.vendor_sync import deploy_continual_learning_overlay, deploy_spec_kit_overlay

    deploy_spec_kit_overlay(source, target)
    deploy_continual_learning_overlay(source, target)


def test_resolve_manifest_from_repo_vendor(tmp_path: Path) -> None:
    repo = tmp_path / "hive"
    repo.mkdir()
    manifest = repo / "vendor" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"schema": "hive-upstream-pins/v1"}\n', encoding="utf-8")

    path = resolve_manifest_path(repo)

    assert path == manifest


def test_check_vendor_manifest_validates_schema(tmp_path: Path) -> None:
    repo = tmp_path / "hive"
    manifest_dir = repo / "vendor"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema": MANIFEST_SCHEMA,
                "updated": "2026-06-26",
                "spec_kit": {
                    "upstream": "https://github.com/github/spec-kit",
                    "path": "vendor/spec-kit",
                    "ref": "TBD",
                    "hive_patch_rev": "1",
                },
                "continual_learning": {
                    "upstream": "https://github.com/cursor/plugins",
                    "path": "vendor/cursor-plugins/continual-learning",
                    "ref": "TBD",
                    "hive_patch_rev": "1",
                },
            }
        ),
        encoding="utf-8",
    )

    report = check_vendor_manifest(repo)

    assert report.ok is True
    assert report.schema == MANIFEST_SCHEMA
    assert any("ref is not pinned" in issue for issue in report.issues)


def test_check_vendor_manifest_rejects_invalid_schema(tmp_path: Path) -> None:
    repo = tmp_path / "hive"
    manifest_dir = repo / "vendor"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "manifest.json").write_text('{"schema": "wrong"}\n', encoding="utf-8")

    report = check_vendor_manifest(repo)

    assert report.ok is False


def test_vendor_sync_check_fails_when_pinned_vendor_paths_missing(tmp_path: Path) -> None:
    repo = tmp_path / "hive"
    manifest_dir = repo / "vendor"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema": MANIFEST_SCHEMA,
                "spec_kit": {
                    "upstream": "https://github.com/github/spec-kit",
                    "path": "vendor/spec-kit",
                    "ref": "abc123",
                    "hive_patch_rev": "1",
                },
                "continual_learning": {
                    "upstream": "https://github.com/cursor/plugins",
                    "path": "vendor/cursor-plugins/continual-learning",
                    "ref": "def456",
                    "hive_patch_rev": "1",
                },
            }
        ),
        encoding="utf-8",
    )

    from hive_planner.vendor_sync import vendor_sync_check

    report = vendor_sync_check(repo)

    assert report.ok is False
    assert any("vendor path missing" in issue for issue in report.issues)


def test_vendor_sync_apply_fails_on_unpinned_refs(tmp_path: Path) -> None:
    repo = tmp_path / "hive"
    manifest_dir = repo / "vendor"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema": MANIFEST_SCHEMA,
                "spec_kit": {
                    "upstream": "u",
                    "path": "vendor/spec-kit",
                    "ref": "TBD",
                    "hive_patch_rev": "1",
                },
                "continual_learning": {
                    "upstream": "u",
                    "path": "vendor/cl",
                    "ref": "TBD",
                    "hive_patch_rev": "1",
                },
            }
        ),
        encoding="utf-8",
    )

    report = vendor_sync_apply(repo)

    assert report.ok is False


def test_project_pins_match_compares_ref_and_patch_rev() -> None:
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "spec_kit": {"ref": "abc123", "hive_patch_rev": "1"},
        "continual_learning": {"ref": "def456", "hive_patch_rev": "2"},
    }
    pins = {
        "schema": MANIFEST_SCHEMA,
        "spec_kit": {"ref": "abc123", "hive_patch_rev": "1"},
        "continual_learning": {"ref": "def456", "hive_patch_rev": "2"},
    }

    assert project_pins_match(manifest, pins) is True
    pins["continual_learning"]["hive_patch_rev"] = "3"
    assert project_pins_match(manifest, pins) is False


def test_unified_verify_bootstrapped_project_without_vendor_manifest(tmp_path: Path) -> None:
    from hive_planner.vendor_sync import load_manifest, packaged_manifest_path

    repo = tmp_path / "project"
    repo.mkdir()
    pins = load_manifest(packaged_manifest_path())
    write_project_pins(repo, pins)
    _deploy_unified_overlays(_hive_repo_root(), repo)

    report = unified_verify(RepoPaths(root=repo))

    assert report.pins_match is True
    assert report.ok is True


def test_unified_verify_checks_overlay_with_local_manifest(tmp_path: Path) -> None:
    from hive_planner.vendor_sync import load_manifest, packaged_manifest_path, unified_verify

    project = tmp_path / "project"
    vendor = project / "vendor"
    vendor.mkdir(parents=True)
    manifest = load_manifest(packaged_manifest_path())
    (vendor / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_project_pins(project, manifest)

    report = unified_verify(RepoPaths(root=project))

    assert report.ok is False
    assert report.pins_match is False
    assert any("spec-kit overlay missing" in issue for issue in report.issues)


def test_unified_verify_fails_when_spec_kit_overlay_missing(tmp_path: Path) -> None:
    from hive_planner.vendor_sync import load_manifest, packaged_manifest_path

    repo = tmp_path / "project"
    repo.mkdir()
    write_project_pins(repo, load_manifest(packaged_manifest_path()))

    report = unified_verify(RepoPaths(root=repo))

    assert report.ok is False
    assert report.pins_match is False
    assert any("spec-kit overlay missing" in issue for issue in report.issues)


def test_unified_verify_detects_stale_overlay_when_packaged_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hive_planner.vendor_sync as vendor_sync

    repo = tmp_path / "project"
    repo.mkdir()
    pins = vendor_sync.load_manifest(vendor_sync.packaged_manifest_path())
    vendor_sync.write_project_pins(repo, pins)
    _deploy_unified_overlays(_hive_repo_root(), repo)
    (repo / ".hive" / "spec-kit" / ".hive-overlay-rev").write_text("0\n", encoding="utf-8")

    original_load = vendor_sync.load_manifest

    def _load_manifest(path: Path) -> dict:
        if "vendor_templates" in path.as_posix():
            raise vendor_sync.VendorSyncError("packaged manifest unavailable")
        return original_load(path)

    monkeypatch.setattr(vendor_sync, "load_manifest", _load_manifest)

    report = vendor_sync.unified_verify(RepoPaths(root=repo))

    assert report.ok is False
    assert any("spec-kit overlay stale" in issue for issue in report.issues)


def test_unified_verify_with_project_pins(tmp_path: Path) -> None:
    from hive_planner.vendor_sync import load_manifest, packaged_manifest_path

    repo = tmp_path / "project"
    vendor = repo / "vendor"
    vendor.mkdir(parents=True)
    manifest = load_manifest(packaged_manifest_path())
    (vendor / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_project_pins(repo, manifest)
    _deploy_unified_overlays(_hive_repo_root(), repo)

    report = unified_verify(RepoPaths(root=repo))

    assert report.pins_match is True
    assert report.ok is True


def test_init_unified_writes_upstream_pins(tmp_path: Path) -> None:
    source_root = tmp_path / "hive-planner"
    kit = source_root / "starter-kit"
    rules = source_root / ".cursor" / "rules"
    rules.mkdir(parents=True)
    kit.mkdir(parents=True)
    (rules / "architecture.mdc").write_text("# a\n", encoding="utf-8")
    (rules / "task-execution.mdc").write_text("# t\n", encoding="utf-8")
    (rules / "validation.mdc").write_text("# v\n", encoding="utf-8")
    (kit / "spec-kit-agent-integration.md").write_text("# sk\n", encoding="utf-8")
    target = tmp_path / "boot-project"

    init_project(RepoPaths(root=source_root), target, agent_handoff="unified")

    pins = target / ".hive" / "upstream-pins.json"
    assert pins.is_file()
    data = json.loads(pins.read_text(encoding="utf-8"))
    assert data.get("schema") == MANIFEST_SCHEMA


def test_init_unified_deploys_spec_kit_overlay(tmp_path: Path) -> None:
    source_root = tmp_path / "hive-planner"
    kit = source_root / "starter-kit"
    rules = source_root / ".cursor" / "rules"
    rules.mkdir(parents=True)
    kit.mkdir(parents=True)
    (rules / "architecture.mdc").write_text("# a\n", encoding="utf-8")
    (rules / "task-execution.mdc").write_text("# t\n", encoding="utf-8")
    (rules / "validation.mdc").write_text("# v\n", encoding="utf-8")
    (kit / "spec-kit-agent-integration.md").write_text("# sk\n", encoding="utf-8")
    target = tmp_path / "boot-project"

    init_project(RepoPaths(root=source_root), target, agent_handoff="unified")

    spec_template = target / ".hive" / "spec-kit" / "templates" / "spec-template.md"
    tasks_template = target / ".hive" / "spec-kit" / "templates" / "tasks-template.md"
    workflow = target / ".hive" / "spec-kit" / "WORKFLOW.md"
    assert spec_template.is_file()
    assert tasks_template.is_file()
    assert workflow.is_file()
    spec_text = spec_template.read_text(encoding="utf-8")
    tasks_text = tasks_template.read_text(encoding="utf-8")
    assert "Agent navigation (Rosetta Stone)" in spec_text
    assert "Integration wiring audit" in tasks_text
    assert "spec-drift-check" in workflow.read_text(encoding="utf-8")


def test_init_unified_deploys_cl_plugin(tmp_path: Path) -> None:
    source_root = tmp_path / "hive-planner"
    kit = source_root / "starter-kit"
    rules = source_root / ".cursor" / "rules"
    rules.mkdir(parents=True)
    kit.mkdir(parents=True)
    (rules / "architecture.mdc").write_text("# a\n", encoding="utf-8")
    (rules / "task-execution.mdc").write_text("# t\n", encoding="utf-8")
    (rules / "validation.mdc").write_text("# v\n", encoding="utf-8")
    (kit / "spec-kit-agent-integration.md").write_text("# sk\n", encoding="utf-8")
    target = tmp_path / "boot-project"

    init_project(RepoPaths(root=source_root), target, agent_handoff="unified")

    agent_md = target / ".cursor" / "plugins" / "hive-continual-learning" / "agents" / "agents-memory-updater.md"
    skill_md = target / ".cursor" / "plugins" / "hive-continual-learning" / "skills" / "continual-learning" / "SKILL.md"
    workflow = target / ".cursor" / "plugins" / "hive-continual-learning" / "WORKFLOW.md"
    rev = target / ".cursor" / "plugins" / "hive-continual-learning" / ".hive-overlay-rev"
    assert agent_md.is_file()
    assert skill_md.is_file()
    assert workflow.is_file()
    assert rev.is_file()
    agent_text = agent_md.read_text(encoding="utf-8")
    skill_text = skill_md.read_text(encoding="utf-8")
    assert "Durable Workspace Facts" in agent_text
    assert "Integration wiring audit" in skill_text
    assert "spec-drift-check" in workflow.read_text(encoding="utf-8")
    assert rev.read_text(encoding="utf-8").strip() == "2"


def test_write_project_pins_refreshes_when_manifest_changes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    initial = {
        "schema": MANIFEST_SCHEMA,
        "spec_kit": {"upstream": "u", "path": "p", "ref": "oldsha", "hive_patch_rev": "1"},
        "continual_learning": {"upstream": "u", "path": "p", "ref": "oldsha2", "hive_patch_rev": "1"},
    }
    updated = {
        "schema": MANIFEST_SCHEMA,
        "spec_kit": {"upstream": "u", "path": "p", "ref": "newsha", "hive_patch_rev": "2"},
        "continual_learning": {"upstream": "u", "path": "p", "ref": "newsha2", "hive_patch_rev": "2"},
    }
    write_project_pins(project, initial)
    write_project_pins(project, updated)

    data = json.loads((project / ".hive" / "upstream-pins.json").read_text(encoding="utf-8"))

    assert data["spec_kit"]["ref"] == "newsha"
    assert data["spec_kit"]["hive_patch_rev"] == "2"


def test_ci_unified_vendor_requires_pins_for_unified_projects(tmp_path: Path) -> None:
    from hive_planner.project_profile import write_project_profile
    from hive_planner.vendor_sync import ci_unified_vendor_step

    project = tmp_path / "unified-project"
    project.mkdir()
    write_project_profile(project, profile="minimal", project_name="unified-project", agent_handoff_mode="unified")

    ok, detail = ci_unified_vendor_step(RepoPaths(root=project), hive_source=False, require_pins=True)

    assert ok is False
    assert "missing .hive/upstream-pins.json" in detail


def test_deploy_spec_kit_overlay_refreshes_when_patch_rev_changes(tmp_path: Path) -> None:
    from hive_planner.vendor_sync import deploy_spec_kit_overlay, packaged_spec_kit_overlay_path

    source = tmp_path / "hive"
    source.mkdir()
    vendor = source / "vendor"
    vendor.mkdir()
    (vendor / "manifest.json").write_text(
        json.dumps(
            {
                "schema": MANIFEST_SCHEMA,
                "spec_kit": {
                    "upstream": "u",
                    "path": "p",
                    "ref": "abc",
                    "hive_patch_rev": "1",
                },
                "continual_learning": {
                    "upstream": "u",
                    "path": "p",
                    "ref": "def",
                    "hive_patch_rev": "1",
                },
            }
        ),
        encoding="utf-8",
    )
    project = tmp_path / "project"
    project.mkdir()
    overlay_src = packaged_spec_kit_overlay_path()
    tasks_src = overlay_src / "templates" / "tasks-template.md"
    original = tasks_src.read_text(encoding="utf-8")

    deploy_spec_kit_overlay(source, project)
    tasks_dest = project / ".hive" / "spec-kit" / "templates" / "tasks-template.md"
    assert tasks_dest.is_file()
    tasks_dest.write_text("# stale overlay\n", encoding="utf-8")

    (vendor / "manifest.json").write_text(
        json.dumps(
            {
                "schema": MANIFEST_SCHEMA,
                "spec_kit": {
                    "upstream": "u",
                    "path": "p",
                    "ref": "abc",
                    "hive_patch_rev": "2",
                },
                "continual_learning": {
                    "upstream": "u",
                    "path": "p",
                    "ref": "def",
                    "hive_patch_rev": "1",
                },
            }
        ),
        encoding="utf-8",
    )
    deploy_spec_kit_overlay(source, project)

    assert "Integration wiring audit" in tasks_dest.read_text(encoding="utf-8")
    assert (project / ".hive" / "spec-kit" / ".hive-overlay-rev").read_text(encoding="utf-8").strip() == "2"


def test_deploy_continual_learning_overlay_refreshes_when_patch_rev_changes(tmp_path: Path) -> None:
    from hive_planner.vendor_sync import deploy_continual_learning_overlay, packaged_continual_learning_overlay_path

    source = tmp_path / "hive"
    source.mkdir()
    vendor = source / "vendor"
    vendor.mkdir()
    (vendor / "manifest.json").write_text(
        json.dumps(
            {
                "schema": MANIFEST_SCHEMA,
                "spec_kit": {
                    "upstream": "u",
                    "path": "p",
                    "ref": "abc",
                    "hive_patch_rev": "1",
                },
                "continual_learning": {
                    "upstream": "u",
                    "path": "p",
                    "ref": "def",
                    "hive_patch_rev": "1",
                },
            }
        ),
        encoding="utf-8",
    )
    project = tmp_path / "project"
    project.mkdir()
    overlay_src = packaged_continual_learning_overlay_path()
    agent_src = overlay_src / "agents" / "agents-memory-updater.md"

    deploy_continual_learning_overlay(source, project)
    agent_dest = project / ".cursor" / "plugins" / "hive-continual-learning" / "agents" / "agents-memory-updater.md"
    assert agent_dest.is_file()
    agent_dest.write_text("# stale overlay\n", encoding="utf-8")

    (vendor / "manifest.json").write_text(
        json.dumps(
            {
                "schema": MANIFEST_SCHEMA,
                "spec_kit": {
                    "upstream": "u",
                    "path": "p",
                    "ref": "abc",
                    "hive_patch_rev": "1",
                },
                "continual_learning": {
                    "upstream": "u",
                    "path": "p",
                    "ref": "def",
                    "hive_patch_rev": "2",
                },
            }
        ),
        encoding="utf-8",
    )
    deploy_continual_learning_overlay(source, project)

    assert "Durable Workspace Facts" in agent_dest.read_text(encoding="utf-8")
    rev = project / ".cursor" / "plugins" / "hive-continual-learning" / ".hive-overlay-rev"
    assert rev.read_text(encoding="utf-8").strip() == "2"
    assert agent_src.read_text(encoding="utf-8")  # ensure packaged overlay still readable


def test_deploy_unified_vendor_artifacts_skips_overlay_when_pins_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hive_planner.vendor_sync as vendor_sync

    def _fail_resolve(_root: Path) -> Path:
        raise vendor_sync.VendorSyncError("no manifest")

    monkeypatch.setattr(vendor_sync, "resolve_manifest_path", _fail_resolve)

    source = tmp_path / "empty-source"
    source.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    warnings: list[str] = []

    vendor_sync.deploy_unified_vendor_artifacts(source, project, warnings=warnings)

    assert warnings
    assert not (project / ".hive" / "spec-kit" / "templates" / "spec-template.md").is_file()
    assert not (
        project / ".cursor" / "plugins" / "hive-continual-learning" / "agents" / "agents-memory-updater.md"
    ).is_file()


def test_deploy_spec_kit_overlay_uses_target_pins_rev_for_refresh(tmp_path: Path) -> None:
    from hive_planner.vendor_sync import deploy_spec_kit_overlay, write_project_pins

    source = tmp_path / "hive"
    vendor = source / "vendor"
    vendor.mkdir(parents=True)
    (vendor / "manifest.json").write_text(
        json.dumps(
            {
                "schema": MANIFEST_SCHEMA,
                "spec_kit": {"upstream": "u", "path": "p", "ref": "abc", "hive_patch_rev": "1"},
                "continual_learning": {"upstream": "u", "path": "p", "ref": "def", "hive_patch_rev": "1"},
            }
        ),
        encoding="utf-8",
    )
    project = tmp_path / "project"
    project.mkdir()
    pins = {
        "schema": MANIFEST_SCHEMA,
        "spec_kit": {"upstream": "u", "path": "p", "ref": "abc", "hive_patch_rev": "2"},
        "continual_learning": {"upstream": "u", "path": "p", "ref": "def", "hive_patch_rev": "1"},
    }
    write_project_pins(project, pins)
    tasks_dest = project / ".hive" / "spec-kit" / "templates" / "tasks-template.md"
    tasks_dest.parent.mkdir(parents=True)
    tasks_dest.write_text("# stale\n", encoding="utf-8")
    (project / ".hive" / "spec-kit" / ".hive-overlay-rev").write_text("1\n", encoding="utf-8")

    deploy_spec_kit_overlay(source, project)

    assert "Integration wiring audit" in tasks_dest.read_text(encoding="utf-8")
    assert (project / ".hive" / "spec-kit" / ".hive-overlay-rev").read_text(encoding="utf-8").strip() == "2"


def test_ci_unified_vendor_checks_overlay_when_packaged_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hive_planner.vendor_sync as vendor_sync

    project = tmp_path / "unified-project"
    project.mkdir()
    vendor_sync.write_project_pins(project, vendor_sync.load_manifest(vendor_sync.packaged_manifest_path()))

    original_load = vendor_sync.load_manifest

    def _load_manifest(path: Path) -> dict:
        if "vendor_templates" in path.as_posix():
            raise vendor_sync.VendorSyncError("packaged manifest unavailable")
        return original_load(path)

    monkeypatch.setattr(vendor_sync, "load_manifest", _load_manifest)

    ok, detail = vendor_sync.ci_unified_vendor_step(RepoPaths(root=project), hive_source=False)

    assert ok is False
    assert "spec-kit overlay missing" in detail


def test_ci_unified_vendor_checks_overlay_with_local_manifest(tmp_path: Path) -> None:
    from hive_planner.vendor_sync import ci_unified_vendor_step, load_manifest, packaged_manifest_path

    project = tmp_path / "unified-project"
    vendor = project / "vendor"
    vendor.mkdir(parents=True)
    manifest = load_manifest(packaged_manifest_path())
    (vendor / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_project_pins(project, manifest)

    ok, detail = ci_unified_vendor_step(RepoPaths(root=project), hive_source=False)

    assert ok is False
    assert "spec-kit overlay missing" in detail


def test_ci_unified_vendor_fails_when_spec_kit_overlay_missing(tmp_path: Path) -> None:
    from hive_planner.vendor_sync import ci_unified_vendor_step, load_manifest, packaged_manifest_path

    project = tmp_path / "unified-project"
    project.mkdir()
    write_project_pins(project, load_manifest(packaged_manifest_path()))

    ok, detail = ci_unified_vendor_step(RepoPaths(root=project), hive_source=False)

    assert ok is False
    assert "spec-kit overlay missing" in detail


def test_ci_unified_vendor_accepts_bootstrapped_pins_without_vendor_manifest(tmp_path: Path) -> None:
    from hive_planner.vendor_sync import ci_unified_vendor_step, load_manifest, packaged_manifest_path

    project = tmp_path / "unified-project"
    project.mkdir()
    pins = load_manifest(packaged_manifest_path())
    write_project_pins(project, pins)
    _deploy_unified_overlays(_hive_repo_root(), project)

    ok, detail = ci_unified_vendor_step(RepoPaths(root=project), hive_source=False)

    assert ok is True
    assert "project pins and unified overlays ok" in detail


def test_ci_unified_vendor_fails_when_pins_patch_rev_stale(tmp_path: Path) -> None:
    from hive_planner.vendor_sync import ci_unified_vendor_step, load_manifest, packaged_manifest_path

    project = tmp_path / "unified-project"
    project.mkdir()
    pins = load_manifest(packaged_manifest_path())
    pins["spec_kit"]["hive_patch_rev"] = "0"
    write_project_pins(project, pins)

    ok, detail = ci_unified_vendor_step(RepoPaths(root=project), hive_source=False)

    assert ok is False
    assert "drift from hive-planner manifest" in detail


def test_ci_unified_vendor_on_hive_source_repo() -> None:
    from hive_planner.config import RepoPaths

    root = Path(__file__).resolve().parents[1]
    if not (root / "vendor" / "manifest.json").is_file():
        pytest.skip("hive source vendor manifest not present")
    report = run_ci_check(RepoPaths(root=root), skip_pytest=True, check_map_drift=False, check_roadmap=False)
    step_names = [s.name for s in report.steps]
    assert "unified-vendor" in step_names
    vendor_step = next(s for s in report.steps if s.name == "unified-vendor")
    assert vendor_step.ok is True

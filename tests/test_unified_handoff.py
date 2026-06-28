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
    repo = tmp_path / "project"
    repo.mkdir()
    pins = {
        "schema": MANIFEST_SCHEMA,
        "updated": "2026-06-26",
        "spec_kit": {
            "upstream": "https://github.com/github/spec-kit",
            "path": "vendor/spec-kit",
            "ref": "b7e67f55bf7a937aaa57dbe0a8198774e285de3a",
            "hive_patch_rev": "1",
        },
        "continual_learning": {
            "upstream": "https://github.com/cursor/plugins",
            "path": "vendor/cursor-plugins/continual-learning",
            "ref": "0452e08a314c03621ec5ac1324f1ad1dd824f1a4",
            "hive_patch_rev": "1",
        },
    }
    write_project_pins(repo, pins)

    report = unified_verify(RepoPaths(root=repo))

    assert report.pins_match is True
    assert report.ok is True


def test_unified_verify_with_project_pins(tmp_path: Path) -> None:
    repo = tmp_path / "project"
    repo.mkdir()
    manifest = {
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
    vendor = repo / "vendor"
    vendor.mkdir()
    (vendor / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_project_pins(repo, manifest)

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


def test_ci_unified_vendor_accepts_bootstrapped_pins_without_vendor_manifest(tmp_path: Path) -> None:
    from hive_planner.vendor_sync import ci_unified_vendor_step

    project = tmp_path / "unified-project"
    project.mkdir()
    pins = {
        "schema": MANIFEST_SCHEMA,
        "updated": "2026-06-26",
        "spec_kit": {
            "upstream": "https://github.com/github/spec-kit",
            "path": "vendor/spec-kit",
            "ref": "b7e67f55bf7a937aaa57dbe0a8198774e285de3a",
            "hive_patch_rev": "1",
        },
        "continual_learning": {
            "upstream": "https://github.com/cursor/plugins",
            "path": "vendor/cursor-plugins/continual-learning",
            "ref": "0452e08a314c03621ec5ac1324f1ad1dd824f1a4",
            "hive_patch_rev": "1",
        },
    }
    write_project_pins(project, pins)

    ok, detail = ci_unified_vendor_step(RepoPaths(root=project), hive_source=False)

    assert ok is True
    assert detail == "project pins valid"


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

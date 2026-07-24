"""Vendor manifest and unified upstream pin verification (Stage 9)."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from hive_planner.config import RepoPaths

MANIFEST_SCHEMA = "hive-upstream-pins/v1"
PROJECT_PINS_REL = ".hive/upstream-pins.json"
SPEC_KIT_OVERLAY_REL = ".hive/spec-kit"
CL_OVERLAY_REL = ".cursor/plugins/hive-continual-learning"
OVERLAY_REV_FILE = ".hive-overlay-rev"
SPEC_KIT_OVERLAY_REV_FILE = OVERLAY_REV_FILE
COMPONENT_KEYS = ("spec_kit", "continual_learning")
COMPONENT_REQUIRED_FIELDS = frozenset({"upstream", "path", "ref", "hive_patch_rev"})

PLACEHOLDER_REFS = frozenset({"TBD", "tbd", ""})


class VendorSyncError(Exception):
    """Vendor manifest load or validation failed."""


@dataclass
class VendorComponentStatus:
    name: str
    path: str
    ref: str
    present: bool
    ref_pinned: bool
    hive_patch_rev: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "ref": self.ref,
            "present": self.present,
            "ref_pinned": self.ref_pinned,
            "hive_patch_rev": self.hive_patch_rev,
        }


@dataclass
class VendorManifestReport:
    ok: bool
    manifest_path: str
    schema: str | None = None
    issues: list[str] = field(default_factory=list)
    components: list[VendorComponentStatus] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "manifest_path": self.manifest_path,
            "schema": self.schema,
            "issues": self.issues,
            "components": [c.to_dict() for c in self.components],
        }


@dataclass
class UnifiedVerifyReport:
    ok: bool
    manifest: VendorManifestReport
    project_pins_path: str | None = None
    pins_match: bool | None = None
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "manifest": self.manifest.to_dict(),
            "project_pins_path": self.project_pins_path,
            "pins_match": self.pins_match,
            "issues": self.issues,
        }


def packaged_manifest_path() -> Path:
    return Path(__file__).resolve().parent / "vendor_templates" / "manifest.json"


def packaged_spec_kit_overlay_path() -> Path:
    return Path(__file__).resolve().parent / "vendor_templates" / "spec-kit"


def packaged_continual_learning_overlay_path() -> Path:
    return Path(__file__).resolve().parent / "vendor_templates" / "continual-learning"


def _spec_kit_overlay_complete(path: Path) -> bool:
    return (path / "templates" / "spec-template.md").is_file() and (path / "WORKFLOW.md").is_file()


def _continual_learning_overlay_complete(path: Path) -> bool:
    return (
        (path / "agents" / "agents-memory-updater.md").is_file()
        and (path / "skills" / "continual-learning" / "SKILL.md").is_file()
        and (path / "WORKFLOW.md").is_file()
    )


def resolve_spec_kit_overlay_path(source_root: Path) -> Path:
    primary = source_root.resolve() / "vendor" / "patches" / "spec-kit"
    if _spec_kit_overlay_complete(primary):
        return primary
    packaged = packaged_spec_kit_overlay_path()
    if _spec_kit_overlay_complete(packaged):
        return packaged
    raise VendorSyncError("Spec Kit overlay not found in vendor/patches/spec-kit or package templates")


def resolve_continual_learning_overlay_path(source_root: Path) -> Path:
    primary = source_root.resolve() / "vendor" / "patches" / "continual-learning"
    if _continual_learning_overlay_complete(primary):
        return primary
    packaged = packaged_continual_learning_overlay_path()
    if _continual_learning_overlay_complete(packaged):
        return packaged
    raise VendorSyncError(
        "Continual Learning overlay not found in vendor/patches/continual-learning or package templates"
    )


def resolve_manifest_path(repo_root: Path) -> Path:
    primary = repo_root.resolve() / "vendor" / "manifest.json"
    if primary.is_file():
        return primary
    packaged = packaged_manifest_path()
    if packaged.is_file():
        return packaged
    raise VendorSyncError("vendor/manifest.json not found in repo or package templates")


def load_manifest(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VendorSyncError(f"Could not read manifest: {path}") from exc
    if not isinstance(data, dict):
        raise VendorSyncError(f"Manifest must be a JSON object: {path}")
    return data


def validate_manifest_data(data: dict, *, manifest_path: Path, repo_root: Path) -> VendorManifestReport:
    issues: list[str] = []
    schema = data.get("schema")
    if schema != MANIFEST_SCHEMA:
        issues.append(f"schema must be {MANIFEST_SCHEMA!r}, got {schema!r}")

    components: list[VendorComponentStatus] = []
    for key in COMPONENT_KEYS:
        block = data.get(key)
        if not isinstance(block, dict):
            issues.append(f"missing or invalid component block: {key}")
            continue
        missing_fields = sorted(COMPONENT_REQUIRED_FIELDS - set(block.keys()))
        if missing_fields:
            issues.append(f"{key} missing fields: {', '.join(missing_fields)}")
        ref = str(block.get("ref", "")).strip()
        rel_path = str(block.get("path", "")).strip()
        abs_path = repo_root / rel_path if rel_path else repo_root
        present = abs_path.is_dir() and any(abs_path.iterdir()) if abs_path.is_dir() else abs_path.is_file()
        ref_pinned = ref not in PLACEHOLDER_REFS
        if not ref_pinned:
            issues.append(f"{key}.ref is not pinned (still {ref or 'empty'})")
        if ref_pinned and not present:
            issues.append(f"{key} vendor path missing or empty: {rel_path}")
        components.append(
            VendorComponentStatus(
                name=key,
                path=rel_path,
                ref=ref,
                present=present,
                ref_pinned=ref_pinned,
                hive_patch_rev=str(block.get("hive_patch_rev", "")),
            )
        )

    structural_ok = schema == MANIFEST_SCHEMA and not any(
        issue.startswith("missing or invalid") or "missing fields" in issue for issue in issues
    )
    return VendorManifestReport(
        ok=structural_ok,
        manifest_path=manifest_path.as_posix(),
        schema=str(schema) if schema else None,
        issues=issues,
        components=components,
    )


def validate_project_pins(data: dict) -> VendorManifestReport:
    """Validate a bootstrapped `.hive/upstream-pins.json` snapshot (no vendor path checks)."""
    issues: list[str] = []
    schema = data.get("schema")
    if schema != MANIFEST_SCHEMA:
        issues.append(f"schema must be {MANIFEST_SCHEMA!r}, got {schema!r}")

    components: list[VendorComponentStatus] = []
    for key in COMPONENT_KEYS:
        block = data.get(key)
        if not isinstance(block, dict):
            issues.append(f"missing or invalid component block: {key}")
            continue
        missing_fields = sorted(COMPONENT_REQUIRED_FIELDS - set(block.keys()))
        if missing_fields:
            issues.append(f"{key} missing fields: {', '.join(missing_fields)}")
        ref = str(block.get("ref", "")).strip()
        rel_path = str(block.get("path", "")).strip()
        ref_pinned = ref not in PLACEHOLDER_REFS
        if not ref_pinned:
            issues.append(f"{key}.ref is not pinned (still {ref or 'empty'})")
        components.append(
            VendorComponentStatus(
                name=key,
                path=rel_path,
                ref=ref,
                present=True,
                ref_pinned=ref_pinned,
                hive_patch_rev=str(block.get("hive_patch_rev", "")),
            )
        )

    structural_ok = schema == MANIFEST_SCHEMA and not any(
        issue.startswith("missing or invalid") or "missing fields" in issue for issue in issues
    )
    pins_ok = structural_ok and all(c.ref_pinned for c in components)
    if structural_ok and not pins_ok:
        issues.append("project pins must pin all component refs")
    return VendorManifestReport(
        ok=pins_ok,
        manifest_path=PROJECT_PINS_REL,
        schema=str(schema) if schema else None,
        issues=issues,
        components=components,
    )


def check_vendor_manifest(repo_root: Path) -> VendorManifestReport:
    manifest_path = resolve_manifest_path(repo_root)
    data = load_manifest(manifest_path)
    return validate_manifest_data(data, manifest_path=manifest_path, repo_root=repo_root.resolve())


def write_project_pins(target: Path, manifest: dict, *, force: bool = False) -> Path:
    dest = target.resolve() / PROJECT_PINS_REL
    if dest.exists() and not force:
        existing = read_project_pins(target)
        if existing is not None and project_pins_match(manifest, existing):
            return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return dest


def read_project_pins(project_root: Path) -> dict | None:
    path = project_root.resolve() / PROJECT_PINS_REL
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _pin_snapshot_for_compare(data: dict) -> dict:
    snapshot: dict = {"schema": data.get("schema"), "updated": data.get("updated")}
    for key in COMPONENT_KEYS:
        block = data.get(key)
        if isinstance(block, dict):
            snapshot[key] = {
                "ref": block.get("ref"),
                "hive_patch_rev": block.get("hive_patch_rev"),
            }
    return snapshot


def project_pins_match(manifest: dict, project_pins: dict) -> bool:
    return _pin_snapshot_for_compare(manifest) == _pin_snapshot_for_compare(project_pins)


def _verify_spec_kit_overlay(root: Path, *, manifest: dict | None = None) -> list[str]:
    issues: list[str] = []
    overlay_root = root / SPEC_KIT_OVERLAY_REL
    for rel in (
        "README.md",
        "WORKFLOW.md",
        "templates/spec-template.md",
        "templates/tasks-template.md",
    ):
        if not (overlay_root / rel).is_file():
            issues.append(f"spec-kit overlay missing: {SPEC_KIT_OVERLAY_REL}/{rel}")
    if manifest is not None:
        expected_rev = _spec_kit_patch_rev(manifest)
        if expected_rev:
            deployed_rev = _read_component_overlay_rev(root, SPEC_KIT_OVERLAY_REL)
            if deployed_rev != expected_rev:
                issues.append(
                    f"spec-kit overlay stale (deployed rev {deployed_rev!r}, expected {expected_rev!r})"
                )
    return issues


def _verify_cl_overlay(root: Path, *, manifest: dict | None = None) -> list[str]:
    issues: list[str] = []
    overlay_root = root / CL_OVERLAY_REL
    for rel in (
        "README.md",
        "WORKFLOW.md",
        "agents/agents-memory-updater.md",
        "skills/continual-learning/SKILL.md",
        ".cursor-plugin/plugin.json",
        # Cursor 3.x stop hook (Python) — without these, CL never triggers
        "hooks/hooks.json",
        "hooks/continual-learning-stop.py",
    ):
        if not (overlay_root / rel).is_file():
            issues.append(f"continual-learning overlay missing: {CL_OVERLAY_REL}/{rel}")
    hooks_json = overlay_root / "hooks" / "hooks.json"
    if hooks_json.is_file():
        try:
            hooks_text = hooks_json.read_text(encoding="utf-8")
        except OSError:
            hooks_text = ""
        if "bun " in hooks_text or "bun\t" in hooks_text or '"bun' in hooks_text:
            issues.append(
                f"continual-learning overlay uses Bun stop hook (need Python): "
                f"{CL_OVERLAY_REL}/hooks/hooks.json"
            )
        if "continual-learning-stop.py" not in hooks_text:
            issues.append(
                f"continual-learning overlay hooks.json must invoke continual-learning-stop.py: "
                f"{CL_OVERLAY_REL}/hooks/hooks.json"
            )
    if manifest is not None:
        expected_rev = _continual_learning_patch_rev(manifest)
        if expected_rev:
            deployed_rev = _read_component_overlay_rev(root, CL_OVERLAY_REL)
            if deployed_rev != expected_rev:
                issues.append(
                    f"continual-learning overlay stale (deployed rev {deployed_rev!r}, expected {expected_rev!r})"
                )
    return issues


def _verify_headless_cl_artifacts(root: Path, *, runtime: str) -> list[str]:
    from hive_planner.cl_runtime import continual_learning_artifact_paths

    issues: list[str] = []
    for rel in continual_learning_artifact_paths(runtime):
        if not (root / rel).is_file():
            issues.append(f"headless CL artifact missing: {rel}")
    return issues


def _verify_unified_overlays(root: Path, *, manifest: dict | None, cl_runtime: str | None = None) -> list[str]:
    from hive_planner.cl_runtime import requires_cursor_plugin, resolve_cl_runtime

    runtime = cl_runtime or resolve_cl_runtime(root)
    issues: list[str] = []
    issues.extend(_verify_spec_kit_overlay(root, manifest=manifest))
    if requires_cursor_plugin(runtime):
        issues.extend(_verify_cl_overlay(root, manifest=manifest))
    else:
        issues.extend(_verify_headless_cl_artifacts(root, runtime=runtime))
    return issues


def overlay_issues_as_missing(root: Path, manifest: dict | None) -> list[str]:
    """Map overlay verification issues to artifact paths for handoff validation."""
    from hive_planner.cl_runtime import requires_cursor_plugin, resolve_cl_runtime

    runtime = resolve_cl_runtime(root)
    missing: list[str] = []
    for issue in _verify_spec_kit_overlay(root, manifest=manifest):
        if issue.startswith("spec-kit overlay missing: "):
            rel = issue.split("spec-kit overlay missing: ", 1)[1]
            if rel not in missing:
                missing.append(rel)
        elif "spec-kit overlay stale" in issue:
            rel = f"{SPEC_KIT_OVERLAY_REL}/{OVERLAY_REV_FILE}"
            if rel not in missing:
                missing.append(rel)
    if not requires_cursor_plugin(runtime):
        return missing
    for issue in _verify_cl_overlay(root, manifest=manifest):
        if issue.startswith("continual-learning overlay missing: "):
            rel = issue.split("continual-learning overlay missing: ", 1)[1]
            if rel not in missing:
                missing.append(rel)
        elif "continual-learning overlay stale" in issue:
            rel = f"{CL_OVERLAY_REL}/{OVERLAY_REV_FILE}"
            if rel not in missing:
                missing.append(rel)
    return missing


def unified_verify(paths: RepoPaths) -> UnifiedVerifyReport:
    root = paths.root.resolve()
    local_manifest = root / "vendor" / "manifest.json"
    pins_path = root / PROJECT_PINS_REL
    pins_match: bool | None = None
    issues: list[str] = []

    if local_manifest.is_file():
        manifest_report = check_vendor_manifest(root)
        issues = list(manifest_report.issues)
        if pins_path.is_file():
            project_pins = read_project_pins(root)
            if project_pins is None:
                issues.append("project pins file is unreadable")
                pins_match = False
            else:
                source_manifest = load_manifest(local_manifest)
                pins_match = project_pins_match(source_manifest, project_pins)
                if not pins_match:
                    issues.append("project .hive/upstream-pins.json drift from source manifest")
                else:
                    overlay_issues = _verify_unified_overlays(root, manifest=project_pins)
                    if overlay_issues:
                        pins_match = False
                        issues.extend(overlay_issues)
        ok = manifest_report.ok and (pins_match is not False)
    elif pins_path.is_file():
        project_pins = read_project_pins(root)
        if project_pins is None:
            manifest_report = VendorManifestReport(
                ok=False,
                manifest_path=PROJECT_PINS_REL,
                issues=["project pins file is unreadable"],
            )
            pins_match = False
            issues = list(manifest_report.issues)
        else:
            manifest_report = validate_project_pins(project_pins)
            pins_match = manifest_report.ok
            issues = list(manifest_report.issues)
            try:
                packaged = load_manifest(packaged_manifest_path())
                if pins_match and not project_pins_match(packaged, project_pins):
                    pins_match = False
                    issues.append("project .hive/upstream-pins.json drift from hive-planner manifest")
                overlay_issues = _verify_unified_overlays(root, manifest=packaged)
                if overlay_issues:
                    pins_match = False
                    issues.extend(overlay_issues)
            except VendorSyncError:
                overlay_issues = _verify_unified_overlays(root, manifest=project_pins)
                if overlay_issues:
                    pins_match = False
                    issues.extend(overlay_issues)
        ok = pins_match is True
    else:
        manifest_report = check_vendor_manifest(root)
        issues = list(manifest_report.issues)
        ok = manifest_report.ok

    return UnifiedVerifyReport(
        ok=ok,
        manifest=manifest_report,
        project_pins_path=pins_path.as_posix() if pins_path.is_file() else None,
        pins_match=pins_match,
        issues=issues,
    )


def vendor_sync_check(repo_root: Path) -> VendorManifestReport:
    report = check_vendor_manifest(repo_root)
    if report.issues:
        report.ok = False
    return report


def _run_git(args: list[str], *, cwd: Path | None = None) -> None:
    try:
        subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise VendorSyncError(f"git {' '.join(args)} failed: {detail}") from exc
    except FileNotFoundError as exc:
        raise VendorSyncError("git is required for vendor-sync --apply") from exc


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return

    def _on_rm_error(_func, p: str, _exc_info) -> None:
        os.chmod(p, stat.S_IWRITE)
        if os.path.isdir(p):
            shutil.rmtree(p, onerror=_on_rm_error)
        else:
            os.unlink(p)

    if path.is_dir():
        shutil.rmtree(path, onerror=_on_rm_error)
    else:
        path.unlink()


def _strip_vcs_metadata(path: Path) -> None:
    git_dir = path / ".git"
    if git_dir.exists():
        _remove_tree(git_dir)


def _import_spec_kit(repo_root: Path, block: dict) -> None:
    upstream = str(block.get("upstream", "")).strip()
    ref = str(block.get("ref", "")).strip()
    rel_path = str(block.get("path", "")).strip()
    if not upstream or not ref or not rel_path:
        raise VendorSyncError("spec_kit block missing upstream, ref, or path")
    dest = repo_root / rel_path
    if dest.exists():
        _remove_tree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run_git(
        [
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--no-checkout",
            upstream,
            str(dest),
        ]
    )
    _run_git(["fetch", "--depth", "1", "origin", ref], cwd=dest)
    _run_git(["checkout", "FETCH_HEAD"], cwd=dest)
    _strip_vcs_metadata(dest)


def _import_continual_learning(repo_root: Path, block: dict) -> None:
    upstream = str(block.get("upstream", "")).strip()
    ref = str(block.get("ref", "")).strip()
    rel_path = str(block.get("path", "")).strip()
    subtree = str(block.get("subtree", "continual-learning")).strip()
    if not upstream or not ref or not rel_path:
        raise VendorSyncError("continual_learning block missing upstream, ref, or path")
    dest = repo_root / rel_path
    if dest.exists():
        _remove_tree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_root = repo_root / ".vendor_import_tmp"
    tmp_clone = tmp_root / "plugins"
    if tmp_root.exists():
        _remove_tree(tmp_root)
    tmp_root.mkdir(parents=True, exist_ok=True)
    try:
        _run_git(
            [
                "clone",
                "--depth",
                "1",
                "--filter=blob:none",
                "--sparse",
                "--no-checkout",
                upstream,
                str(tmp_clone),
            ]
        )
        _run_git(["sparse-checkout", "set", subtree], cwd=tmp_clone)
        _run_git(["fetch", "--depth", "1", "origin", ref], cwd=tmp_clone)
        _run_git(["checkout", "FETCH_HEAD"], cwd=tmp_clone)
        plugin_src = tmp_clone / subtree
        if not plugin_src.is_dir():
            raise VendorSyncError(f"subtree {subtree!r} not found after sparse checkout")
        shutil.move(str(plugin_src), str(dest))
    finally:
        if tmp_root.exists():
            _remove_tree(tmp_root)


def import_vendors(repo_root: Path, manifest: dict) -> list[str]:
    """Import pinned upstream trees into vendor paths. Returns imported paths."""
    imported: list[str] = []
    for key in COMPONENT_KEYS:
        block = manifest.get(key)
        if not isinstance(block, dict):
            continue
        ref = str(block.get("ref", "")).strip()
        if ref in PLACEHOLDER_REFS:
            raise VendorSyncError(f"{key}.ref must be pinned before import")
        if key == "spec_kit":
            _import_spec_kit(repo_root, block)
        elif key == "continual_learning":
            _import_continual_learning(repo_root, block)
        rel_path = str(block.get("path", "")).strip()
        if rel_path:
            imported.append(rel_path)
    return imported


def vendor_sync_apply(repo_root: Path) -> VendorManifestReport:
    """Validate manifest, import pinned upstream trees, re-validate."""
    root = repo_root.resolve()
    manifest_path = resolve_manifest_path(root)
    manifest = load_manifest(manifest_path)
    report = validate_manifest_data(manifest, manifest_path=manifest_path, repo_root=root)
    if not report.ok:
        return report
    if any(not c.ref_pinned for c in report.components):
        report.issues.append("vendor-sync --apply: pin refs in vendor/manifest.json before import")
        report.ok = False
        return report
    try:
        imported = import_vendors(root, manifest)
    except VendorSyncError as exc:
        report.issues.append(str(exc))
        report.ok = False
        return report
    if imported:
        report.issues.append(f"imported: {', '.join(imported)}")
    return validate_manifest_data(manifest, manifest_path=manifest_path, repo_root=root)


def write_unified_vendor_pins(
    source_root: Path,
    target: Path,
    *,
    force: bool = False,
    written: list[str] | None = None,
    warnings: list[str] | None = None,
) -> bool:
    try:
        manifest_path = resolve_manifest_path(source_root)
        manifest = load_manifest(manifest_path)
    except VendorSyncError as exc:
        if warnings is not None:
            warnings.append(str(exc))
        return False
    write_project_pins(target, manifest, force=force)
    if written is not None:
        rel = PROJECT_PINS_REL
        if rel not in written:
            written.append(rel)
    return True


def _spec_kit_patch_rev(manifest: dict) -> str:
    block = manifest.get("spec_kit")
    if isinstance(block, dict):
        return str(block.get("hive_patch_rev", "")).strip()
    return ""


def _continual_learning_patch_rev(manifest: dict) -> str:
    block = manifest.get("continual_learning")
    if isinstance(block, dict):
        return str(block.get("hive_patch_rev", "")).strip()
    return ""


def _read_component_overlay_rev(target: Path, overlay_rel: str) -> str | None:
    marker = target / overlay_rel / OVERLAY_REV_FILE
    if not marker.is_file():
        return None
    try:
        return marker.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _read_overlay_patch_rev(target: Path) -> str | None:
    return _read_component_overlay_rev(target, SPEC_KIT_OVERLAY_REL)


def _write_component_overlay_rev(target: Path, overlay_rel: str, patch_rev: str) -> None:
    if not patch_rev:
        return
    marker = target / overlay_rel / OVERLAY_REV_FILE
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(patch_rev + "\n", encoding="utf-8")


def _write_overlay_patch_rev(target: Path, patch_rev: str) -> None:
    _write_component_overlay_rev(target, SPEC_KIT_OVERLAY_REL, patch_rev)


def deploy_spec_kit_overlay(
    source_root: Path,
    target: Path,
    *,
    force: bool = False,
    written: list[str] | None = None,
    warnings: list[str] | None = None,
) -> None:
    try:
        overlay_root = resolve_spec_kit_overlay_path(source_root)
    except VendorSyncError as exc:
        if warnings is not None:
            warnings.append(str(exc))
        return
    manifest: dict | None = None
    patch_rev = ""
    try:
        manifest = load_manifest(resolve_manifest_path(source_root))
        patch_rev = _spec_kit_patch_rev(manifest)
    except VendorSyncError:
        pass
    target = target.resolve()
    target_pins = read_project_pins(target)
    if target_pins:
        pins_rev = _spec_kit_patch_rev(target_pins)
        if pins_rev:
            patch_rev = pins_rev
    dest_root = target / SPEC_KIT_OVERLAY_REL
    overlay_force = force
    if not overlay_force and patch_rev:
        deployed_rev = _read_overlay_patch_rev(target)
        if deployed_rev != patch_rev:
            overlay_force = True
    for src in sorted(overlay_root.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(overlay_root)
        dest = dest_root / rel
        if dest.exists() and not overlay_force:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        if written is not None:
            rel_dest = dest.relative_to(target).as_posix()
            if rel_dest not in written:
                written.append(rel_dest)
    if patch_rev:
        _write_overlay_patch_rev(target, patch_rev)
        if written is not None:
            rel_marker = f"{SPEC_KIT_OVERLAY_REL}/{OVERLAY_REV_FILE}"
            if rel_marker not in written:
                written.append(rel_marker)


def deploy_continual_learning_overlay(
    source_root: Path,
    target: Path,
    *,
    force: bool = False,
    written: list[str] | None = None,
    warnings: list[str] | None = None,
) -> None:
    try:
        overlay_root = resolve_continual_learning_overlay_path(source_root)
    except VendorSyncError as exc:
        if warnings is not None:
            warnings.append(str(exc))
        return
    manifest: dict | None = None
    patch_rev = ""
    try:
        manifest = load_manifest(resolve_manifest_path(source_root))
        patch_rev = _continual_learning_patch_rev(manifest)
    except VendorSyncError:
        pass
    target = target.resolve()
    target_pins = read_project_pins(target)
    if target_pins:
        pins_rev = _continual_learning_patch_rev(target_pins)
        if pins_rev:
            patch_rev = pins_rev
    dest_root = target / CL_OVERLAY_REL
    overlay_force = force
    if not overlay_force and patch_rev:
        deployed_rev = _read_component_overlay_rev(target, CL_OVERLAY_REL)
        if deployed_rev != patch_rev:
            overlay_force = True
    for src in sorted(overlay_root.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(overlay_root)
        dest = dest_root / rel
        if dest.exists() and not overlay_force:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        if written is not None:
            rel_dest = dest.relative_to(target).as_posix()
            if rel_dest not in written:
                written.append(rel_dest)
    if patch_rev:
        _write_component_overlay_rev(target, CL_OVERLAY_REL, patch_rev)
        if written is not None:
            rel_marker = f"{CL_OVERLAY_REL}/{OVERLAY_REV_FILE}"
            if rel_marker not in written:
                written.append(rel_marker)


def deploy_unified_vendor_artifacts(
    source_root: Path,
    target: Path,
    *,
    force: bool = False,
    written: list[str] | None = None,
    warnings: list[str] | None = None,
    cl_runtime: str | None = None,
) -> None:
    from hive_planner.cl_runtime import (
        CL_RUNTIME_CURSOR,
        deploy_headless_cl_artifacts,
        normalize_cl_runtime,
        requires_cursor_plugin,
        set_project_cl_runtime,
    )

    runtime = normalize_cl_runtime(cl_runtime or CL_RUNTIME_CURSOR)
    if not write_unified_vendor_pins(
        source_root,
        target,
        force=force,
        written=written,
        warnings=warnings,
    ):
        return
    deploy_spec_kit_overlay(
        source_root,
        target,
        force=force,
        written=written,
        warnings=warnings,
    )
    if requires_cursor_plugin(runtime):
        deploy_continual_learning_overlay(
            source_root,
            target,
            force=force,
            written=written,
            warnings=warnings,
        )
    else:
        deploy_headless_cl_artifacts(target, runtime, force=force, written=written)
        from hive_planner.agent_handoff import MARKETPLACE_CL_REL
        from hive_planner.cl_migration import marketplace_plugin_tree_present

        if marketplace_plugin_tree_present(target):
            message = (
                f"Cursor CL plugin tree still present at {MARKETPLACE_CL_REL}/ — "
                "remove manually or switch to cl-runtime cursor and re-deploy."
            )
            if warnings is not None:
                warnings.append(message)
        hive_overlay = target / CL_OVERLAY_REL
        if hive_overlay.is_dir():
            message = (
                f"Cursor hive-continual-learning overlay still present at {CL_OVERLAY_REL}/ — "
                "safe to remove for headless runtime."
            )
            if warnings is not None:
                warnings.append(message)
        try:
            set_project_cl_runtime(target, runtime)
            if written is not None and ".hive/project.json" not in written:
                written.append(".hive/project.json")
        except ValueError:
            if warnings is not None:
                warnings.append("Could not update .hive/project.json with cl_runtime — bootstrap profile missing")


def ci_unified_vendor_step(
    paths: RepoPaths,
    *,
    hive_source: bool,
    require_pins: bool = False,
) -> tuple[bool, str]:
    root = paths.root.resolve()
    if hive_source:
        report = check_vendor_manifest(root)
        if not report.ok:
            return False, f"manifest invalid: {'; '.join(report.issues)}"
        unpinned = [c.name for c in report.components if not c.ref_pinned]
        if unpinned:
            return True, f"manifest ok (refs unpinned: {', '.join(unpinned)} — Task 3)"
        missing = [c.path for c in report.components if not c.present]
        if missing:
            return False, f"vendor paths missing: {', '.join(missing)}"
        return True, "manifest ok, vendor paths present"

    pins = read_project_pins(root)
    if pins is None:
        if require_pins:
            return False, "missing .hive/upstream-pins.json (required for unified handoff)"
        return True, "skipped (no .hive/upstream-pins.json)"
    local_manifest = root / "vendor" / "manifest.json"
    if local_manifest.is_file():
        source_manifest = load_manifest(local_manifest)
        if not project_pins_match(source_manifest, pins):
            return False, "project pins drift from source manifest"
        overlay_issues = _verify_unified_overlays(root, manifest=pins)
        if overlay_issues:
            return False, "; ".join(overlay_issues)
        return True, "project pins and unified overlays ok"
    pin_report = validate_project_pins(pins)
    if not pin_report.ok:
        return False, f"project pins invalid: {'; '.join(pin_report.issues)}"
    try:
        packaged = load_manifest(packaged_manifest_path())
    except VendorSyncError:
        overlay_issues = _verify_unified_overlays(root, manifest=pins)
        if overlay_issues:
            return False, "; ".join(overlay_issues)
        return True, "project pins valid (packaged manifest unavailable)"
    if not project_pins_match(packaged, pins):
        return False, "project pins drift from hive-planner manifest (re-run deploy handoff)"
    overlay_issues = _verify_unified_overlays(root, manifest=packaged)
    if overlay_issues:
        return False, "; ".join(overlay_issues)
    return True, "project pins and unified overlays ok"

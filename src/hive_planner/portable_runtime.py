"""Portable / frozen runtime — self-contained Spec Kit + Continual Learning deploy."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

PORTABLE_RUNTIME_MARKER = ".hive/portable-runtime.json"
PORTABLE_RUNTIME_SCHEMA = "hive-portable-runtime/v1"


@dataclass
class PortableRuntimeReport:
    ok: bool
    bundled_ok: bool
    deployed_ok: bool
    detail: str
    missing: list[str] = field(default_factory=list)
    files_written: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "bundled_ok": self.bundled_ok,
            "deployed_ok": self.deployed_ok,
            "detail": self.detail,
            "missing": self.missing,
            "files_written": self.files_written,
            "warnings": self.warnings,
        }


def _required_deploy_paths() -> tuple[str, ...]:
    from hive_planner.vendor_sync import CL_OVERLAY_REL, PROJECT_PINS_REL, SPEC_KIT_OVERLAY_REL

    return (
        PROJECT_PINS_REL,
        f"{SPEC_KIT_OVERLAY_REL}/WORKFLOW.md",
        f"{SPEC_KIT_OVERLAY_REL}/templates/spec-template.md",
        f"{CL_OVERLAY_REL}/WORKFLOW.md",
        f"{CL_OVERLAY_REL}/skills/continual-learning/SKILL.md",
        f"{CL_OVERLAY_REL}/.cursor-plugin/plugin.json",
    )


def verify_bundled_templates() -> tuple[bool, list[str]]:
    """Check packaged vendor_templates inside the frozen/dev bundle."""
    from hive_planner.vendor_sync import (
        _continual_learning_overlay_complete,
        _spec_kit_overlay_complete,
        packaged_continual_learning_overlay_path,
        packaged_manifest_path,
        packaged_spec_kit_overlay_path,
    )

    missing: list[str] = []
    manifest = packaged_manifest_path()
    if not manifest.is_file():
        missing.append("vendor_templates/manifest.json")
    spec_kit = packaged_spec_kit_overlay_path()
    if not _spec_kit_overlay_complete(spec_kit):
        missing.append("vendor_templates/spec-kit overlay")
    cl = packaged_continual_learning_overlay_path()
    if not _continual_learning_overlay_complete(cl):
        missing.append("vendor_templates/continual-learning overlay")
    return not missing, missing


def verify_portable_artifacts(app_root: Path) -> tuple[bool, list[str]]:
    """Check deployed Spec Kit + CL files (excluding the portable marker)."""
    root = app_root.resolve()
    missing = [rel for rel in _required_deploy_paths() if not (root / rel).is_file()]
    return not missing, missing


def verify_portable_deploy(app_root: Path) -> tuple[bool, list[str]]:
    root = app_root.resolve()
    ok, missing = verify_portable_artifacts(root)
    marker = root / PORTABLE_RUNTIME_MARKER
    if not marker.is_file():
        missing.append(PORTABLE_RUNTIME_MARKER)
    return not missing, missing


def _write_portable_marker(app_root: Path) -> None:
    from hive_planner import __version__

    root = app_root.resolve()
    path = root / PORTABLE_RUNTIME_MARKER
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": PORTABLE_RUNTIME_SCHEMA,
        "deployed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "hive_planner_version": __version__,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def ensure_portable_runtime(app_root: Path, *, force: bool = False) -> PortableRuntimeReport:
    """Deploy unified Spec Kit + CL overlays beside the portable exe when missing."""
    from hive_planner.runtime_paths import is_portable_runtime
    from hive_planner.vendor_sync import deploy_unified_vendor_artifacts

    if not is_portable_runtime():
        return PortableRuntimeReport(
            ok=False,
            bundled_ok=False,
            deployed_ok=False,
            detail="Not a portable runtime",
        )

    root = app_root.resolve()
    bundled_ok, bundled_missing = verify_bundled_templates()
    if not bundled_ok:
        return PortableRuntimeReport(
            ok=False,
            bundled_ok=False,
            deployed_ok=False,
            detail="Bundled Spec Kit / Continual Learning templates missing from build",
            missing=bundled_missing,
        )

    deployed_ok, deployed_missing = verify_portable_deploy(root)
    written: list[str] = []
    warnings: list[str] = []
    if force or not deployed_ok:
        artifacts_present, _ = verify_portable_artifacts(root)
        deploy_force = force or not artifacts_present
        deploy_unified_vendor_artifacts(
            root,
            root,
            force=deploy_force,
            written=written,
            warnings=warnings,
        )
        artifacts_ok, _artifact_missing = verify_portable_artifacts(root)
        if artifacts_ok:
            _write_portable_marker(root)
        deployed_ok, deployed_missing = verify_portable_deploy(root)

    ok = bundled_ok and deployed_ok
    if ok:
        detail = "Portable runtime ready — Spec Kit + Continual Learning deployed"
    elif not deployed_ok:
        detail = f"Deploy incomplete — missing: {', '.join(deployed_missing)}"
    else:
        detail = "Portable runtime check failed"

    return PortableRuntimeReport(
        ok=ok,
        bundled_ok=bundled_ok,
        deployed_ok=deployed_ok,
        detail=detail,
        missing=deployed_missing if not deployed_ok else [],
        files_written=written,
        warnings=warnings,
    )

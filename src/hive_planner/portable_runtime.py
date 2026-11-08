"""Portable / frozen runtime — self-contained Spec Kit + Continual Learning deploy."""

from __future__ import annotations

import json
import os
import sys
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
        f"{CL_OVERLAY_REL}/hooks/hooks.json",
        f"{CL_OVERLAY_REL}/hooks/continual-learning-stop.py",
        ".cursor/hooks.json",
        ".cursor/hooks/hive_workspace_open.py",
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
        from hive_planner.bootstrap import _copy_cursor_workspace_plugin_hooks

        _copy_cursor_workspace_plugin_hooks(
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


def _tk_marker_usable(folder: Path, marker: str) -> bool:
    path = folder / marker
    try:
        if not path.is_file() or path.stat().st_size <= 0:
            return False
        with path.open("rb") as handle:
            if not handle.read(1):
                return False
        return True
    except OSError:
        return False


def _tk_env_inside_meipass(folder: Path) -> bool:
    if not getattr(sys, "frozen", False):
        return False
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return False
    try:
        folder.resolve().relative_to(Path(meipass).resolve())
    except (OSError, ValueError):
        return False
    return True


def _frozen_tk_dir(key: str) -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return None
    try:
        root = Path(meipass).resolve()
        folder = (root / ("_tcl_data" if key == "TCL_LIBRARY" else "_tk_data")).resolve()
        folder.relative_to(root)
    except (OSError, ValueError):
        return None
    marker = "init.tcl" if key == "TCL_LIBRARY" else "tk.tcl"
    return folder if _tk_marker_usable(folder, marker) else None


def clear_stale_tk_library_env() -> list[str]:
    """Drop TCL_LIBRARY/TK_LIBRARY when they point at an unusable portable tree.

    HivePlannerPortable can leave those variables in the user environment. CPython
    tkinter then looks there first and fails even when Python's own tcl8.6 works.
    Frozen portable keeps a readable bundled tree, or retargets sys._MEIPASS.
    """
    frozen = bool(getattr(sys, "frozen", False))
    dropped: list[str] = []
    for key, marker in (("TCL_LIBRARY", "init.tcl"), ("TK_LIBRARY", "tk.tcl")):
        raw = os.environ.get(key)
        if not raw or "\x00" in raw or raw.startswith(("\\\\", "//")):
            if raw:
                os.environ.pop(key, None)
                dropped.append(key)
            continue
        folder = Path(raw)
        usable = _tk_marker_usable(folder, marker)
        portable = "hiveplannerportable" in raw.replace("\\", "/").casefold()
        if frozen:
            keep = usable and _tk_env_inside_meipass(folder)
        else:
            keep = usable and not portable
        if keep:
            continue
        os.environ.pop(key, None)
        dropped.append(key)
        if frozen:
            fallback = _frozen_tk_dir(key)
            if fallback is not None:
                os.environ[key] = str(fallback)
    return dropped

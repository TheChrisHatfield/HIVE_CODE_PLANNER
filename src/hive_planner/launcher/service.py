from __future__ import annotations

import importlib.metadata
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from hive_planner.bootstrap import BootstrapError, init_project
from hive_planner.ci_handoff import run_ci_check
from hive_planner.config import RepoPaths, is_repo_root
from hive_planner.launcher.config import LauncherConfig
from hive_planner.map_sync import sync_impact_maps
from hive_planner.project_profile import resolve_project_profile
from hive_planner.spec_drift import parse_active_feature


@dataclass
class SetupStatus:
    python_ok: bool
    python_version: str
    hive_root: str
    hive_root_ok: bool
    hive_installed: bool
    hive_version: str
    git_available: bool
    onboarding_complete: bool

    def to_dict(self) -> dict:
        return {
            "python_ok": self.python_ok,
            "python_version": self.python_version,
            "hive_root": self.hive_root,
            "hive_root_ok": self.hive_root_ok,
            "hive_installed": self.hive_installed,
            "hive_version": self.hive_version,
            "git_available": self.git_available,
            "onboarding_complete": self.onboarding_complete,
        }


@dataclass
class InstallResult:
    ok: bool
    detail: str
    output: str = ""


@dataclass
class ProjectSummary:
    root: str
    ok: bool
    project_name: str
    active_feature: str | None
    bootstrap_profile: str | None = None
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "ok": self.ok,
            "project_name": self.project_name,
            "active_feature": self.active_feature,
            "bootstrap_profile": self.bootstrap_profile,
            "detail": self.detail,
        }


def _python_command(config: LauncherConfig) -> list[str]:
    raw = config.python_executable.strip() or "py -3.11"
    parts = shlex.split(raw, posix=(sys.platform != "win32"))
    return [part.strip('"').strip("'") for part in parts]


def get_setup_status(config: LauncherConfig) -> SetupStatus:
    hive_root = config.normalized_hive_root()
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    hive_version = ""
    hive_installed = False
    try:
        hive_version = importlib.metadata.version("hive-planner")
        hive_installed = True
    except importlib.metadata.PackageNotFoundError:
        pass
    return SetupStatus(
        python_ok=sys.version_info >= (3, 10),
        python_version=version,
        hive_root=str(hive_root),
        hive_root_ok=hive_root.is_dir() and (hive_root / "pyproject.toml").is_file(),
        hive_installed=hive_installed,
        hive_version=hive_version,
        git_available=shutil.which("git") is not None,
        onboarding_complete=config.onboarding_complete,
    )


def run_install(config: LauncherConfig, *, extras: str = "dev") -> InstallResult:
    hive_root = config.normalized_hive_root()
    if not hive_root.is_dir():
        return InstallResult(False, f"Hive root not found: {hive_root}")
    cmd = _python_command(config) + ["-m", "pip", "install", "-e", f".[{extras}]"]
    try:
        proc = subprocess.run(
            cmd,
            cwd=hive_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return InstallResult(False, str(exc))
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        tail = output.strip().splitlines()[-1] if output.strip() else "pip install failed"
        return InstallResult(False, tail, output=output[-4000:])
    version = ""
    try:
        version = importlib.metadata.version("hive-planner")
    except importlib.metadata.PackageNotFoundError:
        pass
    detail = f"Installed hive-planner {version}" if version else "Install complete"
    return InstallResult(True, detail, output=output[-4000:])


def summarize_project(project_root: Path) -> ProjectSummary:
    root = project_root.resolve()
    if not root.is_dir():
        return ProjectSummary(str(root), False, root.name, None, None, "Directory not found")
    paths = RepoPaths(root=root)
    if not is_repo_root(root) and not (root / "START_HERE.md").is_file():
        return ProjectSummary(
            str(root), False, root.name, None, None, "Not a Hive project (missing START_HERE.md)"
        )
    feature = parse_active_feature(paths)
    meta = resolve_project_profile(root)
    profile = meta.bootstrap_profile if meta else None
    name = meta.project_name if meta else root.name
    return ProjectSummary(str(root), True, name, feature, profile, "ok")


def run_project_ci_check(project_root: Path) -> dict:
    paths = RepoPaths(root=project_root.resolve())
    report = run_ci_check(paths)
    return report.to_dict()


def run_project_map_sync(project_root: Path, *, dry_run: bool = False) -> dict:
    paths = RepoPaths(root=project_root.resolve())
    report = sync_impact_maps(paths, dry_run=dry_run)
    return {
        "dry_run": dry_run,
        "project_added": sorted(report.project_added),
        "test_added": sorted(report.test_added),
        "project_updated": sorted(report.project_updated),
        "test_updated": sorted(report.test_updated),
    }


def run_project_init(
    config: LauncherConfig,
    *,
    target: Path,
    name: str | None,
    profile: str,
    git_init: bool,
    force: bool,
) -> dict:
    hive_root = config.normalized_hive_root()
    paths = RepoPaths(root=hive_root)
    try:
        result = init_project(
            paths,
            target,
            name=name,
            force=force,
            profile=profile,
            git_init=git_init,
        )
    except BootstrapError as exc:
        return {"ok": False, "error": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    payload = result.to_dict()
    payload["ok"] = True
    return payload


def open_path_in_explorer(path: Path) -> dict:
    target = path.resolve()
    if not target.exists():
        return {"ok": False, "error": "Path does not exist"}
    if sys.platform == "win32":
        subprocess.Popen(["explorer", str(target)], shell=False)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target)])
    return {"ok": True, "path": str(target)}


def find_cursor_executable() -> str | None:
    found = shutil.which("cursor")
    if found:
        return found
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            for rel in (
                "Programs/cursor/Cursor.exe",
                "Programs/Cursor/Cursor.exe",
            ):
                candidate = Path(local) / rel
                if candidate.is_file():
                    return str(candidate)
    elif sys.platform == "darwin":
        candidate = Path("/Applications/Cursor.app/Contents/MacOS/Cursor")
        if candidate.is_file():
            return str(candidate)
    return None


def open_in_cursor(project_root: Path) -> dict:
    target = project_root.resolve()
    if not target.is_dir():
        return {"ok": False, "error": "Directory not found"}
    summary = summarize_project(target)
    if not summary.ok:
        return {"ok": False, "error": summary.detail}
    cursor_exe = find_cursor_executable()
    if not cursor_exe:
        return {
            "ok": False,
            "error": "Cursor not found. Install Cursor or add the cursor CLI to PATH.",
        }
    try:
        subprocess.Popen([cursor_exe, str(target)], cwd=str(target), shell=False)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "path": str(target),
        "cursor": cursor_exe,
        "bootstrap_profile": summary.bootstrap_profile,
    }

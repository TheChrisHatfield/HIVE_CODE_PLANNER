from __future__ import annotations

import importlib.metadata
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
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
class PythonInstallation:
    command: str
    version: str
    executable: str
    supported: bool

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "version": self.version,
            "executable": self.executable,
            "supported": self.supported,
        }


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


def _hidden_subprocess_kwargs() -> dict:
    """Prevent console/PowerShell windows from flashing on Windows."""
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


def _run_hidden(args: list[str], **kwargs):
    return subprocess.run(args, **_hidden_subprocess_kwargs(), **kwargs)


_probe_cache: dict[str, PythonInstallation | None] = {}


def clear_python_probe_cache() -> None:
    _probe_cache.clear()


def _command_label(command: list[str]) -> str:
    if len(command) == 1:
        return command[0]
    if sys.platform == "win32":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def _version_supported(version: str) -> bool:
    parts = version.split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return False
    return (major, minor) >= (3, 10)


def probe_python_command(command: list[str], *, use_cache: bool = True) -> PythonInstallation | None:
    cache_key = _command_label(command).lower()
    if use_cache and cache_key in _probe_cache:
        return _probe_cache[cache_key]
    try:
        proc = _run_hidden(
            command
            + [
                "-c",
                "import sys; print('.'.join(map(str, sys.version_info[:3]))); print(sys.executable)",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        result = None
    else:
        if proc.returncode != 0:
            result = None
        else:
            lines = (proc.stdout or "").strip().splitlines()
            if len(lines) < 2:
                result = None
            else:
                version = lines[0].strip()
                executable = lines[1].strip()
                if not version or not executable:
                    result = None
                else:
                    result = PythonInstallation(
                        command=_command_label(command),
                        version=version,
                        executable=executable,
                        supported=_version_supported(version),
                    )
    if use_cache:
        _probe_cache[cache_key] = result
    return result


def _py_launcher_commands() -> list[list[str]]:
    if sys.platform != "win32" or not shutil.which("py"):
        return []
    try:
        proc = _run_hidden(["py", "-0p"], capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    commands: list[list[str]] = []
    for line in (proc.stdout or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("-V:"):
            continue
        rest = stripped[3:].strip()
        if not rest:
            continue
        tag = rest.split()[0].rstrip("*")
        path = rest.split(None, 1)[1].strip() if len(rest.split()) > 1 else ""
        path = path.lstrip("*").strip()
        if path and Path(path).is_file():
            commands.append([path])
        if tag:
            commands.append(["py", f"-{tag}"])
    return commands


def _well_known_python_commands() -> list[list[str]]:
    commands: list[list[str]] = []
    if sys.platform == "win32":
        roots: list[Path] = []
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            roots.append(Path(local) / "Programs" / "Python")
        for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
            env_val = os.environ.get(env_name, "")
            if env_val:
                roots.append(Path(env_val))
        for root in roots:
            if not root.is_dir():
                continue
            for pattern in ("Python3*", "Python\\Python3*"):
                for match in root.glob(pattern):
                    exe = match / "python.exe" if match.is_dir() else None
                    if exe and exe.is_file():
                        commands.append([str(exe)])
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            commands.append([found])
    return commands


def _dedupe_probe_commands(commands: list[list[str]]) -> list[list[str]]:
    seen: set[str] = set()
    unique: list[list[str]] = []
    for command in commands:
        key = _command_label(command).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(command)
    return unique


def _collect_probe_candidates() -> list[list[str]]:
    commands: list[list[str]] = [[sys.executable]]
    commands.extend(_py_launcher_commands())
    py_path = shutil.which("py")
    if py_path:
        commands.append([py_path])
    commands.extend(_well_known_python_commands())
    return _dedupe_probe_commands(commands)


def discover_python_installations(
    on_progress: Callable[[int, int, str], None] | None = None,
) -> list[PythonInstallation]:
    if on_progress:
        on_progress(0, 1, "Collecting candidates")
    clear_python_probe_cache()
    candidates = _collect_probe_candidates()
    total = len(candidates) or 1
    seen: set[str] = set()
    found: list[PythonInstallation] = []

    for index, command in enumerate(candidates):
        if on_progress:
            on_progress(index, total, _command_label(command))
        inst = probe_python_command(command, use_cache=True)
        if not inst:
            continue
        try:
            key = str(Path(inst.executable).resolve()).lower()
        except OSError:
            key = inst.executable.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(inst)

    if on_progress:
        on_progress(total, total, "Done")

    def sort_key(item: PythonInstallation) -> tuple:
        parts = item.version.split(".")
        try:
            nums = tuple(int(p) for p in parts[:3])
        except ValueError:
            nums = (0, 0, 0)
        while len(nums) < 3:
            nums = (*nums, 0)
        return (0 if item.supported else 1, -nums[0], -nums[1], -nums[2])

    found.sort(key=sort_key)
    return found


def format_python_scan_report(installations: list[PythonInstallation]) -> str:
    if not installations:
        return (
            "No Python installations found.\n\n"
            "Install Python 3.10+ from python.org or the Microsoft Store, then scan again."
        )
    lines = ["Found Python installations:", ""]
    for inst in installations:
        status = "OK" if inst.supported else "too old"
        lines.append(f"{status:8}  {inst.version}  —  {inst.command}")
        lines.append(f"          {inst.executable}")
        lines.append("")
    lines.append("Hive Planner requires Python 3.10 or newer.")
    return "\n".join(lines).rstrip()


def get_setup_status(config: LauncherConfig) -> SetupStatus:
    hive_root = config.normalized_hive_root()
    runtime_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    configured = probe_python_command(_python_command(config))
    if configured:
        python_ok = configured.supported
        python_version = f"{configured.version}  ({configured.command})"
    else:
        python_ok = sys.version_info >= (3, 10)
        python_version = f"{runtime_version}  (launcher runtime)"
    hive_version = ""
    hive_installed = False
    try:
        hive_version = importlib.metadata.version("hive-planner")
        hive_installed = True
    except importlib.metadata.PackageNotFoundError:
        pass
    return SetupStatus(
        python_ok=python_ok,
        python_version=python_version,
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
    target = project_root.resolve()
    summary = summarize_project(target)
    if not summary.ok:
        return {"ok": False, "error": summary.detail}
    paths = RepoPaths(root=target)
    report = run_ci_check(paths)
    return report.to_dict()


def run_project_map_sync(project_root: Path, *, dry_run: bool = False) -> dict:
    target = project_root.resolve()
    summary = summarize_project(target)
    if not summary.ok:
        return {"ok": False, "error": summary.detail}
    paths = RepoPaths(root=target)
    report = sync_impact_maps(paths, dry_run=dry_run)
    return {
        "ok": True,
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

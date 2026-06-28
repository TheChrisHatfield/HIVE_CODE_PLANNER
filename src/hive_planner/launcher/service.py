from __future__ import annotations

import importlib.metadata
import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from hive_planner.bootstrap import BootstrapError, init_project
from hive_planner.ci_handoff import run_ci_check
from hive_planner.config import SUPPORTED_EXTENSIONS, RepoPaths, is_repo_root, validate_feature_id
from hive_planner.emitter import emit_cartridge
from hive_planner.launcher.config import LauncherConfig
from hive_planner.map_sync import sync_impact_maps
from hive_planner.pipeline import ingest
from hive_planner.project_profile import read_project_profile
from hive_planner.spec_drift import parse_active_feature, repair_agents_active_feature


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
    if use_cache and result is not None:
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


def auto_complete_onboarding_if_ready(config: LauncherConfig) -> bool:
    """Mark onboarding done when Python, hive root, and package are already OK."""
    if config.onboarding_complete:
        return False
    status = get_setup_status(config)
    if status.python_ok and status.hive_root_ok and status.hive_installed:
        config.onboarding_complete = True
        return True
    return False


def run_install(config: LauncherConfig, *, extras: str = "dev") -> InstallResult:
    hive_root = config.normalized_hive_root()
    if not hive_root.is_dir():
        return InstallResult(False, f"Hive root not found: {hive_root}")
    cmd = _python_command(config) + ["-m", "pip", "install", "-e", f".[{extras}]"]
    try:
        proc = _run_hidden(
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
    clear_python_probe_cache()
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
    meta = read_project_profile(root)
    profile = meta.bootstrap_profile if meta else None
    name = meta.project_name if meta else root.name
    return ProjectSummary(str(root), True, name, feature, profile, "ok")


@dataclass
class CursorWorkspace:
    path: str
    name: str
    location: str
    exists: bool
    hive_ready: bool
    has_cursor_dir: bool
    has_git: bool
    entry_kind: str = "folder"

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "name": self.name,
            "location": self.location,
            "exists": self.exists,
            "hive_ready": self.hive_ready,
            "has_cursor_dir": self.has_cursor_dir,
            "has_git": self.has_git,
            "entry_kind": self.entry_kind,
        }


def file_uri_to_path(uri: str) -> str | None:
    raw = str(uri or "").strip()
    if not raw.startswith("file://"):
        return None
    parsed = urlparse(raw)
    path = unquote(parsed.path)
    if sys.platform == "win32" and path.startswith("/") and len(path) > 2 and path[2] == ":":
        path = path[1:]
    return path or None


def is_code_workspace_file(path: Path) -> bool:
    return path.suffix.lower() == ".code-workspace"


def read_code_workspace_folders(workspace_file: Path) -> list[Path]:
    try:
        data = json.loads(workspace_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    folders: list[Path] = []
    for entry in data.get("folders") or []:
        rel = entry.get("path") if isinstance(entry, dict) else entry
        if not rel:
            continue
        rel_text = str(rel).strip()
        try:
            if rel_text in (".", "./"):
                folders.append(workspace_file.parent.resolve())
            else:
                folders.append((workspace_file.parent / rel_text).resolve())
        except OSError:
            continue
    return folders


def list_workspace_roots(path: Path) -> list[Path]:
    if is_code_workspace_file(path):
        if not path.is_file():
            return []
        return read_code_workspace_folders(path)
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    return [resolved] if resolved.is_dir() else []


def _filter_workspace_roots(link_path: Path, roots: list[Path]) -> list[Path]:
    if not roots:
        return []
    workspace_parent = link_path.parent.resolve() if is_code_workspace_file(link_path) else None
    filtered: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            resolved = root.resolve()
        except OSError:
            continue
        key = str(resolved).lower()
        if key in seen:
            continue
        if workspace_parent is not None and len(roots) > 1 and resolved == workspace_parent:
            continue
        seen.add(key)
        filtered.append(resolved)
    return filtered or roots


def _hive_root_score(path: Path) -> int:
    if not path.is_dir():
        return -1
    score = 0
    if (path / "START_HERE.md").is_file():
        score += 10
    if (path / "pyproject.toml").is_file():
        score += 8
    if (path / ".hive" / "project.json").is_file():
        score += 4
    if (path / "src").is_dir():
        score += 2
    if (path / "AGENTS.md").is_file():
        score += 1
    return score


def _collect_hive_root_candidates(roots: list[Path]) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()

    def add(folder: Path) -> None:
        try:
            resolved = folder.resolve()
        except OSError:
            return
        key = str(resolved).lower()
        if key in seen:
            return
        seen.add(key)
        candidates.append(resolved)

    for root in roots:
        if not root.is_dir():
            continue
        add(root)
        try:
            for child in root.iterdir():
                if child.is_dir() and (child / "START_HERE.md").is_file():
                    add(child)
        except OSError:
            continue
    return candidates


def _best_hive_root(candidates: list[Path]) -> Path | None:
    if not candidates:
        return None
    scored = [(path, _hive_root_score(path)) for path in candidates]
    viable = [(path, score) for path, score in scored if score > 0]
    if viable:
        viable.sort(key=lambda item: (item[1], len(str(item[0]))), reverse=True)
        return viable[0][0]
    for path in candidates:
        if path.is_dir():
            return path
    return candidates[0]


def _resolved_workspace_roots(link_path: Path) -> list[Path]:
    return _filter_workspace_roots(link_path, list_workspace_roots(link_path))


def pick_hive_bootstrap_target(link_path: Path) -> Path | None:
    """Pick the best folder to add Hive planning files for a linked workspace."""
    roots = _resolved_workspace_roots(link_path)
    if not roots:
        return workspace_primary_folder(link_path)

    for root in roots:
        if not root.is_dir():
            continue
        try:
            if not any(root.iterdir()):
                return root
        except OSError:
            continue

    best = _best_hive_root(_collect_hive_root_candidates(roots))
    if best is not None and _hive_root_score(best) > 0:
        return best

    for root in roots:
        if not root.is_dir():
            continue
        if (root / ".cursor").is_dir() or (root / ".git").exists():
            return root

    for root in roots:
        if root.is_dir():
            return root
    return roots[0]


def workspace_primary_folder(path: Path) -> Path | None:
    if is_code_workspace_file(path):
        if not path.is_file():
            return None
        roots = _resolved_workspace_roots(path)
        if not roots:
            try:
                return path.parent.resolve()
            except OSError:
                return path.parent
        best = _best_hive_root(_collect_hive_root_candidates(roots))
        if best is not None:
            return best
        for root in roots:
            if root.is_dir():
                return root
        return roots[0]
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    if not resolved.is_dir():
        return None
    if (resolved / "START_HERE.md").is_file():
        return resolved
    nested = _best_hive_root(_collect_hive_root_candidates([resolved]))
    if nested is not None and _hive_root_score(nested) > 0:
        return nested
    return resolved


def resolve_linked_project_root(path: Path) -> Path | None:
    """Folder used for Hive health checks and profile metadata."""
    return workspace_primary_folder(path)


def prepare_linked_project_root(path: Path, *, repair_agents: bool = True):
    from hive_planner.project_profile import resolve_project_integrations
    from hive_planner.spec_drift import AgentsRepairResult, repair_agents_active_feature, repair_handoff_rosetta_navigation

    root = resolve_linked_project_root(path)
    if not root:
        return None, None
    if not repair_agents:
        return root, None
    if not resolve_project_integrations(root).spec_kit_enabled:
        return root, None
    if not (root / "START_HERE.md").is_file() and not is_repo_root(root):
        return root, None
    paths = RepoPaths(root=root)
    repair_handoff_rosetta_navigation(paths)
    repair = repair_agents_active_feature(paths)
    if repair.repaired:
        return root, repair
    return root, None


def summarize_linked_project(link_path: Path, *, repair_agents: bool = True) -> ProjectSummary:
    root, _repair = prepare_linked_project_root(link_path, repair_agents=repair_agents)
    if not root:
        label = link_path.name if link_path else "project"
        return ProjectSummary(str(link_path), False, label, None, None, "Could not resolve project root")
    return summarize_project(root)


def _cursor_state_db_path() -> Path | None:
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        return None
    db = Path(appdata) / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    return db if db.is_file() else None


def _read_cursor_recent_entries() -> list[dict]:
    db = _cursor_state_db_path()
    if not db:
        return []
    try:
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT value FROM ItemTable WHERE key = ?",
            ("history.recentlyOpenedPathsList",),
        ).fetchone()
        conn.close()
    except sqlite3.Error:
        return []
    if not row:
        return []
    raw = row[0]
    text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    entries = data.get("entries")
    return entries if isinstance(entries, list) else []


def _folder_workspace_flags(folder: Path) -> tuple[bool, bool, bool]:
    exists = folder.is_dir()
    if not exists:
        return False, False, False
    hive_ready = is_repo_root(folder) or (folder / "START_HERE.md").is_file()
    has_cursor_dir = (folder / ".cursor").is_dir()
    has_git = (folder / ".git").exists()
    return hive_ready, has_cursor_dir, has_git


def build_cursor_workspace(path: Path, *, entry_kind: str, display_name: str | None = None) -> CursorWorkspace:
    if entry_kind == "workspace" or is_code_workspace_file(path):
        exists = path.is_file()
        location = str(path.parent)
        name = display_name or f"{path.stem} (Workspace)"
        primary = workspace_primary_folder(path) if exists else None
        hive_ready, has_cursor_dir, has_git = (
            _folder_workspace_flags(primary) if primary else (False, False, False)
        )
        resolved = str(path.resolve()) if exists else str(path)
        return CursorWorkspace(
            path=resolved,
            name=name,
            location=location,
            exists=exists,
            hive_ready=hive_ready,
            has_cursor_dir=has_cursor_dir,
            has_git=has_git,
            entry_kind="workspace",
        )

    try:
        resolved_path = path.resolve()
    except OSError:
        resolved_path = path
    exists = resolved_path.is_dir()
    hive_ready, has_cursor_dir, has_git = _folder_workspace_flags(resolved_path)
    return CursorWorkspace(
        path=str(resolved_path),
        name=display_name or resolved_path.name or str(resolved_path),
        location=str(resolved_path.parent),
        exists=exists,
        hive_ready=hive_ready,
        has_cursor_dir=has_cursor_dir,
        has_git=has_git,
        entry_kind="folder",
    )


def classify_workspace(project_root: Path) -> CursorWorkspace:
    path = Path(project_root)
    if is_code_workspace_file(path):
        return build_cursor_workspace(path, entry_kind="workspace")
    return build_cursor_workspace(path, entry_kind="folder")


def _workspace_from_recent_entry(entry: dict) -> CursorWorkspace | None:
    workspace = entry.get("workspace")
    if isinstance(workspace, dict):
        uri = str(workspace.get("configPath") or workspace.get("configURIPath") or "")
        raw_path = file_uri_to_path(uri)
        if not raw_path:
            return None
        path = Path(raw_path)
        return build_cursor_workspace(path, entry_kind="workspace")

    uri = str(entry.get("folderUri") or "")
    raw_path = file_uri_to_path(uri)
    if not raw_path:
        return None
    return build_cursor_workspace(Path(raw_path), entry_kind="folder")


def discover_cursor_workspaces() -> list[CursorWorkspace]:
    """Match Cursor's Recent projects list (history.recentlyOpenedPathsList)."""
    seen: set[str] = set()
    workspaces: list[CursorWorkspace] = []
    for entry in _read_cursor_recent_entries():
        if not isinstance(entry, dict):
            continue
        workspace = _workspace_from_recent_entry(entry)
        if not workspace:
            continue
        key = workspace.path.lower()
        if key in seen:
            continue
        seen.add(key)
        workspaces.append(workspace)
    return workspaces


def is_hive_planner_source_repo(root: Path) -> bool:
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return False
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return False
    return 'name = "hive-planner"' in text


def ci_check_hints(root: Path, report) -> list[str]:
    from hive_planner.ci_handoff import CiCheckReport
    from hive_planner.project_profile import resolve_project_integrations

    if not isinstance(report, CiCheckReport):
        return []
    hints: list[str] = []
    paths = RepoPaths(root=root)
    integrations = resolve_project_integrations(root)
    feature = parse_active_feature(paths)
    failed = {step.name for step in report.steps if not step.ok}
    if integrations.spec_kit_enabled and "handoff-artifacts" in failed and not feature:
        hints.append(
            "Set Active feature in AGENTS.md to a real feature id (e.g. **example-feature**), "
            "or re-bootstrap with Spec Kit enabled."
        )
    if integrations.spec_kit_enabled and "spec-drift" in failed and not feature:
        hints.append("Spec drift stays red until Active feature is set and matching spec/delta files exist.")
    if not is_hive_planner_source_repo(root):
        hints.append(
            "Full roadmap checks apply only to the Hive Planner source repo. "
            "Bootstrapped app/workspace projects skip roadmap-artifacts."
        )
    elif "roadmap-artifacts" in failed:
        hints.append("Roadmap failures mean spec/delta/tasks files are missing for planned features in this repo.")
    return hints


def run_project_ci_check(project_root: Path) -> dict:
    target = project_root.resolve()
    summary = summarize_project(target)
    if not summary.ok:
        return {"ok": False, "error": summary.detail}
    paths = RepoPaths(root=target)
    from hive_planner.spec_drift import repair_handoff_rosetta_navigation

    rosetta_repair = repair_handoff_rosetta_navigation(paths)
    repair = repair_agents_active_feature(paths)
    report = run_ci_check(paths, check_roadmap=is_hive_planner_source_repo(target))
    payload = report.to_dict()
    if rosetta_repair:
        payload["rosetta_repair"] = rosetta_repair
    if repair.repaired:
        payload["repair"] = {"feature": repair.feature, "detail": repair.detail}
    hints = ci_check_hints(target, report)
    if hints:
        payload["hints"] = hints
    return payload


def run_deploy_agent_handoff(project_root: Path, *, hive_planner_root: Path, force: bool = False) -> dict:
    from hive_planner.agent_handoff import validate_unified_handoff
    from hive_planner.bootstrap import BootstrapError, deploy_agent_handoff_scaffold
    from hive_planner.rosetta_nav import DEPLOY_HANDOFF_NAV_LAYERS, ensure_handoff_rosetta_navigation
    from hive_planner.spec_drift import BOOTSTRAP_DEFAULT_FEATURE, repair_agents_active_feature, repair_agents_rosetta_section

    target = project_root.resolve()
    summary = summarize_project(target)
    if not summary.ok:
        return {"ok": False, "error": summary.detail}
    paths = RepoPaths(root=hive_planner_root.resolve())
    try:
        written, warnings = deploy_agent_handoff_scaffold(paths, target, force=force)
    except BootstrapError as exc:
        return {"ok": False, "error": str(exc)}
    target_paths = RepoPaths(root=target)
    repair = repair_agents_active_feature(target_paths)
    rosetta_repair = repair_agents_rosetta_section(target_paths)
    patched = ensure_handoff_rosetta_navigation(
        target_paths,
        BOOTSTRAP_DEFAULT_FEATURE,
        promoted_layers=set(DEPLOY_HANDOFF_NAV_LAYERS),
    )
    handoff = validate_unified_handoff(target)
    payload = {
        "ok": handoff.complete,
        "files_written": written,
        "warnings": warnings,
        "agent_handoff_mode": "unified",
    }
    if not handoff.complete:
        payload["error"] = f"Unified handoff incomplete — missing: {', '.join(handoff.missing)}"
        payload["handoff"] = {
            "mode": handoff.mode,
            "complete": handoff.complete,
            "missing": handoff.missing,
            "spec_kit_enabled": handoff.spec_kit_enabled,
            "continual_learning_enabled": handoff.continual_learning_enabled,
        }
    if repair.repaired:
        payload["repair"] = {"feature": repair.feature, "detail": repair.detail}
    rosetta_details: list[str] = []
    if rosetta_repair.repaired:
        rosetta_details.append(rosetta_repair.detail)
    if patched:
        rosetta_details.append(f"patched navigation in {len(patched)} handoff file(s)")
    if rosetta_details or patched:
        payload["rosetta_repair"] = {
            "detail": "; ".join(rosetta_details) if rosetta_details else "navigation updated",
            "patched": patched,
        }
    return payload


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


_CARTRIDGE_IMPORT_SUFFIXES = {".md", ".json", ".mdc", ".seed"}


def resolve_cartridge_import_root(folder: Path) -> Path:
    source = folder.resolve()
    if not source.is_dir():
        raise ValueError(f"Folder not found: {folder}")
    if (source / "manifest.json").is_file() or (source / "holistic.md").is_file():
        return source
    nested = source / "cartridge"
    if nested.is_dir() and (
        (nested / "manifest.json").is_file() or (nested / "holistic.md").is_file()
    ):
        return nested
    return source


def _cartridge_import_allowed(rel: Path) -> bool:
    suffix = rel.suffix.lower()
    if suffix in {".md", ".json"}:
        return True
    name = rel.name.lower()
    return name.endswith(".mdc.seed")


def _stage_context_sources(paths: RepoPaths, source_files: list[Path]) -> tuple[list[str], list[str]]:
    dest_dir = paths.sources / "imported"
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    warnings: list[str] = []
    for raw in source_files:
        src = raw.resolve()
        if not src.is_file():
            warnings.append(f"Skipped (not a file): {src}")
            continue
        if src.suffix.lower() not in SUPPORTED_EXTENSIONS:
            warnings.append(f"Skipped (unsupported type): {src.name}")
            continue
        dest = dest_dir / src.name
        if dest.exists():
            stem = dest.stem
            suffix = dest.suffix
            counter = 2
            while dest.exists():
                dest = dest_dir / f"{stem}-{counter}{suffix}"
                counter += 1
        shutil.copy2(src, dest)
        copied.append(dest.relative_to(paths.root).as_posix())
    return copied, warnings


def _merge_cartridge_promote(payload: dict, promote_result: dict | None) -> dict:
    if not promote_result:
        return payload
    payload["promote"] = promote_result
    return payload


def cartridge_load_will_promote(*, promote_checked: bool, handoff_unified: bool) -> bool:
    return promote_checked and handoff_unified


def cartridge_load_needs_feature(mode: str, *, will_promote: bool) -> bool:
    if mode in ("sources", "translate"):
        return True
    return False


def _run_cartridge_promote(project_root: Path, feature: str, *, promote: bool, force: bool = False) -> dict | None:
    if not promote:
        return None
    from hive_planner.cartridge_promote import promote_cartridge_drafts

    paths = RepoPaths(root=project_root.resolve())
    return promote_cartridge_drafts(paths, feature.strip(), force=force).to_dict()


def run_cartridge_load_sources(
    project_root: Path,
    source_files: list[Path],
    feature: str,
    *,
    embed: bool = False,
    promote: bool = True,
    force_promote: bool = False,
) -> dict:
    target = project_root.resolve()
    summary = summarize_project(target)
    if not summary.ok:
        return {"ok": False, "error": summary.detail}
    if not source_files:
        return {"ok": False, "error": "Choose at least one source file."}
    try:
        validate_feature_id(feature.strip())
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    paths = RepoPaths(root=target)
    copied, warnings = _stage_context_sources(paths, source_files)
    if not copied:
        return {"ok": False, "error": "No supported source files were copied.", "warnings": warnings}

    ingest_report = ingest(paths, embed=embed)
    try:
        outputs, emit_warnings = emit_cartridge(paths, feature.strip())
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "copied": copied, "warnings": warnings}

    return _merge_cartridge_promote(
        {
            "ok": True,
            "mode": "sources",
            "feature": feature.strip(),
            "copied": copied,
            "processed": ingest_report.processed,
            "skipped": ingest_report.skipped,
            "outputs": {name: path.relative_to(target).as_posix() for name, path in outputs.items()},
            "warnings": warnings + list(ingest_report.warnings) + list(emit_warnings),
        },
        _run_cartridge_promote(target, feature, promote=promote, force=force_promote),
    )


def run_cartridge_translate(
    project_root: Path,
    input_file: Path,
    feature: str,
    *,
    promote: bool = True,
    force_promote: bool = False,
) -> dict:
    from hive_planner.translator import TranslatorError, translate_document, write_translator_status

    target = project_root.resolve()
    summary = summarize_project(target)
    if not summary.ok:
        return {"ok": False, "error": summary.detail}
    try:
        validate_feature_id(feature.strip())
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    paths = RepoPaths(root=target)
    try:
        result = translate_document(paths, input_file, feature.strip())
        status_path = write_translator_status(paths, result)
    except (TranslatorError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}

    return _merge_cartridge_promote(
        {
            "ok": True,
            "mode": "translate",
            "feature": feature.strip(),
            "input": str(input_file),
            "files_written": result.files_written,
            "status_path": status_path.relative_to(target).as_posix(),
            "classification_counts": result.classification_counts,
        },
        _run_cartridge_promote(target, feature, promote=promote, force=force_promote),
    )


def run_cartridge_import_folder(
    project_root: Path,
    folder: Path,
    *,
    overwrite: bool = False,
    feature: str | None = None,
    promote: bool = True,
    force_promote: bool = False,
) -> dict:
    target = project_root.resolve()
    summary = summarize_project(target)
    if not summary.ok:
        return {"ok": False, "error": summary.detail}
    try:
        cart_src = resolve_cartridge_import_root(folder)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    paths = RepoPaths(root=target)
    paths.cartridge.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    skipped: list[str] = []
    for path in sorted(cart_src.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(cart_src)
        if not _cartridge_import_allowed(rel):
            continue
        dest = paths.cartridge / rel
        if dest.exists() and not overwrite:
            skipped.append(rel.as_posix())
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        written.append(rel.as_posix())

    if not written and not skipped:
        return {
            "ok": False,
            "error": "No cartridge markdown or manifest files found in that folder.",
        }
    if not written:
        return {
            "ok": False,
            "error": "All cartridge files already exist in the project (nothing imported).",
            "mode": "import",
            "import_root": str(cart_src),
            "written": written,
            "skipped": skipped,
        }

    payload = {
        "ok": True,
        "mode": "import",
        "import_root": str(cart_src),
        "written": written,
        "skipped": skipped,
    }
    manifest = None
    manifest_path = paths.cartridge / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = None

    if promote:
        from hive_planner.cartridge_adapt import (
            adapt_cartridge_for_promote,
            import_needs_cartridge_adapt,
            infer_feature_id,
        )

        try:
            resolved_feature = infer_feature_id(
                requested=feature,
                imported_rels=written,
                manifest=manifest,
            )
            if import_needs_cartridge_adapt(paths, written):
                adapt = adapt_cartridge_for_promote(
                    paths,
                    resolved_feature,
                    overwrite=overwrite,
                    source_rels=written,
                )
                payload["adapt"] = adapt.to_dict()
                payload.setdefault("warnings", []).extend(adapt.warnings)
            payload["feature"] = resolved_feature
            payload = _merge_cartridge_promote(
                payload,
                _run_cartridge_promote(target, resolved_feature, promote=promote, force=force_promote),
            )
        except ValueError as exc:
            msg = str(exc)
            payload.setdefault("warnings", []).append(msg)
            payload["promote"] = {
                "ok": False,
                "feature": feature,
                "promotions": {},
                "warnings": [msg],
            }
    return payload


def run_project_init(
    config: LauncherConfig,
    *,
    target: Path,
    name: str | None,
    profile: str,
    git_init: bool,
    force: bool,
    agent_handoff: str | None = None,
    spec_kit: bool | None = None,
    continual_learning: bool | None = None,
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
            agent_handoff=agent_handoff,
            spec_kit=spec_kit,
            continual_learning=continual_learning,
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


_CURSOR_LOG_APP_ROOT = re.compile(
    r"([A-Za-z]:\\[^\"'\s]+?\\cursor\\[^\\]+)\\resources\\app",
    re.IGNORECASE,
)


def _cursor_exe_from_app_root(app_root: Path) -> str | None:
    candidate = app_root / "Cursor.exe"
    if candidate.is_file():
        return str(candidate)
    return None


def _cursor_from_config(config: LauncherConfig | None) -> str | None:
    if config is None:
        return None
    raw = config.cursor_executable.strip()
    if not raw:
        return None
    candidate = Path(raw)
    if candidate.is_file():
        return str(candidate)
    return None


def _cursor_from_path() -> str | None:
    found = shutil.which("cursor")
    if found:
        return found
    return None


def _cursor_from_well_known_paths() -> str | None:
    candidates: list[Path] = []
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            local_root = Path(local)
            for rel in (
                "Programs/cursor/Cursor.exe",
                "Programs/Cursor/Cursor.exe",
                "Programs/cursor/_/Cursor.exe",
                "Programs/Cursor/_/Cursor.exe",
                "cursor/Cursor.exe",
                "cursor/_/Cursor.exe",
            ):
                candidates.append(local_root / rel)
        for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
            env_val = os.environ.get(env_name, "")
            if not env_val:
                continue
            root = Path(env_val)
            candidates.extend(
                (
                    root / "cursor" / "Cursor.exe",
                    root / "cursor" / "_" / "Cursor.exe",
                    root / "Cursor" / "Cursor.exe",
                    root / "Cursor" / "_" / "Cursor.exe",
                )
            )
    elif sys.platform == "darwin":
        candidates.append(Path("/Applications/Cursor.app/Contents/MacOS/Cursor"))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def _cursor_from_logs() -> str | None:
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        return None
    logs_root = Path(appdata) / "Cursor" / "logs"
    if not logs_root.is_dir():
        return None
    log_files = sorted(
        logs_root.rglob("*.log"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for log_file in log_files[:30]:
        try:
            text = log_file.read_text(encoding="utf-8", errors="ignore")[:100_000]
        except OSError:
            continue
        match = _CURSOR_LOG_APP_ROOT.search(text)
        if not match:
            continue
        resolved = _cursor_exe_from_app_root(Path(match.group(1)))
        if resolved:
            return resolved
    return None


def _cursor_from_start_menu_shortcuts() -> str | None:
    if sys.platform != "win32":
        return None
    start_dirs: list[Path] = []
    for env_name in ("APPDATA", "PROGRAMDATA"):
        env_val = os.environ.get(env_name, "")
        if not env_val:
            continue
        start_dirs.append(Path(env_val) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    for start_dir in start_dirs:
        if not start_dir.is_dir():
            continue
        try:
            links = sorted(start_dir.rglob("*.lnk"))
        except OSError:
            continue
        for link in links:
            if "cursor" not in link.name.lower():
                continue
            target = _resolve_windows_shortcut(link)
            if target and Path(target).is_file():
                return target
    return None


def _resolve_windows_shortcut(link_path: Path) -> str | None:
    if sys.platform != "win32":
        return None
    try:
        proc = _run_hidden(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(New-Object -ComObject WScript.Shell).CreateShortcut('{link_path}').TargetPath",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    target = (proc.stdout or "").strip()
    if proc.returncode != 0 or not target:
        return None
    return target


def find_cursor_executable(config: LauncherConfig | None = None) -> str | None:
    for resolver in (
        lambda: _cursor_from_config(config),
        _cursor_from_path,
        _cursor_from_well_known_paths,
        _cursor_from_logs,
        _cursor_from_start_menu_shortcuts,
    ):
        found = resolver()
        if found:
            return found
    return None


def open_in_cursor(project_root: Path, *, config: LauncherConfig | None = None) -> dict:
    raw = Path(project_root)
    if is_code_workspace_file(raw):
        target = raw
        if not target.is_file():
            return {"ok": False, "error": "Workspace file not found"}
        launch_path = target.resolve()
        cwd = str(launch_path.parent)
    else:
        try:
            launch_path = raw.resolve()
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        if not launch_path.is_dir():
            return {"ok": False, "error": "Directory not found"}
        cwd = str(launch_path)
    cursor_exe = find_cursor_executable(config)
    if not cursor_exe:
        return {
            "ok": False,
            "error": (
                "Cursor not found. Install Cursor, add the cursor CLI to PATH, "
                "or set Cursor executable in Settings."
            ),
        }
    try:
        subprocess.Popen([cursor_exe, str(launch_path)], cwd=cwd, shell=False)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    hive_root = resolve_linked_project_root(launch_path)
    summary = summarize_project(hive_root) if hive_root else summarize_project(launch_path)
    return {
        "ok": True,
        "path": str(launch_path),
        "cursor": cursor_exe,
        "hive_ready": summary.ok,
        "bootstrap_profile": summary.bootstrap_profile,
        "entry_kind": "workspace" if is_code_workspace_file(launch_path) else "folder",
    }

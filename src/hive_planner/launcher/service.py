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
from collections.abc import Callable, Iterable
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
    portable_mode: bool = False
    unified_handoff_ready: bool = False
    unified_handoff_detail: str = ""

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
            "portable_mode": self.portable_mode,
            "unified_handoff_ready": self.unified_handoff_ready,
            "unified_handoff_detail": self.unified_handoff_detail,
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
    # Bare Windows paths with spaces (e.g. C:\Program Files\...\python.exe) must
    # stay as a single argv entry even when the user omitted quotes.
    if Path(raw).is_file():
        return [raw]
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
    from hive_planner.portable_runtime import verify_portable_deploy
    from hive_planner.runtime_paths import is_portable_runtime, portable_app_root

    hive_root = config.normalized_hive_root()
    runtime_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if is_portable_runtime():
        python_ok = sys.version_info >= (3, 10)
        python_version = f"{runtime_version}  (bundled — no separate Python install)"
        try:
            from hive_planner import __version__ as hive_version_str

            hive_version = hive_version_str
        except ImportError:
            hive_version = ""
        app_root = portable_app_root()
        deployed_ok, missing = verify_portable_deploy(app_root)
        if deployed_ok:
            unified_detail = "Spec Kit + Continual Learning ready"
            unified_ready = True
        else:
            unified_detail = f"Not deployed — run Verify install ({len(missing)} missing)"
            unified_ready = False
        return SetupStatus(
            python_ok=python_ok,
            python_version=python_version,
            hive_root=str(app_root),
            hive_root_ok=True,
            hive_installed=True,
            hive_version=hive_version,
            git_available=shutil.which("git") is not None,
            onboarding_complete=config.onboarding_complete,
            portable_mode=True,
            unified_handoff_ready=unified_ready,
            unified_handoff_detail=unified_detail,
        )
    configured = probe_python_command(_python_command(config))
    if configured:
        python_ok = configured.supported
        python_version = f"{configured.version}  ({configured.command})"
    else:
        # Do not treat the launcher interpreter as an OK substitute for a broken
        # configured python_executable — Install/onboarding still use that command.
        python_ok = False
        python_version = f"{runtime_version}  (launcher runtime; configured Python unavailable)"
    hive_version = ""
    hive_installed = False
    py_cmd = _python_command(config)
    try:
        proc = _run_hidden(
            [*py_cmd, "-c", "import importlib.metadata as m; print(m.version('hive-planner'))"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode == 0:
            version = (proc.stdout or "").strip().splitlines()
            if version:
                hive_version = version[0].strip()
                hive_installed = True
    except (OSError, subprocess.SubprocessError, ValueError):
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
    from hive_planner.portable_runtime import verify_portable_deploy
    from hive_planner.runtime_paths import is_portable_runtime, portable_app_root

    if config.onboarding_complete:
        return False
    if is_portable_runtime():
        deployed_ok, _missing = verify_portable_deploy(portable_app_root())
        if deployed_ok:
            config.onboarding_complete = True
            return True
        return False
    status = get_setup_status(config)
    if status.python_ok and status.hive_root_ok and status.hive_installed:
        config.onboarding_complete = True
        return True
    return False


def run_install(config: LauncherConfig, *, extras: str = "dev") -> InstallResult:
    from hive_planner.portable_runtime import ensure_portable_runtime
    from hive_planner.runtime_paths import is_portable_runtime, portable_app_root

    if is_portable_runtime():
        report = ensure_portable_runtime(portable_app_root(), force=True)
        if report.ok:
            detail = report.detail
            if report.files_written:
                detail += f" ({len(report.files_written)} file(s) updated)"
        else:
            detail = report.detail
            if report.missing:
                detail += f" — missing: {', '.join(report.missing)}"
        return InstallResult(report.ok, detail)
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


def run_portable_bootstrap(*, force: bool = False) -> dict:
    """Deploy or verify Spec Kit + CL beside the portable exe (first-run / repair)."""
    from hive_planner.portable_runtime import ensure_portable_runtime
    from hive_planner.runtime_paths import is_portable_runtime, portable_app_root

    if not is_portable_runtime():
        return {"ok": False, "error": "Not a portable runtime"}
    report = ensure_portable_runtime(portable_app_root(), force=force)
    return report.to_dict()


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
    netloc = unquote(parsed.netloc or "").strip()
    if sys.platform == "win32":
        if netloc and netloc.lower() != "localhost":
            # UNC / WSL: file://server/share/... → \\server\share\...
            unc = "\\\\" + netloc + path.replace("/", "\\")
            return unc.rstrip("\\") or None
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
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
    return None


def workspace_primary_folder(path: Path) -> Path | None:
    if is_code_workspace_file(path):
        if not path.is_file():
            return None
        roots = _resolved_workspace_roots(path)
        if not roots:
            try:
                parent = path.parent.resolve()
            except OSError:
                parent = path.parent
            return parent if parent.is_dir() else None
        best = _best_hive_root(_collect_hive_root_candidates(roots))
        if best is not None:
            return best
        for root in roots:
            if root.is_dir():
                return root
        # Do not return a missing folder path — callers treat None as unlinkable.
        return None
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


def candidates_path_in_project(project_root: Path, candidates_path: Path) -> bool:
    """True when candidates_path resolves inside project_root."""
    try:
        candidates_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return False
    return candidates_path.is_file()


def memory_candidates_picker_dir(project_root: Path, default: Path | None = None) -> str:
    """Existing directory for CL candidates file picker (Windows requires a real initialdir)."""
    root = project_root.resolve()
    if default is not None:
        if default.is_file():
            return str(default.parent)
        if default.is_dir():
            return str(default)
    proposals = root / "docs" / "proposals"
    if proposals.is_dir():
        return str(proposals)
    return str(root)


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


def _missing_from_ci_report(report) -> list[str]:
    from hive_planner.ci_handoff import CiCheckReport
    from hive_planner.vendor_sync import CL_OVERLAY_REL, OVERLAY_REV_FILE, SPEC_KIT_OVERLAY_REL

    if not isinstance(report, CiCheckReport):
        return []
    missing: list[str] = []
    for step in report.steps:
        if step.ok:
            continue
        if step.name == "agent-handoff-profile" and step.detail.startswith("missing:"):
            tail = step.detail.split("missing:", 1)[1]
            missing.extend(part.strip() for part in tail.split(",") if part.strip())
        if step.name == "unified-vendor":
            if "missing .hive/upstream-pins.json" in step.detail:
                missing.append(".hive/upstream-pins.json")
            for fragment in step.detail.split(";"):
                fragment = fragment.strip()
                if "overlay missing: " in fragment:
                    missing.append(fragment.split("overlay missing: ", 1)[1].strip())
                elif "spec-kit overlay stale" in fragment:
                    missing.append(f"{SPEC_KIT_OVERLAY_REL}/{OVERLAY_REV_FILE}")
                elif "continual-learning overlay stale" in fragment:
                    missing.append(f"{CL_OVERLAY_REL}/{OVERLAY_REV_FILE}")
    deduped: list[str] = []
    for rel in missing:
        if rel not in deduped:
            deduped.append(rel)
    return deduped


def unified_vendor_repair_hints(*, missing: list[str] | None = None) -> list[str]:
    """Launcher tips when unified vendor artifacts are missing or stale."""
    if not missing:
        return []
    markers = (
        ".hive/upstream-pins.json",
        ".hive/spec-kit/",
        "hive-continual-learning",
        ".hive-overlay-rev",
    )
    if not any(any(marker in rel for marker in markers) for rel in missing):
        return []
    return [
        "Home → Verify vendor pins to inspect pins and overlays.",
        "Repair: Home → Deploy agent handoff (refreshes .hive/spec-kit/ and hive-continual-learning plugin).",
    ]


def ci_check_hints(root: Path, report) -> list[str]:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED
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
    if not report.ok and not is_hive_planner_source_repo(root):
        hints.append(
            "Full roadmap checks apply only to the Hive Planner source repo. "
            "Bootstrapped app/workspace projects skip roadmap-artifacts."
        )
    elif "roadmap-artifacts" in failed:
        hints.append("Roadmap failures mean spec/delta/tasks files are missing for planned features in this repo.")
    if "unified-vendor" in failed:
        if is_hive_planner_source_repo(root):
            hints.append(
                "Hive source vendor check failed. Run py -3.11 -m hive_planner vendor-sync --check "
                "and vendor-sync --apply from this repo root — see scripts/README.md § Unified vendor path."
            )
        elif integrations.agent_handoff_mode == AGENT_HANDOFF_UNIFIED:
            vendor_missing = _missing_from_ci_report(report)
            hints.extend(unified_vendor_repair_hints(missing=vendor_missing or [".hive/upstream-pins.json"]))
    if "cl-install" in failed:
        from hive_planner.agent_handoff import scan_legacy_deployment
        from hive_planner.cl_migration import hive_cl_installed, marketplace_cl_installed

        findings = {item.code: item for item in scan_legacy_deployment(root).findings}
        migrate_cmd = "py -3.11 -m hive_planner cl-migrate"
        if (
            "dual_cl_install" in findings
            or "marketplace_cl_only" in findings
            or (marketplace_cl_installed(root) and hive_cl_installed(root))
        ):
            migrate_cmd += " --remove-marketplace-plugin"
        hints.append(
            "Migrate marketplace Continual Learning: Home → Migrate marketplace CL, or "
            + migrate_cmd
        )
    if "wiring-audit" in failed:
        hints.append(
            "Record wiring audit after integration validation: Home → Record wiring audit, or "
            'py -3.11 -m hive_planner wiring-audit record --evidence "pytest tests/… -q"'
        )
        hints.append(
            "Complete unchecked items in tasks.md Integration wiring audit checklist before recording."
        )
    return hints


def wiring_audit_status_label(project_root: Path) -> str:
    from hive_planner.wiring_audit import check_wiring_audit, wiring_audit_enforced

    paths = RepoPaths(root=project_root.resolve())
    if not wiring_audit_enforced(paths):
        return "n/a"
    report = check_wiring_audit(paths)
    if report.ok:
        return "ok"
    if "Missing wiring audit" in report.detail:
        return "missing"
    if any("stale" in item for item in report.missing):
        return "stale"
    if any("checklist incomplete" in item for item in report.missing):
        return "checklist"
    return "review"


def find_staged_candidates(project_root: Path) -> Path | None:
    proposals = project_root.resolve() / "docs" / "proposals"
    if not proposals.is_dir():
        return None
    paths: list[Path] = []
    for pattern in ("candidates*.md", "cartridge-memory-*.md"):
        for path in proposals.glob(pattern):
            if path.name == "candidates-template.md":
                continue
            if path.is_file() and path.stat().st_size > 0:
                paths.append(path)
    if not paths:
        return None
    return max(paths, key=lambda path: path.stat().st_mtime)


def run_wiring_audit_check(project_root: Path) -> dict:
    summary = summarize_project(project_root)
    if not summary.ok:
        return {"ok": False, "error": summary.detail}
    from hive_planner.wiring_audit import check_wiring_audit, wiring_audit_enforced

    paths = RepoPaths(root=project_root.resolve())
    if not wiring_audit_enforced(paths):
        return {"ok": True, "skipped": True, "detail": "wiring audit not enforced for this project"}
    report = check_wiring_audit(paths)
    payload = report.to_dict()
    payload["ok"] = report.ok
    if not report.ok:
        payload["hints"] = [
            'Home → Record wiring audit, or: py -3.11 -m hive_planner wiring-audit record --evidence "pytest … -q"',
            "Complete the Integration wiring audit checklist in tasks.md before recording.",
        ]
    return payload


def run_wiring_audit_record(project_root: Path, evidence: str) -> dict:
    summary = summarize_project(project_root)
    if not summary.ok:
        return {"ok": False, "error": summary.detail}
    from hive_planner.wiring_audit import WiringAuditError, check_wiring_audit, record_wiring_audit, wiring_audit_enforced

    paths = RepoPaths(root=project_root.resolve())
    if not wiring_audit_enforced(paths):
        return {"ok": True, "skipped": True, "detail": "wiring audit not enforced for this project"}
    try:
        out_path = record_wiring_audit(paths, evidence=evidence)
    except WiringAuditError as exc:
        return {"ok": False, "error": str(exc)}
    check = check_wiring_audit(paths)
    payload = {
        "ok": check.ok,
        "recorded": out_path.relative_to(paths.root).as_posix(),
        "check": check.to_dict(),
    }
    if not check.ok:
        payload["error"] = check.detail
        payload["hints"] = [
            "Attestation recorded but check still failing — review tasks.md wiring audit checklist.",
        ]
    return payload


def run_unified_verify(project_root: Path) -> dict:
    summary = summarize_project(project_root)
    if not summary.ok:
        return {"ok": False, "error": summary.detail, "detail": summary.detail}
    from hive_planner.vendor_sync import unified_verify

    paths = RepoPaths(root=project_root.resolve())
    report = unified_verify(paths)
    payload = report.to_dict()
    payload["ok"] = report.ok
    if not report.ok:
        payload["error"] = "; ".join(report.issues) if report.issues else "Unified vendor verify failed"
        payload["hints"] = [
            "Home → Deploy agent handoff refreshes .hive/upstream-pins.json and vendored overlays.",
            "Home → Scan legacy deployment for marketplace CL or starter-kit-only layout.",
        ]
    return payload


def run_legacy_deployment_scan(project_root: Path) -> dict:
    summary = summarize_project(project_root)
    if not summary.ok:
        return {"ok": False, "error": summary.detail, "detail": summary.detail}
    from hive_planner.agent_handoff import scan_legacy_deployment

    report = scan_legacy_deployment(project_root.resolve())
    payload = report.to_dict()
    if not report.findings:
        payload["detail"] = "No legacy deployment traces detected."
    elif report.ok:
        payload["detail"] = f"{len(report.findings)} informational finding(s); no blocking legacy layout."
    else:
        warns = [item for item in report.findings if item.severity == "warn"]
        payload["detail"] = f"{len(warns)} legacy deployment issue(s) detected."
    return payload


def run_cl_migrate(project_root: Path, *, remove_marketplace_plugin: bool = False, dry_run: bool = False) -> dict:
    summary = summarize_project(project_root)
    if not summary.ok:
        return {"ok": False, "error": summary.detail, "detail": summary.detail}
    from hive_planner.cl_migration import ClMigrationError, migrate_marketplace_cl

    paths = RepoPaths(root=project_root.resolve())
    try:
        report = migrate_marketplace_cl(
            paths,
            remove_marketplace_plugin=remove_marketplace_plugin,
            dry_run=dry_run,
        )
    except ClMigrationError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "hints": ["Verify the marketplace plugin path before removal."],
        }
    payload = report.to_dict()
    from hive_planner.cl_runtime import requires_cursor_plugin, resolve_cl_runtime

    runtime = resolve_cl_runtime(project_root)
    payload["cl_runtime"] = runtime
    if report.ok and any("lint failed" in w for w in report.warnings):
        payload["hints"] = [
            "Marketplace plugin removed; fix AGENTS.md lint issues and re-run migrate to merge Learned Workspace Facts.",
        ]
    elif not report.ok:
        payload["error"] = "; ".join(report.warnings) if report.warnings else "CL migration failed"
        if report.removed_marketplace_plugin:
            payload["hints"] = [
                "Marketplace plugin removed; fix AGENTS.md lint issues and re-run migrate to merge Learned Workspace Facts.",
            ]
        elif not requires_cursor_plugin(runtime):
            payload["hints"] = [
                "Headless runtime: fix warnings above, then use agents-propose/agents-apply for memory promotion.",
            ]
        else:
            payload["hints"] = [
                "Deploy agent handoff first if hive-continual-learning is missing.",
                "Re-run with remove marketplace plugin enabled after reviewing the log.",
            ]
    return payload


def run_agents_memory_propose(project_root: Path, candidates_path: Path, *, apply: bool = False) -> dict:
    from hive_planner.agents_memory import AgentsMemoryError, run_agents_memory
    from hive_planner.wiring_audit import check_wiring_audit, wiring_audit_enforced

    summary = summarize_project(project_root)
    if not summary.ok:
        return {"ok": False, "error": summary.detail, "detail": summary.detail}
    paths = RepoPaths(root=project_root.resolve())
    candidate_file = candidates_path if candidates_path.is_absolute() else paths.root / candidates_path
    if not candidate_file.is_file():
        return {"ok": False, "error": f"Candidates file not found: {candidates_path}"}
    if not candidates_path_in_project(paths.root, candidate_file):
        return {
            "ok": False,
            "error": f"Candidates file must be inside project root: {paths.root}",
            "hints": ["Select a candidates file from the linked project docs/proposals folder."],
        }
    if candidate_file.name.startswith("agents-memory-") and candidate_file.suffix.lower() == ".md":
        return {
            "ok": False,
            "error": "Select a candidates file, not a generated agents-memory proposal.",
            "hints": [
                "Use docs/proposals/candidates.md, cl-candidates.md, or another source export.",
                "Open the proposal file separately to review rejection reasons.",
            ],
        }
    if wiring_audit_enforced(paths):
        wiring = check_wiring_audit(paths)
        if not wiring.ok:
            return {
                "ok": False,
                "error": f"Wiring audit required before memory promotion - {wiring.detail}",
                "hints": [
                    'Home → Record wiring audit after validation, or: py -3.11 -m hive_planner wiring-audit record --evidence "pytest … -q"',
                ],
            }
    try:
        result = run_agents_memory(paths, candidate_file, apply=apply, auto_route=True)
    except AgentsMemoryError as exc:
        msg = str(exc)
        payload: dict = {"ok": False, "error": msg}
        lowered = msg.lower()
        if exc.proposal_path:
            payload["proposal_path"] = exc.proposal_path
            payload["rejected"] = exc.rejected
            payload["spec_actions"] = exc.spec_actions
            payload["current_facts"] = exc.current_facts
            payload["after_section"] = exc.after_section or exc.current_facts
            payload["accepted"] = exc.accepted
        if "all candidate" in lowered:
            payload["all_rejected"] = True
            payload["hints"] = [
                "Add `# operational` or `# behavioral` tags to ambiguous bullets.",
                "Behavioral bullets belong in the active spec.md, not AGENTS.md.",
                "Oversized operational bullets are auto-split when possible; check routing in the proposal.",
            ]
        elif "wiring audit" in lowered:
            payload["hints"] = [
                'Home → Record wiring audit after validation, or: py -3.11 -m hive_planner wiring-audit record --evidence "pytest … -q"',
            ]
        elif "inside project root" in lowered:
            payload["hints"] = ["Select a candidates file from the linked project docs/proposals folder."]
        return payload
    return {
        "ok": True,
        "applied": result.applied,
        "noop": apply and not result.applied and not result.accepted,
        "proposal_path": result.proposal_path.relative_to(paths.root).as_posix(),
        "accepted": result.accepted,
        "rejected": [{"candidate": c, "reason": r} for c, r in result.rejected],
        "current_facts": result.current_facts,
        "after_section": result.after_section,
        "spec_actions": result.spec_actions,
        "routing": result.routing,
    }


def run_agents_memory_finalize_apply(project_root: Path, prior: dict) -> dict:
    """Apply accepted bullets from a prior propose result without re-routing candidates."""
    from hive_planner.agents_memory import AgentsMemoryError, apply_agents_memory_accepted

    summary = summarize_project(project_root)
    if not summary.ok:
        return {"ok": False, "error": summary.detail, "detail": summary.detail}
    paths = RepoPaths(root=project_root.resolve())
    accepted = prior.get("accepted") or []
    if not accepted:
        return {"ok": False, "error": "No accepted bullets in prior propose result"}
    rejected = [
        (item["candidate"], item["reason"])
        for item in prior.get("rejected") or []
        if isinstance(item, dict) and "candidate" in item and "reason" in item
    ]
    try:
        result = apply_agents_memory_accepted(
            paths,
            accepted=accepted,
            rejected=rejected,
            spec_actions=prior.get("spec_actions") or [],
            routing=prior.get("routing") or [],
            current_facts=prior.get("current_facts"),
            after_section=prior.get("after_section"),
            proposal_path=prior.get("proposal_path"),
        )
    except AgentsMemoryError as exc:
        msg = str(exc)
        payload: dict = {"ok": False, "error": msg}
        if exc.proposal_path:
            payload["proposal_path"] = exc.proposal_path
            payload["rejected"] = exc.rejected
            payload["spec_actions"] = exc.spec_actions
            payload["current_facts"] = exc.current_facts
            payload["after_section"] = exc.after_section or exc.current_facts
            payload["accepted"] = exc.accepted
        return payload
    return {
        "ok": True,
        "applied": result.applied,
        "noop": not result.applied and not result.accepted,
        "proposal_path": result.proposal_path.relative_to(paths.root).as_posix(),
        "accepted": result.accepted,
        "rejected": [{"candidate": c, "reason": r} for c, r in result.rejected],
        "current_facts": result.current_facts,
        "after_section": result.after_section,
        "spec_actions": result.spec_actions,
        "routing": result.routing,
    }


def run_agents_memory_apply(project_root: Path, candidates_path: Path) -> dict:
    """Apply accepted CL candidates to AGENTS.md (agents-apply)."""
    return run_agents_memory_propose(project_root, candidates_path, apply=True)


def run_project_ci_check(project_root: Path) -> dict:
    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error}
    summary = summarize_project(target)
    if not summary.ok:
        return {"ok": False, "error": summary.detail}
    paths = RepoPaths(root=target)
    from hive_planner.runtime_paths import is_portable_runtime
    from hive_planner.spec_drift import repair_handoff_rosetta_navigation

    rosetta_repair = repair_handoff_rosetta_navigation(paths)
    repair = repair_agents_active_feature(paths)
    portable = is_portable_runtime()
    report = run_ci_check(
        paths,
        check_roadmap=None,
        skip_pytest=portable,
    )
    payload = report.to_dict()
    if rosetta_repair:
        payload["rosetta_repair"] = rosetta_repair
    if repair.repaired:
        payload["repair"] = {"feature": repair.feature, "detail": repair.detail}
    hints = ci_check_hints(target, report)
    if hints:
        payload["hints"] = hints
    return payload


def run_deploy_agent_handoff(
    project_root: Path,
    *,
    hive_planner_root: Path,
    force: bool = False,
    cl_runtime: str | None = None,
) -> dict:
    from hive_planner.agent_handoff import validate_unified_handoff
    from hive_planner.bootstrap import BootstrapError, deploy_agent_handoff_scaffold
    from hive_planner.cl_runtime import normalize_cl_runtime, resolve_cl_runtime
    from hive_planner.rosetta_nav import DEPLOY_HANDOFF_NAV_LAYERS, ensure_handoff_rosetta_navigation
    from hive_planner.spec_drift import BOOTSTRAP_DEFAULT_FEATURE, repair_agents_active_feature, repair_agents_rosetta_section

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error}
    summary = summarize_project(target)
    if not summary.ok:
        return {"ok": False, "error": summary.detail}
    resolved_runtime = normalize_cl_runtime(cl_runtime or resolve_cl_runtime(target))
    paths = RepoPaths(root=hive_planner_root.resolve())
    try:
        written, warnings = deploy_agent_handoff_scaffold(
            paths,
            target,
            force=force,
            cl_runtime=resolved_runtime,
        )
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
        "cl_runtime": resolved_runtime,
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
        hints = unified_vendor_repair_hints(missing=handoff.missing)
        if hints:
            payload["hints"] = hints
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


def run_project_bug_hunt_install(
    project_root: Path,
    *,
    iterations: int = 50,
) -> dict:
    """Install the chat-triggered bug-hunt script into a linked project."""
    from hive_planner.bug_hunt import BugHuntError, install_bug_hunt, missing_bug_hunt_artifacts

    target = project_root.resolve()
    if not target.exists():
        return {"ok": False, "error": "Path does not exist"}
    if target.is_file() and target.suffix.lower() == ".code-workspace":
        folder = resolve_linked_project_root(target)
        if folder is None:
            return {"ok": False, "error": "Workspace file has no folder on disk"}
        target = folder
    if not target.is_dir():
        return {"ok": False, "error": "Path is not a project directory"}
    try:
        installed = install_bug_hunt(target, iterations=iterations, force=True)
    except (BugHuntError, OSError) as exc:
        return {"ok": False, "error": str(exc)}
    payload = installed.to_dict()
    missing = missing_bug_hunt_artifacts(target)
    if missing:
        payload["ok"] = False
        payload["error"] = "Bug-hunt install incomplete — missing: " + ", ".join(missing)
        return payload
    payload["ok"] = True
    return payload


def run_project_agnostic_loop_install(project_root: Path) -> dict:
    """Install the pause-cycle agnostic loop into a linked project."""
    from hive_planner.agnostic_loop import install_agnostic_loop, missing_agnostic_loop_artifacts

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error}
    try:
        written = install_agnostic_loop(target)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    payload = {"ok": True, "files_written": written, "root": str(target)}
    missing = missing_agnostic_loop_artifacts(target)
    if missing:
        payload["ok"] = False
        payload["error"] = "Agnostic-loop install incomplete — missing: " + ", ".join(missing)
    return payload


def peek_bug_hunt_status(project_root: Path) -> dict:
    """Whether bug-hunt chat files are present in the linked project."""
    from hive_planner.bug_hunt import missing_bug_hunt_artifacts

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error, "installed": False, "missing": [], "action": "bug-hunt-status"}
    missing = missing_bug_hunt_artifacts(target)
    return {
        "ok": True,
        "action": "bug-hunt-status",
        "installed": not missing,
        "missing": missing,
        "root": str(target),
    }


def peek_agnostic_loop_status(project_root: Path) -> dict:
    """Whether hive-loop-kit files are present in the linked project."""
    from hive_planner.agnostic_loop import missing_agnostic_loop_artifacts

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error, "installed": False, "missing": [], "action": "agnostic-status"}
    missing = missing_agnostic_loop_artifacts(target)
    return {
        "ok": True,
        "action": "agnostic-status",
        "installed": not missing,
        "missing": missing,
        "root": str(target),
    }


def _agnostic_linked_or_error(project_root: Path, action: str) -> tuple[Path | None, dict | None]:
    from hive_planner.agnostic_loop import catalog_problem

    target, error = linked_install_directory(project_root)
    if error:
        return None, {"ok": False, "error": error, "action": action}
    try:
        problem = catalog_problem(target)
    except OSError as exc:
        return None, {"ok": False, "error": str(exc), "action": action, "blocked_reason": str(exc)}
    if problem:
        return None, {"ok": False, "error": problem, "action": action, "blocked_reason": problem}
    return target, None


def _agnostic_gate_payload(payload: dict, *, root: Path) -> dict:
    data = dict(payload)
    data["root"] = str(root)
    if data.get("ok") is False and not data.get("error"):
        data["error"] = data.get("blocked_reason") or "blocked"
    return data


def run_project_agnostic_loop_rewards(project_root: Path) -> dict:
    from hive_planner.agnostic_loop import rewards

    target, fail = _agnostic_linked_or_error(project_root, "rewards")
    if fail:
        return fail
    try:
        names = list(rewards(target))
    except OSError as exc:
        return {"ok": False, "action": "rewards", "error": str(exc), "blocked_reason": str(exc)}
    return {"ok": True, "action": "rewards", "rewards": names, "root": str(target)}


def run_project_agnostic_loop_status(project_root: Path) -> dict:
    from hive_planner.agnostic_loop import status

    target, fail = _agnostic_linked_or_error(project_root, "status")
    if fail:
        return fail
    try:
        report = status(target)
    except OSError as exc:
        return {"ok": False, "action": "status", "error": str(exc), "blocked_reason": str(exc)}
    return _agnostic_gate_payload(report, root=target)


def run_project_agnostic_loop_arm(project_root: Path, reward: str, cycles: int) -> dict:
    from hive_planner.agnostic_loop import arm

    target, fail = _agnostic_linked_or_error(project_root, "arm")
    if fail:
        return fail
    try:
        payload, _code = arm(target, reward, cycles)
    except OSError as exc:
        return {"ok": False, "action": "arm", "error": str(exc), "blocked_reason": str(exc)}
    return _agnostic_gate_payload(payload, root=target)


def run_project_agnostic_loop_begin(project_root: Path) -> dict:
    from hive_planner.agnostic_loop import begin

    target, fail = _agnostic_linked_or_error(project_root, "begin")
    if fail:
        return fail
    try:
        payload, _code = begin(target)
    except OSError as exc:
        return {"ok": False, "action": "begin", "error": str(exc), "blocked_reason": str(exc)}
    return _agnostic_gate_payload(payload, root=target)


def run_project_agnostic_loop_review(project_root: Path, note: str) -> dict:
    from hive_planner.agnostic_loop import review

    target, fail = _agnostic_linked_or_error(project_root, "review")
    if fail:
        return fail
    try:
        payload, _code = review(target, note)
    except OSError as exc:
        return {"ok": False, "action": "review", "error": str(exc), "blocked_reason": str(exc)}
    return _agnostic_gate_payload(payload, root=target)


def run_project_agnostic_loop_observe(project_root: Path, reward: str, hit: bool) -> dict:
    from hive_planner.agnostic_loop import observe

    target, fail = _agnostic_linked_or_error(project_root, "observe")
    if fail:
        return fail
    try:
        payload, _code = observe(target, reward, hit)
    except OSError as exc:
        return {"ok": False, "action": "observe", "error": str(exc), "blocked_reason": str(exc)}
    return _agnostic_gate_payload(payload, root=target)


def run_project_agnostic_loop_choose(
    project_root: Path,
    open_text: str | None = None,
    *,
    do_arm: bool = False,
    cycles: int = 1,
    sims: int = 64,
    horizon: int = 4,
    seed: int | None = None,
) -> dict:
    from hive_planner.agnostic_loop import choose, parse_open, rewards

    target, fail = _agnostic_linked_or_error(project_root, "choose")
    if fail:
        return fail
    try:
        names = rewards(target)
        opens = parse_open(open_text, names)
        if opens is None:
            return {
                "ok": False,
                "action": "choose",
                "error": "invalid --open",
                "blocked_reason": "invalid --open",
                "root": str(target),
            }
        payload, _code = choose(
            target,
            opens,
            sims=sims,
            horizon=horizon,
            seed=seed,
            do_arm=do_arm,
            cycles=cycles,
            names=names,
        )
    except OSError as exc:
        return {"ok": False, "action": "choose", "error": str(exc), "blocked_reason": str(exc)}
    return _agnostic_gate_payload(payload, root=target)


def linked_install_directory(project_root: Path) -> tuple[Path | None, str | None]:
    target = project_root.resolve()
    if not target.exists():
        return None, "Path does not exist"
    if target.is_file() and target.suffix.lower() == ".code-workspace":
        folder = resolve_linked_project_root(target)
        if folder is None:
            return None, "Workspace file has no folder on disk"
        target = folder
    if not target.is_dir():
        return None, "Path is not a project directory"
    return target, None


def peek_implementation_loop_pack(project_root: Path) -> dict:
    """Read the installed pack from the same folder install will use."""
    from hive_planner.implementation_loop import (
        LOOP_DIR,
        _read_existing_json_object,
        read_installed_pack,
    )

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error, "pack": None}
    try:
        _read_existing_json_object(target / LOOP_DIR / "state.json", "state.json")
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "pack": None, "root": str(target)}
    return {"ok": True, "pack": read_installed_pack(target), "root": str(target)}


def run_project_implementation_loop_install(
    project_root: Path,
    pack: str,
    *,
    force_pack: bool = False,
) -> dict:
    """Install the post-spec coding loop into a linked project."""
    from hive_planner.implementation_loop import install_implementation_loop

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error}
    try:
        written = install_implementation_loop(target, pack, force_pack=force_pack)
    except (ValueError, OSError) as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "files_written": written, "pack": pack}


def _resolve_implementation_loop_feature(target: Path, feature: str | None) -> tuple[str | None, str | None]:
    feat = (feature or "").strip() or None
    if not feat:
        feat = parse_active_feature(RepoPaths(root=target))
    if not feat:
        return None, "Set an active feature in AGENTS.md or enter a feature id."
    return feat, None


def _coordinator_error_payload(exc: Exception) -> dict:
    payload = {"ok": False, "error": str(exc)}
    fields = getattr(exc, "fields", None)
    if isinstance(fields, dict):
        payload.update(fields)
        payload["ok"] = False
        payload["error"] = str(exc)
    return payload


def run_project_implementation_loop_status(project_root: Path, feature: str | None = None) -> dict:
    """Report readiness using the same assess function as the CLI."""
    from hive_planner.implementation_loop import assess_implementation_readiness

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error, "action": "status"}
    feat, ferr = _resolve_implementation_loop_feature(target, feature)
    if ferr:
        return {"ok": False, "error": ferr, "action": "status"}
    report = assess_implementation_readiness(target, feat)
    payload = report.to_dict()
    payload["ok"] = bool(report.ready)
    payload["action"] = "status"
    payload["root"] = str(target)
    if not payload["ok"]:
        payload["error"] = payload.get("blocked_reason") or "not ready"
    return payload


def run_project_implementation_loop_start(
    project_root: Path,
    feature: str | None = None,
    *,
    allow_dirty: bool = False,
    force_feature: bool = False,
) -> dict:
    """Start coordinator gates (same as CLI `implementation-loop start`)."""
    from hive_planner.implementation_loop import CoordinatorError, coordinator_start

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error, "action": "start"}
    feat, ferr = _resolve_implementation_loop_feature(target, feature)
    if ferr:
        return {"ok": False, "error": ferr, "action": "start"}
    try:
        report = coordinator_start(
            target,
            feat,
            allow_dirty=allow_dirty,
            force_feature=force_feature,
        )
    except CoordinatorError as exc:
        return _coordinator_error_payload(exc)
    payload = report.to_dict()
    if payload.get("ok") is False and not payload.get("error"):
        payload["error"] = payload.get("blocked_reason") or "blocked"
    return payload


def run_project_implementation_loop_handoff(
    project_root: Path,
    role: str,
    *,
    continue_after_cap: bool = False,
) -> dict:
    """Write handoff.md (same as CLI `implementation-loop handoff`)."""
    from hive_planner.implementation_loop import CoordinatorError, coordinator_handoff

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error, "action": "handoff"}
    name = (role or "").strip()
    if not name:
        return {"ok": False, "error": "Enter a role (coder, checker, reviewer, or coordinator).", "action": "handoff"}
    try:
        report = coordinator_handoff(target, name, continue_after_cap=continue_after_cap)
    except CoordinatorError as exc:
        return _coordinator_error_payload(exc)
    payload = report.to_dict()
    if payload.get("ok") is False and not payload.get("error"):
        payload["error"] = payload.get("blocked_reason") or "blocked"
    return payload


def run_project_implementation_loop_check(project_root: Path) -> dict:
    """Run checker infrastructure (same as CLI `implementation-loop check`)."""
    from hive_planner.implementation_loop import CoordinatorError, coordinator_check

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error, "action": "check"}
    try:
        report = coordinator_check(target)
    except CoordinatorError as exc:
        return _coordinator_error_payload(exc)
    payload = report.to_dict()
    if payload.get("ok") is False and not payload.get("error"):
        payload["error"] = payload.get("blocked_reason") or "blocked"
    return payload


def run_project_implementation_loop_accept(project_root: Path, role: str) -> dict:
    """Accept a result.md entry (same as CLI `implementation-loop accept`)."""
    from hive_planner.implementation_loop import CoordinatorError, coordinator_accept

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error, "action": "accept"}
    name = (role or "").strip()
    if not name:
        return {"ok": False, "error": "Enter a role (coder, checker, reviewer, or coordinator).", "action": "accept"}
    try:
        report = coordinator_accept(target, name)
    except CoordinatorError as exc:
        return _coordinator_error_payload(exc)
    payload = report.to_dict()
    if payload.get("ok") is False and not payload.get("error"):
        payload["error"] = payload.get("blocked_reason") or "blocked"
    return payload


def run_project_implementation_loop_commit(project_root: Path) -> dict:
    """Commit after checker and reviewer pass (same as CLI `implementation-loop commit`)."""
    from hive_planner.implementation_loop import CoordinatorError, coordinator_commit

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error, "action": "commit"}
    try:
        report = coordinator_commit(target)
    except CoordinatorError as exc:
        return _coordinator_error_payload(exc)
    payload = report.to_dict()
    if payload.get("ok") is False and not payload.get("error"):
        payload["error"] = payload.get("blocked_reason") or "blocked"
    return payload


def run_project_map_sync(project_root: Path, *, dry_run: bool = False) -> dict:
    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error}
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


def peek_hive_planner_mcp(project_root: Path, config: LauncherConfig) -> dict:
    """Whether the active project lets a Cursor agent call this Hive Planner over MCP."""
    from hive_planner.launcher.mcp_servers import (
        HIVE_PLANNER_MCP_NAME,
        McpConfigError,
        format_mcp_args,
        hive_planner_mcp_enabled,
        hive_planner_stdio_launch,
        load_mcp_document,
        mcp_config_path,
    )

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error, "enabled": False}
    path = mcp_config_path(target)
    try:
        command, args = hive_planner_stdio_launch(config)
    except McpConfigError as exc:
        return {"ok": False, "error": str(exc), "enabled": False, "root": str(target)}
    try:
        doc = load_mcp_document(target)
    except McpConfigError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "enabled": False,
            "path": str(path),
            "root": str(target),
        }
    servers = doc.get("mcpServers")
    entry = servers.get(HIVE_PLANNER_MCP_NAME) if isinstance(servers, dict) else None
    enabled = hive_planner_mcp_enabled(doc)
    proposed = " ".join([command, format_mcp_args(args)]).strip()
    snippet = proposed
    if isinstance(entry, dict) and str(entry.get("command") or "").strip():
        stored_args = entry.get("args") if isinstance(entry.get("args"), list) else []
        stored = " ".join(
            [str(entry.get("command")).strip(), format_mcp_args([str(part) for part in stored_args])]
        ).strip()
        if stored:
            snippet = stored
    return {
        "ok": True,
        "enabled": enabled,
        "path": str(path),
        "root": str(target),
        "name": HIVE_PLANNER_MCP_NAME,
        "launch_command": command,
        "launch_args": args,
        "launch_snippet": snippet,
        "entry": entry if isinstance(entry, dict) else None,
    }


def run_set_hive_planner_mcp(project_root: Path, config: LauncherConfig, *, enabled: bool) -> dict:
    """Write or disable the hive-planner entry in the linked project's `.cursor/mcp.json`."""
    from hive_planner.launcher.mcp_servers import (
        McpConfigError,
        hive_planner_stdio_launch,
        load_mcp_document,
        save_mcp_document,
        set_hive_planner_mcp,
    )

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error, "enabled": False}
    try:
        command, args = hive_planner_stdio_launch(config)
        doc = load_mcp_document(target)
        set_hive_planner_mcp(doc, enabled=enabled, command=command, args=args)
        save_mcp_document(target, doc)
    except (McpConfigError, OSError) as exc:
        return {"ok": False, "error": str(exc), "enabled": False, "root": str(target)}
    payload = peek_hive_planner_mcp(target, config)
    payload["action"] = "enable" if enabled else "disable"
    return payload


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


def cartridge_load_mark_draft_default(
    *,
    mode: str,
    promote_checked: bool,
    handoff_unified: bool,
    config_default: bool,
) -> bool:
    if mode != "sources" or not promote_checked or not handoff_unified:
        return False
    return config_default


def cartridge_load_needs_feature(mode: str, *, will_promote: bool) -> bool:
    if mode in ("sources", "translate"):
        return True
    return False


def _run_cartridge_promote(
    project_root: Path,
    feature: str,
    *,
    promote: bool,
    force: bool = False,
    only_cartridge_paths: Iterable[Path] | None = None,
) -> dict | None:
    if not promote:
        return None
    from hive_planner.cartridge_promote import promote_cartridge_drafts

    paths = RepoPaths(root=project_root.resolve())
    return promote_cartridge_drafts(
        paths,
        feature.strip(),
        force=force,
        only_cartridge_paths=only_cartridge_paths,
    ).to_dict()


def run_cartridge_load_sources(
    project_root: Path,
    source_files: list[Path],
    feature: str,
    *,
    embed: bool = False,
    promote: bool = True,
    force_promote: bool = False,
    mark_emitted_draft: bool = False,
) -> dict:
    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error}
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
    warnings = warnings + list(ingest_report.warnings)

    from hive_planner.indexer import load_document_index

    indexed_paths = {doc.source_path for doc in load_document_index(paths.document_index).documents}
    indexed_copied = [rel for rel in copied if rel in indexed_paths]
    not_indexed = [rel for rel in copied if rel not in indexed_paths]
    if not_indexed:
        warnings.append(
            f"{len(not_indexed)} of {len(copied)} staged file(s) could not be indexed: "
            + ", ".join(not_indexed)
        )
    if not indexed_copied:
        return {
            "ok": False,
            "error": "Staged files were copied but none could be indexed into the context library.",
            "mode": "sources",
            "feature": feature.strip(),
            "copied": copied,
            "processed": ingest_report.processed,
            "skipped": ingest_report.skipped,
            "warnings": warnings,
        }

    try:
        outputs, emit_warnings = emit_cartridge(
            paths,
            feature.strip(),
            prefer_source_paths=indexed_copied,
        )
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "copied": copied, "warnings": warnings}

    mark_draft: dict[str, str] | None = None
    if mark_emitted_draft:
        from hive_planner.cartridge_promote import mark_cartridge_layers_draft

        mark_draft = mark_cartridge_layers_draft(
            paths,
            feature.strip(),
            only_paths=outputs.values(),
        )
        stamped = [
            name
            for name, status in mark_draft.items()
            if status in {"marked draft", "already draft"}
        ]
        if not stamped:
            warnings.append(
                "Mark as draft had nothing to stamp — Sources emit refreshes source-context "
                "(and delta sync when present), not research drafts. "
                "Use 'Turn one research note into planning drafts' for cartridge/*.md drafts, "
                "or ensure docs/delta layers exist before marking emitted cartridge files as draft."
            )

    payload = {
        "ok": True,
        "mode": "sources",
        "feature": feature.strip(),
        "copied": copied,
        "processed": ingest_report.processed,
        "skipped": ingest_report.skipped,
        "outputs": {name: path.relative_to(target).as_posix() for name, path in outputs.items()},
        "warnings": warnings + list(emit_warnings),
    }
    if mark_draft is not None:
        payload["mark_draft"] = mark_draft

    return _merge_cartridge_promote(
        payload,
        _run_cartridge_promote(
            target,
            feature,
            promote=promote,
            force=force_promote,
            only_cartridge_paths=outputs.values(),
        ),
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

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error}
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
    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error}
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


def run_source4s_upload(
    project_root: Path,
    source_files: list[Path],
    feature: str | None,
    *,
    embed: bool = False,
    update_cartridge: bool = True,
    force_delta: bool = False,
    ocr_pdf: bool = True,
) -> dict:
    """Upload txt/pdf reference files and link them to the active cartridge."""
    from hive_planner.source4s import list_source4s_files, run_source4s

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error}
    summary = summarize_project(target)
    if not summary.ok:
        return {"ok": False, "error": summary.detail}

    paths = RepoPaths(root=target)
    result = run_source4s(
        paths,
        source_files,
        feature=feature,
        embed=embed,
        update_cartridge=update_cartridge,
        force_delta=force_delta,
        ocr_pdf=ocr_pdf,
    )
    payload = result.to_dict()
    payload["existing_sources"] = list_source4s_files(paths)
    return payload


def cl_runtime_status_label(project_root: Path) -> str:
    from hive_planner.agent_handoff import resolve_agent_handoff_mode, AGENT_HANDOFF_UNIFIED
    from hive_planner.cl_runtime import requires_cursor_plugin, resolve_cl_runtime

    root, error = linked_install_directory(project_root)
    if error or root is None:
        return "\u2014"
    if resolve_agent_handoff_mode(root) != AGENT_HANDOFF_UNIFIED:
        return "\u2014"
    runtime = resolve_cl_runtime(root)
    if requires_cursor_plugin(runtime):
        return "cursor (plugin)"
    if runtime == "external":
        return "external (CLI)"
    return "headless (CLI)"


def run_set_cl_runtime(project_root: Path, runtime: str) -> dict:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED, resolve_agent_handoff_mode
    from hive_planner.cl_runtime import normalize_cl_runtime, set_project_cl_runtime

    target, error = linked_install_directory(project_root)
    if error:
        return {"ok": False, "error": error}
    summary = summarize_project(target)
    if not summary.ok:
        return {"ok": False, "error": summary.detail}
    if resolve_agent_handoff_mode(target) != AGENT_HANDOFF_UNIFIED:
        return {
            "ok": False,
            "error": "CL runtime applies only to unified agent handoff (Spec Kit + Continual Learning).",
            "hints": ["Deploy agent handoff first, then set CL runtime."],
        }
    try:
        set_project_cl_runtime(target, runtime)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    normalized = normalize_cl_runtime(runtime)
    return {
        "ok": True,
        "cl_runtime": normalized,
        "hints": ["Home \u2192 Deploy agent handoff to refresh CL artifacts for the selected runtime."],
    }


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
    cl_runtime: str | None = None,
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
            cl_runtime=cl_runtime,
        )
    except BootstrapError as exc:
        return {"ok": False, "error": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    payload = result.to_dict()
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED, resolve_agent_handoff_mode, validate_unified_handoff

    target = target.resolve()
    mode = resolve_agent_handoff_mode(target)
    if mode == AGENT_HANDOFF_UNIFIED:
        handoff = validate_unified_handoff(target)
        payload["ok"] = handoff.complete
        from hive_planner.cl_runtime import resolve_cl_runtime

        payload["cl_runtime"] = resolve_cl_runtime(target)
        if not handoff.complete:
            payload["error"] = f"Unified handoff incomplete — missing: {', '.join(handoff.missing)}"
            payload["handoff"] = {
                "mode": handoff.mode,
                "complete": handoff.complete,
                "missing": handoff.missing,
                "spec_kit_enabled": handoff.spec_kit_enabled,
                "continual_learning_enabled": handoff.continual_learning_enabled,
            }
    else:
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


def _cursor_cli_js_for_exe(exe: Path) -> Path | None:
    """Return resources/app/out/cli.js next to Cursor.exe when present."""
    cli_js = exe.parent / "resources" / "app" / "out" / "cli.js"
    if cli_js.is_file():
        return cli_js
    return None


def resolve_cursor_cli_launch(cursor_path: str) -> tuple[list[str], dict[str, str]]:
    """Build argv + env that invokes Cursor's Node CLI (supports --classic).

    Cursor 3.x glass/Agents window is the default for many GUI launches. Going through
    cli.js (same as ``cursor.cmd``) lets us pass ``--classic`` so Open in Cursor loads
    the real editor workspace for the linked folder/.code-workspace.
    """
    path = Path(cursor_path)
    name = path.name.lower()
    exe: Path | None = None
    cli_js: Path | None = None

    if name in {"cursor.cmd", "cursor.bat"}:
        # resources/app/bin/cursor.cmd → ../../../Cursor.exe and ../out/cli.js
        exe = (path.parent / ".." / ".." / ".." / "Cursor.exe").resolve()
        cli_js = (path.parent / ".." / "out" / "cli.js").resolve()
    elif name == "cursor.exe":
        exe = path.resolve() if path.is_file() else path
        cli_js = _cursor_cli_js_for_exe(exe)
    elif name == "cursor":
        # Unix launcher script lives beside the app; prefer adjacent Cursor binary + cli.js
        maybe_exe = (path.parent / ".." / ".." / ".." / "Cursor").resolve()
        if maybe_exe.is_file():
            exe = maybe_exe
            cli_js = (path.parent / ".." / "out" / "cli.js").resolve()
            if not cli_js.is_file():
                cli_js = None

    if exe is not None and exe.is_file():
        if cli_js is None or not cli_js.is_file():
            cli_js = _cursor_cli_js_for_exe(exe)
        if cli_js is not None and cli_js.is_file():
            return [str(exe), str(cli_js)], {
                "ELECTRON_RUN_AS_NODE": "1",
                "VSCODE_DEV": "",
            }

    # Windows cannot CreateProcess a .cmd/.bat with shell=False; run via cmd.exe so
    # cursor.cmd can still set ELECTRON_RUN_AS_NODE and forward --classic.
    if sys.platform == "win32" and name in {"cursor.cmd", "cursor.bat"} and path.is_file():
        return ["cmd.exe", "/c", str(path.resolve())], {}

    return [str(path)], {}


def _cursor_launch_prefix_error(prefix: list[str]) -> str | None:
    """Return an error if the launch argv cannot run; None when it looks runnable."""
    if not prefix:
        return "Cursor launch command is empty"
    argv0 = prefix[0]
    lowered = Path(argv0).name.lower()
    if lowered in {"cmd", "cmd.exe"}:
        if shutil.which("cmd.exe") or shutil.which("cmd"):
            return None
        return "cmd.exe not found on PATH"
    if not Path(argv0).is_file():
        return f"Cursor executable not found: {argv0}"
    if len(prefix) >= 2 and str(prefix[1]).lower().endswith("cli.js") and not Path(prefix[1]).is_file():
        return f"Cursor CLI not found: {prefix[1]}"
    return None


def open_in_cursor(project_root: Path, *, config: LauncherConfig | None = None) -> dict:
    raw = Path(project_root)
    if is_code_workspace_file(raw):
        target = raw
        if not target.is_file():
            return {"ok": False, "error": "Workspace file not found"}
        launch_path = target.resolve()
        cwd = str(launch_path.parent)
        entry_kind = "workspace"
    else:
        try:
            launch_path = raw.resolve()
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        if not launch_path.is_dir():
            return {"ok": False, "error": "Directory not found"}
        cwd = str(launch_path)
        entry_kind = "folder"
    cursor_exe = find_cursor_executable(config)
    if not cursor_exe:
        return {
            "ok": False,
            "error": (
                "Cursor not found. Install Cursor, add the cursor CLI to PATH, "
                "or set Cursor executable in Settings."
            ),
        }
    prefix, extra_env = resolve_cursor_cli_launch(cursor_exe)
    prefix_error = _cursor_launch_prefix_error(prefix)
    if prefix_error:
        return {"ok": False, "error": prefix_error}
    # --classic: Cursor 3.x opens the editor workspace instead of Agents/Glass.
    cmd = [*prefix, "--classic", str(launch_path)]
    env = os.environ.copy()
    env.update(extra_env)
    try:
        subprocess.Popen(cmd, cwd=cwd, shell=False, env=env)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    hive_root = resolve_linked_project_root(raw if is_code_workspace_file(raw) else launch_path)
    summary = summarize_project(hive_root) if hive_root else summarize_project(launch_path)
    return {
        "ok": True,
        "path": str(launch_path),
        "cursor": cursor_exe,
        "launch_cmd": cmd,
        "hive_ready": summary.ok,
        "bootstrap_profile": summary.bootstrap_profile,
        "entry_kind": entry_kind,
    }

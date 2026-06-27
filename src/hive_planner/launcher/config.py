from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


def default_config_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "HivePlanner"
    return Path.home() / ".hive-planner"


def default_hive_root() -> Path:
    return Path(__file__).resolve().parents[3]


def normalize_project_path(path: str | Path) -> str:
    raw = str(path).strip()
    if not raw:
        return ""
    return str(Path(raw).resolve())


def linked_project_exists(path: str | Path) -> bool:
    entry = Path(path)
    if entry.suffix.lower() == ".code-workspace":
        return entry.is_file()
    try:
        return entry.resolve().is_dir()
    except OSError:
        return False


def prune_stale_projects(config: LauncherConfig) -> bool:
    """Dedupe linked workspaces and clear a stale active project when its path is missing."""
    changed = False
    valid_recent: list[str] = []
    seen: set[str] = set()
    for entry in config.recent_projects:
        if not entry:
            changed = True
            continue
        normalized = normalize_project_path(entry)
        if not normalized or normalized in seen:
            changed = True
            continue
        seen.add(normalized)
        valid_recent.append(normalized)
    if valid_recent != config.recent_projects:
        config.recent_projects = valid_recent
        changed = True

    if config.active_project and not linked_project_exists(config.active_project):
        config.active_project = ""
        changed = True

    recent_keys = {normalize_project_path(p) for p in config.recent_projects}
    pruned_profiles = {
        normalize_project_path(k): v
        for k, v in config.project_profiles.items()
        if normalize_project_path(k) in recent_keys
    }
    if pruned_profiles != config.project_profiles:
        config.project_profiles = pruned_profiles
        changed = True
    return changed


@dataclass
class LauncherConfig:
    onboarding_complete: bool = False
    hive_planner_root: str = ""
    python_executable: str = "py -3.11"
    cursor_executable: str = ""
    default_profile: str = "full"
    theme: str = "light"
    active_project: str = ""
    recent_projects: list[str] = field(default_factory=list)
    project_profiles: dict[str, str] = field(default_factory=dict)

    def normalized_hive_root(self) -> Path:
        raw = self.hive_planner_root.strip()
        if raw:
            return Path(raw).resolve()
        return default_hive_root().resolve()

    def add_recent_project(self, project_root: Path) -> None:
        from hive_planner.project_profile import resolve_project_profile

        value = normalize_project_path(project_root)
        if not value:
            return
        self.recent_projects = [
            value,
            *(
                p
                for p in self.recent_projects
                if normalize_project_path(p) != value
            ),
        ]
        self.recent_projects = self.recent_projects[:8]
        self.active_project = value
        profile_root = Path(value)
        if profile_root.suffix.lower() == ".code-workspace":
            from hive_planner.launcher.service import workspace_primary_folder

            primary = workspace_primary_folder(profile_root)
            if primary:
                profile_root = primary
        meta = resolve_project_profile(profile_root)
        if meta:
            self.project_profiles[value] = meta.bootstrap_profile
        self.project_profiles = {
            p: self.project_profiles[p]
            for p in self.recent_projects
            if p in self.project_profiles
        }
        for recent in self.recent_projects:
            if recent in self.project_profiles:
                continue
            root = Path(recent)
            if root.suffix.lower() == ".code-workspace":
                from hive_planner.launcher.service import workspace_primary_folder

                primary = workspace_primary_folder(root)
                if primary:
                    root = primary
            inferred = resolve_project_profile(root)
            if inferred:
                self.project_profiles[recent] = inferred.bootstrap_profile

    def remove_recent_project(self, project_root: Path | str) -> bool:
        value = normalize_project_path(project_root)
        if not value:
            return False
        match = next((p for p in self.recent_projects if normalize_project_path(p) == value), None)
        if match is None:
            return False
        self.recent_projects = [p for p in self.recent_projects if normalize_project_path(p) != value]
        self.project_profiles.pop(match, None)
        self.project_profiles.pop(value, None)
        if normalize_project_path(self.active_project) == value:
            self.active_project = ""
        return True


def config_path() -> Path:
    return default_config_dir() / "config.json"


def load_config() -> LauncherConfig:
    from hive_planner.launcher.service import auto_complete_onboarding_if_ready

    path = config_path()
    if not path.is_file():
        cfg = LauncherConfig(hive_planner_root=str(default_hive_root().resolve()))
        auto_complete_onboarding_if_ready(cfg)
        save_config(cfg)
        return cfg
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cfg = LauncherConfig(hive_planner_root=str(default_hive_root().resolve()))
        auto_complete_onboarding_if_ready(cfg)
        save_config(cfg)
        return cfg
    active = normalize_project_path(data.get("active_project") or "")
    recent = [normalize_project_path(p) for p in data.get("recent_projects", []) if str(p).strip()]
    profiles_raw = data.get("project_profiles") or {}
    profiles = {
        normalize_project_path(k): str(v)
        for k, v in profiles_raw.items()
        if str(v) in ("minimal", "full") and str(k).strip()
    }
    cfg = LauncherConfig(
        onboarding_complete=bool(data.get("onboarding_complete", False)),
        hive_planner_root=str(data.get("hive_planner_root") or default_hive_root().resolve()),
        python_executable=str(data.get("python_executable") or "py -3.11"),
        cursor_executable=str(data.get("cursor_executable") or ""),
        default_profile=str(data.get("default_profile") or "full"),
        theme=str(data.get("theme") or "light"),
        active_project=active,
        recent_projects=recent,
        project_profiles=profiles,
    )
    if prune_stale_projects(cfg):
        save_config(cfg)
    elif auto_complete_onboarding_if_ready(cfg):
        save_config(cfg)
    return cfg


def save_config(config: LauncherConfig) -> None:
    path = config_path()
    old_python: str | None = None
    if path.is_file():
        try:
            old_python = str(json.loads(path.read_text(encoding="utf-8")).get("python_executable") or "")
        except (OSError, json.JSONDecodeError):
            old_python = None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
    if old_python is not None and old_python != config.python_executable:
        from hive_planner.launcher.service import clear_python_probe_cache

        clear_python_probe_cache()

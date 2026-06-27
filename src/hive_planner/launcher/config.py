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


@dataclass
class LauncherConfig:
    onboarding_complete: bool = False
    hive_planner_root: str = ""
    python_executable: str = "py -3.11"
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
        self.recent_projects = [value] + [p for p in self.recent_projects if p != value]
        self.recent_projects = self.recent_projects[:8]
        self.active_project = value
        meta = resolve_project_profile(Path(value))
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
            inferred = resolve_project_profile(Path(recent))
            if inferred:
                self.project_profiles[recent] = inferred.bootstrap_profile


def config_path() -> Path:
    return default_config_dir() / "config.json"


def load_config() -> LauncherConfig:
    path = config_path()
    if not path.is_file():
        cfg = LauncherConfig(hive_planner_root=str(default_hive_root().resolve()))
        save_config(cfg)
        return cfg
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cfg = LauncherConfig(hive_planner_root=str(default_hive_root().resolve()))
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
    return LauncherConfig(
        onboarding_complete=bool(data.get("onboarding_complete", False)),
        hive_planner_root=str(data.get("hive_planner_root") or default_hive_root().resolve()),
        python_executable=str(data.get("python_executable") or "py -3.11"),
        default_profile=str(data.get("default_profile") or "full"),
        theme=str(data.get("theme") or "light"),
        active_project=active,
        recent_projects=recent,
        project_profiles=profiles,
    )


def save_config(config: LauncherConfig) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")

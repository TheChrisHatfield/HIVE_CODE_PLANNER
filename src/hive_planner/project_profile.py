from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_META_DIR = ".hive"
PROJECT_META_FILE = ".hive/project.json"
SCHEMA_VERSION = 1
BOOTSTRAP_PROFILES = frozenset({"minimal", "full"})


@dataclass
class ProjectProfile:
    bootstrap_profile: str
    project_name: str
    schema_version: int = SCHEMA_VERSION
    hive_planner_version: str | None = None
    created_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def project_meta_path(project_root: Path) -> Path:
    return project_root.resolve() / PROJECT_META_FILE


def infer_bootstrap_profile(project_root: Path) -> str:
    root = project_root.resolve()
    if (root / "pyproject.toml").is_file() and (root / "START_HERE.md").is_file():
        return "full"
    return "minimal"


def read_project_profile(project_root: Path) -> ProjectProfile | None:
    path = project_meta_path(project_root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    profile = str(data.get("bootstrap_profile") or "").strip()
    if profile not in BOOTSTRAP_PROFILES:
        return None
    name = str(data.get("project_name") or project_root.name).strip() or project_root.name
    try:
        schema_version = int(data.get("schema_version") or SCHEMA_VERSION)
    except (TypeError, ValueError):
        schema_version = SCHEMA_VERSION
    return ProjectProfile(
        bootstrap_profile=profile,
        project_name=name,
        schema_version=schema_version,
        hive_planner_version=(str(data["hive_planner_version"]) if data.get("hive_planner_version") else None),
        created_at=(str(data["created_at"]) if data.get("created_at") else None),
    )


def resolve_project_profile(project_root: Path) -> ProjectProfile | None:
    root = project_root.resolve()
    if not root.is_dir():
        return None
    meta = read_project_profile(root)
    if meta:
        return meta
    if not (root / "START_HERE.md").is_file():
        return None
    return ProjectProfile(
        bootstrap_profile=infer_bootstrap_profile(root),
        project_name=root.name,
    )


def write_project_profile(
    project_root: Path,
    *,
    profile: str,
    project_name: str,
    hive_planner_version: str | None = None,
) -> Path:
    if profile not in BOOTSTRAP_PROFILES:
        raise ValueError(f"Unknown bootstrap profile: {profile}")
    root = project_root.resolve()
    meta_dir = root / PROJECT_META_DIR
    meta_dir.mkdir(parents=True, exist_ok=True)
    payload = ProjectProfile(
        bootstrap_profile=profile,
        project_name=project_name,
        hive_planner_version=hive_planner_version,
        created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    path = project_meta_path(root)
    path.write_text(json.dumps(payload.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path

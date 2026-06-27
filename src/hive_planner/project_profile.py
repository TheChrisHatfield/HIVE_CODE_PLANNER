from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_META_DIR = ".hive"
PROJECT_META_FILE = ".hive/project.json"
SCHEMA_VERSION = 3
BOOTSTRAP_PROFILES = frozenset({"minimal", "full"})


@dataclass
class ProjectIntegrations:
    spec_kit_enabled: bool
    continual_learning_enabled: bool
    agent_handoff_mode: str = "off"


@dataclass
class ProjectProfile:
    bootstrap_profile: str
    project_name: str
    schema_version: int = SCHEMA_VERSION
    hive_planner_version: str | None = None
    created_at: str | None = None
    agent_handoff_mode: str | None = None
    spec_kit_enabled: bool | None = None
    continual_learning_enabled: bool | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def project_meta_path(project_root: Path) -> Path:
    return project_root.resolve() / PROJECT_META_FILE


def infer_bootstrap_profile(project_root: Path) -> str:
    root = project_root.resolve()
    if (root / "pyproject.toml").is_file() and (root / "START_HERE.md").is_file():
        return "full"
    return "minimal"


def infer_spec_kit_enabled(project_root: Path) -> bool:
    root = project_root.resolve()
    specs = root / "docs" / "specs"
    if specs.is_dir():
        for feature_dir in specs.iterdir():
            if feature_dir.is_dir() and (feature_dir / "spec.md").is_file():
                return True
    return (root / "spec-kit-agent-integration.md").is_file()


def resolve_project_integrations(project_root: Path) -> ProjectIntegrations:
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED, integrations_from_mode, resolve_agent_handoff_mode

    mode = resolve_agent_handoff_mode(project_root)
    spec_kit, continual_learning = integrations_from_mode(mode)
    return ProjectIntegrations(
        spec_kit_enabled=spec_kit,
        continual_learning_enabled=continual_learning,
        agent_handoff_mode=mode,
    )


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
    spec_kit = data["spec_kit_enabled"] if "spec_kit_enabled" in data else None
    continual_learning = data["continual_learning_enabled"] if "continual_learning_enabled" in data else None
    agent_handoff = str(data["agent_handoff_mode"]).strip().lower() if data.get("agent_handoff_mode") else None
    if spec_kit is not None:
        spec_kit = bool(spec_kit)
    if continual_learning is not None:
        continual_learning = bool(continual_learning)
    return ProjectProfile(
        bootstrap_profile=profile,
        project_name=name,
        schema_version=schema_version,
        hive_planner_version=(str(data["hive_planner_version"]) if data.get("hive_planner_version") else None),
        created_at=(str(data["created_at"]) if data.get("created_at") else None),
        agent_handoff_mode=agent_handoff,
        spec_kit_enabled=spec_kit,
        continual_learning_enabled=continual_learning,
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
    agent_handoff_mode: str | None = None,
    spec_kit_enabled: bool | None = None,
    continual_learning_enabled: bool | None = None,
) -> Path:
    from hive_planner.agent_handoff import AGENT_HANDOFF_OFF, AGENT_HANDOFF_UNIFIED, integrations_from_mode, normalize_agent_handoff_mode

    if profile not in BOOTSTRAP_PROFILES:
        raise ValueError(f"Unknown bootstrap profile: {profile}")
    if agent_handoff_mode is not None:
        mode = normalize_agent_handoff_mode(agent_handoff_mode, default=AGENT_HANDOFF_OFF)
        spec_kit_enabled, continual_learning_enabled = integrations_from_mode(mode)
    elif spec_kit_enabled is not None or continual_learning_enabled is not None:
        spec_on = bool(spec_kit_enabled)
        cl_on = bool(continual_learning_enabled) if continual_learning_enabled is not None else spec_on
        if cl_on and not spec_on:
            cl_on = False
        mode = AGENT_HANDOFF_UNIFIED if (spec_on and cl_on) else (AGENT_HANDOFF_UNIFIED if spec_on else AGENT_HANDOFF_OFF)
        if spec_on and not cl_on:
            mode = AGENT_HANDOFF_UNIFIED
            cl_on = True
        spec_kit_enabled = spec_on or cl_on
        continual_learning_enabled = cl_on
        agent_handoff_mode = mode
    else:
        mode = AGENT_HANDOFF_OFF
        spec_kit_enabled = False
        continual_learning_enabled = False
        agent_handoff_mode = mode
    root = project_root.resolve()
    meta_dir = root / PROJECT_META_DIR
    meta_dir.mkdir(parents=True, exist_ok=True)
    existing = read_project_profile(root)
    created_at = existing.created_at if existing and existing.created_at else datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload = ProjectProfile(
        bootstrap_profile=profile,
        project_name=project_name,
        hive_planner_version=hive_planner_version if hive_planner_version is not None else (existing.hive_planner_version if existing else None),
        created_at=created_at,
        agent_handoff_mode=agent_handoff_mode,
        spec_kit_enabled=spec_kit_enabled,
        continual_learning_enabled=continual_learning_enabled,
    )
    path = project_meta_path(root)
    path.write_text(json.dumps(payload.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def delete_project_profile(project_root: Path) -> tuple[bool, str]:
    """Permanently remove .hive/project.json (and empty .hive folder)."""
    root = project_root.resolve()
    meta_path = project_meta_path(root)
    meta_dir = root / PROJECT_META_DIR
    if not meta_path.is_file() and not meta_dir.is_dir():
        return False, "No Hive profile metadata found in this project."
    try:
        if meta_path.is_file():
            meta_path.unlink()
        if meta_dir.is_dir() and not any(meta_dir.iterdir()):
            meta_dir.rmdir()
    except OSError as exc:
        return False, str(exc)
    return True, "Hive profile metadata deleted."

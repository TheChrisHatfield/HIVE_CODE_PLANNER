"""Unified Spec Kit + Continual Learning deployment profile (symbiotic pair)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hive_planner.config import RepoPaths

AGENT_HANDOFF_OFF = "off"
AGENT_HANDOFF_UNIFIED = "unified"
AGENT_HANDOFF_MODES = frozenset({AGENT_HANDOFF_OFF, AGENT_HANDOFF_UNIFIED})


@dataclass
class AgentHandoffStatus:
    mode: str
    spec_kit_enabled: bool
    continual_learning_enabled: bool
    complete: bool
    missing: list[str]


def normalize_agent_handoff_mode(value: str | None, *, default: str = AGENT_HANDOFF_UNIFIED) -> str:
    mode = str(value or default).strip().lower()
    if mode in AGENT_HANDOFF_MODES:
        return mode
    if mode in {"on", "true", "yes", "both", "symbiotic", "unified"}:
        return AGENT_HANDOFF_UNIFIED
    if mode in {"false", "no", "none"}:
        return AGENT_HANDOFF_OFF
    return default


def integrations_from_mode(mode: str) -> tuple[bool, bool]:
    """Spec Kit and Continual Learning deploy together in unified mode."""
    unified = normalize_agent_handoff_mode(mode) == AGENT_HANDOFF_UNIFIED
    return unified, unified


def resolve_agent_handoff_mode(project_root: Path) -> str:
    from hive_planner.project_profile import infer_spec_kit_enabled, read_project_profile

    meta = read_project_profile(project_root)
    if meta and meta.agent_handoff_mode:
        return normalize_agent_handoff_mode(meta.agent_handoff_mode, default=AGENT_HANDOFF_OFF)
    if meta:
        if meta.spec_kit_enabled and meta.continual_learning_enabled:
            return AGENT_HANDOFF_UNIFIED
        if meta.spec_kit_enabled:
            return AGENT_HANDOFF_UNIFIED
        if meta.spec_kit_enabled is False and meta.continual_learning_enabled is False:
            return AGENT_HANDOFF_OFF
        if meta.spec_kit_enabled is False:
            return AGENT_HANDOFF_OFF
    if infer_spec_kit_enabled(project_root):
        return AGENT_HANDOFF_UNIFIED
    return AGENT_HANDOFF_OFF


def unified_handoff_artifacts(project_root: Path) -> list[str]:
    root = project_root.resolve()
    feature = "example-feature"
    return [
        f"docs/specs/{feature}/spec.md",
        f"docs/specs/{feature}/plan.md",
        f"docs/specs/{feature}/tasks.md",
        f"docs/delta/20_micro/{feature}.md",
        "docs/proposals/candidates-template.md",
        "docs/cl-spec-integration.md",
        "spec-kit-agent-integration.md",
    ]


def validate_unified_handoff(project_root: Path) -> AgentHandoffStatus:
    mode = resolve_agent_handoff_mode(project_root)
    spec_kit, continual_learning = integrations_from_mode(mode)
    if mode != AGENT_HANDOFF_UNIFIED:
        return AgentHandoffStatus(
            mode=mode,
            spec_kit_enabled=spec_kit,
            continual_learning_enabled=continual_learning,
            complete=True,
            missing=[],
        )
    root = project_root.resolve()
    missing = [rel for rel in unified_handoff_artifacts(root) if not (root / rel).is_file()]
    return AgentHandoffStatus(
        mode=mode,
        spec_kit_enabled=True,
        continual_learning_enabled=True,
        complete=not missing,
        missing=missing,
    )


def deploy_unified_agent_handoff(
    source_paths: RepoPaths,
    target: Path,
    *,
    project_name: str | None = None,
    force: bool = False,
) -> tuple[list[str], list[str]]:
    """Scaffold the symbiotic Spec Kit + Continual Learning bundle into a project."""
    from hive_planner.bootstrap import deploy_agent_handoff_scaffold

    return deploy_agent_handoff_scaffold(
        source_paths,
        target,
        project_name=project_name,
        force=force,
    )


def apply_agent_handoff_mode(
    project_root: Path,
    mode: str,
    *,
    hive_planner_version: str | None = None,
) -> Path:
    from hive_planner.project_profile import infer_bootstrap_profile, read_project_profile, resolve_project_profile, write_project_profile

    root = project_root.resolve()
    meta = read_project_profile(root)
    resolved = resolve_project_profile(root)
    name = meta.project_name if meta else (resolved.project_name if resolved else root.name)
    profile = (
        meta.bootstrap_profile
        if meta
        else (resolved.bootstrap_profile if resolved else infer_bootstrap_profile(root))
    )
    normalized = normalize_agent_handoff_mode(mode)
    spec_kit, continual_learning = integrations_from_mode(normalized)
    return write_project_profile(
        root,
        profile=profile,
        project_name=name,
        hive_planner_version=hive_planner_version or (meta.hive_planner_version if meta else None),
        agent_handoff_mode=normalized,
        spec_kit_enabled=spec_kit,
        continual_learning_enabled=continual_learning,
    )

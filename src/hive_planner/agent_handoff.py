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
        ".cursor/rules/integration-wiring-audit.mdc",
        ".cursor/rules/cl-spec-integration.mdc",
        ".hive/upstream-pins.json",
        ".hive/spec-kit/README.md",
        ".hive/spec-kit/WORKFLOW.md",
        ".hive/spec-kit/templates/spec-template.md",
        ".hive/spec-kit/templates/tasks-template.md",
        ".cursor/plugins/hive-continual-learning/README.md",
        ".cursor/plugins/hive-continual-learning/WORKFLOW.md",
        ".cursor/plugins/hive-continual-learning/agents/agents-memory-updater.md",
        ".cursor/plugins/hive-continual-learning/skills/continual-learning/SKILL.md",
        ".cursor/plugins/hive-continual-learning/.cursor-plugin/plugin.json",
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
    from hive_planner.vendor_sync import PROJECT_PINS_REL, overlay_issues_as_missing, read_project_pins

    pins_path = root / PROJECT_PINS_REL
    pins = read_project_pins(root)
    if pins_path.is_file() and pins is None:
        if PROJECT_PINS_REL not in missing:
            missing.append(PROJECT_PINS_REL)
    for rel in overlay_issues_as_missing(root, pins):
        if rel not in missing:
            missing.append(rel)
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


MARKETPLACE_CL_REL = ".cursor/plugins/continual-learning"


@dataclass
class LegacyDeploymentFinding:
    code: str
    severity: str
    detail: str
    repair: str | None = None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "detail": self.detail,
            "repair": self.repair,
        }


@dataclass
class LegacyDeploymentReport:
    findings: list[LegacyDeploymentFinding]

    @property
    def ok(self) -> bool:
        return not any(item.severity == "warn" for item in self.findings)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "findings": [item.to_dict() for item in self.findings],
        }


def _plugin_tree_present(plugin_root: Path) -> bool:
    return (
        (plugin_root / ".cursor-plugin" / "plugin.json").is_file()
        or (plugin_root / "skills" / "continual-learning" / "SKILL.md").is_file()
    )


def scan_legacy_deployment(project_root: Path) -> LegacyDeploymentReport:
    """Detect pre-unified or marketplace-only handoff artifacts in a Hive project."""
    from hive_planner.project_profile import infer_spec_kit_enabled, read_project_profile
    from hive_planner.vendor_sync import CL_OVERLAY_REL, PROJECT_PINS_REL, SPEC_KIT_OVERLAY_REL

    root = project_root.resolve()
    findings: list[LegacyDeploymentFinding] = []

    marketplace_cl = root / MARKETPLACE_CL_REL
    hive_cl = root / CL_OVERLAY_REL
    marketplace_installed = _plugin_tree_present(marketplace_cl)
    hive_installed = _plugin_tree_present(hive_cl)

    if marketplace_installed and hive_installed:
        findings.append(
            LegacyDeploymentFinding(
                code="dual_cl_install",
                severity="warn",
                detail="Both marketplace continual-learning and hive-continual-learning plugins are present.",
                repair="Disable or remove marketplace /add-plugin continual-learning; use hive-continual-learning only.",
            )
        )
    elif marketplace_installed:
        findings.append(
            LegacyDeploymentFinding(
                code="marketplace_cl_only",
                severity="warn",
                detail=f"Marketplace Continual Learning plugin found at {MARKETPLACE_CL_REL}/.",
                repair="Home → Deploy agent handoff (installs vendored hive-continual-learning).",
            )
        )

    starter_kit_doc = (root / "spec-kit-agent-integration.md").is_file()
    pins_path = root / PROJECT_PINS_REL
    spec_kit_overlay = root / SPEC_KIT_OVERLAY_REL
    if starter_kit_doc and not pins_path.is_file():
        findings.append(
            LegacyDeploymentFinding(
                code="missing_upstream_pins",
                severity="warn",
                detail="spec-kit-agent-integration.md present but .hive/upstream-pins.json is missing (pre-Stage 9 layout).",
                repair="Home → Deploy agent handoff to write pins and vendored overlays.",
            )
        )
    if starter_kit_doc and not (spec_kit_overlay / "WORKFLOW.md").is_file():
        findings.append(
            LegacyDeploymentFinding(
                code="starter_kit_only_layout",
                severity="warn",
                detail="Starter-kit Spec Kit guide present but .hive/spec-kit/ vendored overlay is missing or incomplete.",
                repair="Home → Deploy agent handoff to install .hive/spec-kit/ templates.",
            )
        )

    mode = resolve_agent_handoff_mode(root)
    meta = read_project_profile(root)
    if mode != AGENT_HANDOFF_UNIFIED and infer_spec_kit_enabled(root):
        profile_mode = meta.agent_handoff_mode if meta and meta.agent_handoff_mode else "inferred"
        findings.append(
            LegacyDeploymentFinding(
                code="handoff_mode_not_unified",
                severity="warn",
                detail=f"Spec Kit artifacts detected but agent handoff mode is {profile_mode!r}, not unified.",
                repair="Home → Deploy agent handoff to enable unified Spec Kit + Continual Learning.",
            )
        )

    agents_path = root / "AGENTS.md"
    if agents_path.is_file():
        try:
            agents_text = agents_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            agents_text = ""
        if "## Learned Workspace Facts" in agents_text:
            findings.append(
                LegacyDeploymentFinding(
                    code="learned_workspace_facts",
                    severity="info",
                    detail="AGENTS.md still uses ## Learned Workspace Facts (upstream CL section name).",
                    repair="Merge into ## Durable Workspace Facts when running agents-apply or CL memory update.",
                )
            )

    if mode == AGENT_HANDOFF_UNIFIED:
        status = validate_unified_handoff(root)
        if not status.complete:
            findings.append(
                LegacyDeploymentFinding(
                    code="unified_handoff_incomplete",
                    severity="warn",
                    detail=f"Unified handoff enabled but {len(status.missing)} required artifact(s) missing.",
                    repair="Home → Verify vendor pins, then Deploy agent handoff if overlays are stale.",
                )
            )

    return LegacyDeploymentReport(findings=findings)


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

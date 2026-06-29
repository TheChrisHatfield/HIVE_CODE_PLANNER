"""Migrate marketplace Continual Learning data to Hive vendored CL."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from hive_planner.agent_handoff import MARKETPLACE_CL_REL
from hive_planner.agents_memory import (
    EDITABLE_SECTION,
    _match_section,
    _normalize_bullet,
    _section_bullets,
    _section_render_order,
    lint_agents_md,
    parse_sections,
    _preamble_lines,
)
from hive_planner.config import RepoPaths

LEGACY_WORKSPACE_FACTS = "Learned Workspace Facts"
CL_MIGRATION_REL = ".hive/cl-migration.json"
CL_SOURCE_VENDORED = "vendored"
CL_SOURCE_MARKETPLACE = "marketplace"


class ClMigrationError(Exception):
    """Continual Learning migration failed."""


@dataclass
class ClMigrationReport:
    ok: bool
    dry_run: bool
    merged_bullets: int = 0
    removed_marketplace_plugin: bool = False
    agents_updated: bool = False
    cl_source: str | None = None
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "dry_run": self.dry_run,
            "merged_bullets": self.merged_bullets,
            "removed_marketplace_plugin": self.removed_marketplace_plugin,
            "agents_updated": self.agents_updated,
            "cl_source": self.cl_source,
            "actions": self.actions,
            "warnings": self.warnings,
        }


def _plugin_name(plugin_root: Path) -> str | None:
    plugin_json = plugin_root / ".cursor-plugin" / "plugin.json"
    if not plugin_json.is_file():
        return None
    try:
        data = json.loads(plugin_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    name = data.get("name")
    return str(name).strip() if name else None


def marketplace_plugin_tree_present(project_root: Path) -> bool:
    from hive_planner.agent_handoff import _plugin_tree_present

    root = project_root.resolve() / MARKETPLACE_CL_REL
    return _plugin_tree_present(root)


def marketplace_cl_installed(project_root: Path) -> bool:
    from hive_planner.agent_handoff import _plugin_tree_present

    root = project_root.resolve() / MARKETPLACE_CL_REL
    return _plugin_tree_present(root) and _plugin_name(root) in {None, "continual-learning"}


def hive_cl_installed(project_root: Path) -> bool:
    from hive_planner.agent_handoff import _plugin_tree_present
    from hive_planner.vendor_sync import CL_OVERLAY_REL

    root = project_root.resolve() / CL_OVERLAY_REL
    return _plugin_tree_present(root)


def merge_learned_workspace_facts(agents_text: str) -> tuple[str, int]:
    """Move bullets from ## Learned Workspace Facts into ## Durable Workspace Facts."""
    sections = parse_sections(agents_text)
    legacy_key = _match_section(sections, LEGACY_WORKSPACE_FACTS)
    if not legacy_key:
        return agents_text, 0

    legacy_bullets = [bullet for _, bullet in _section_bullets(sections[legacy_key])]
    if not legacy_bullets:
        sections.pop(legacy_key, None)
        return _render_agents_sections(agents_text, sections), 0

    durable_key = _match_section(sections, EDITABLE_SECTION) or EDITABLE_SECTION
    durable_body = sections.get(durable_key, "").strip()
    existing = {
        _normalize_bullet(bullet)
        for title, body in sections.items()
        if title != legacy_key
        for _, bullet in _section_bullets(body)
    }

    merged: list[str] = []
    for bullet in legacy_bullets:
        normalized = _normalize_bullet(bullet)
        if normalized and normalized not in existing:
            merged.append(bullet)
            existing.add(normalized)

    if merged:
        merged_lines = "\n".join(f"- {bullet}" for bullet in merged)
        sections[durable_key] = f"{durable_body}\n{merged_lines}".strip() if durable_body else merged_lines

    sections.pop(legacy_key, None)
    return _render_agents_sections(agents_text, sections), len(merged)


def _render_agents_sections(agents_text: str, sections: dict[str, str]) -> str:
    preamble = _preamble_lines(agents_text)
    durable_key = _match_section(sections, EDITABLE_SECTION)
    out = list(preamble)
    if out and out[-1].strip():
        out.append("")
    for heading in _section_render_order(sections, insert_key=None if durable_key else EDITABLE_SECTION):
        body = sections[heading]
        out.append(f"## {heading}")
        out.append("")
        if body:
            out.append(body)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def remove_marketplace_cl_plugin(project_root: Path) -> bool:
    """Remove project-local marketplace plugin tree when safe."""
    plugin_root = project_root.resolve() / MARKETPLACE_CL_REL
    if not plugin_root.is_dir():
        return False
    name = _plugin_name(plugin_root)
    if name not in {None, "continual-learning"}:
        raise ClMigrationError(
            f"Refusing to remove {MARKETPLACE_CL_REL}: unexpected plugin name {name!r}"
        )
    shutil.rmtree(plugin_root)
    return True


def _write_migration_record(project_root: Path, report: ClMigrationReport) -> None:
    path = project_root.resolve() / CL_MIGRATION_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "migrated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "merged_bullets": report.merged_bullets,
        "removed_marketplace_plugin": report.removed_marketplace_plugin,
        "cl_source": report.cl_source,
        "dry_run": report.dry_run,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def migrate_marketplace_cl(
    paths: RepoPaths,
    *,
    remove_marketplace_plugin: bool = False,
    dry_run: bool = False,
) -> ClMigrationReport:
    """Transfer marketplace CL memory into Hive format and optionally remove marketplace plugin."""
    root = paths.root.resolve()
    report = ClMigrationReport(ok=True, dry_run=dry_run)
    from hive_planner.cl_runtime import requires_cursor_plugin, resolve_cl_runtime

    runtime = resolve_cl_runtime(root)
    cursor_runtime = requires_cursor_plugin(runtime)

    if cursor_runtime and not hive_cl_installed(root):
        report.ok = False
        report.warnings.append(
            "Hive continual-learning plugin missing — run Deploy agent handoff before migrating."
        )
        return report

    agents_path = paths.root / "AGENTS.md"
    original = ""
    merged_text = ""
    count = 0
    if agents_path.is_file():
        original = agents_path.read_text(encoding="utf-8", errors="replace")
        merged_text, count = merge_learned_workspace_facts(original)
    else:
        report.warnings.append("AGENTS.md not found — skipping Learned Workspace Facts merge.")
    report.merged_bullets = count

    if count:
        report.actions.append(f"Merged {count} bullet(s) from ## {LEGACY_WORKSPACE_FACTS} into ## {EDITABLE_SECTION}")
    elif LEGACY_WORKSPACE_FACTS in original:
        report.actions.append(f"Removed empty ## {LEGACY_WORKSPACE_FACTS} section")

    if merged_text != original and agents_path.is_file():
        report.agents_updated = True
        if not dry_run:
            agents_path.write_text(merged_text, encoding="utf-8")
            lint = lint_agents_md(paths, agents_path=agents_path)
            if not lint.ok:
                agents_path.write_text(original, encoding="utf-8")
                report.ok = False
                report.agents_updated = False
                errors = [issue.message for issue in lint.issues if issue.severity == "error"]
                report.warnings.append(f"AGENTS.md lint failed after merge — rolled back: {'; '.join(errors)}")

    if marketplace_plugin_tree_present(root):
        if marketplace_cl_installed(root):
            if remove_marketplace_plugin:
                report.actions.append(f"Remove marketplace plugin at {MARKETPLACE_CL_REL}/")
                if not dry_run:
                    try:
                        report.removed_marketplace_plugin = remove_marketplace_cl_plugin(root)
                    except ClMigrationError as exc:
                        if report.agents_updated and agents_path.is_file():
                            agents_path.write_text(original, encoding="utf-8")
                            report.agents_updated = False
                        report.ok = False
                        report.warnings.append(str(exc))
            elif cursor_runtime:
                report.warnings.append(
                    f"Marketplace plugin still present at {MARKETPLACE_CL_REL}/ — "
                    "disable in Cursor or re-run with --remove-marketplace-plugin."
                )
            else:
                report.warnings.append(
                    f"Cursor plugin tree still present at {MARKETPLACE_CL_REL}/ — "
                    "re-run with --remove-marketplace-plugin or remove manually."
                )
        elif not cursor_runtime:
            report.warnings.append(
                f"Cursor plugin tree at {MARKETPLACE_CL_REL}/ detected but cl_runtime is {runtime!r} — "
                "remove manually or re-run with --remove-marketplace-plugin."
            )
        else:
            plugin_name = _plugin_name(root / MARKETPLACE_CL_REL)
            report.warnings.append(
                f"Plugin tree at {MARKETPLACE_CL_REL}/ has unexpected name {plugin_name!r} — "
                "manual review required before removal."
            )
    elif "## Learned Workspace Facts" not in merged_text and agents_path.is_file():
        report.actions.append("No marketplace plugin directory detected")

    if marketplace_plugin_tree_present(root) and not dry_run and cursor_runtime:
        report.ok = False
    elif not dry_run and report.removed_marketplace_plugin:
        report.ok = True

    lint_failed = any("lint failed" in w for w in report.warnings)
    if not dry_run and report.ok and cursor_runtime and not lint_failed:
        from hive_planner.project_profile import set_project_cl_source

        set_project_cl_source(root, CL_SOURCE_VENDORED)
        report.cl_source = CL_SOURCE_VENDORED

    if not dry_run and report.ok and not lint_failed:
        _write_migration_record(root, report)

    hook_state = root / ".cursor" / "hooks" / "state" / "continual-learning-index.json"
    if hook_state.is_file():
        report.actions.append("Preserved existing .cursor/hooks/state/continual-learning-index.json (shared with Hive CL)")

    return report


def ci_cl_install_step(project_root: Path) -> tuple[bool, str]:
    """CI gate: unified projects must not use marketplace-only or dual CL installs."""
    from hive_planner.agent_handoff import scan_legacy_deployment
    from hive_planner.project_profile import resolve_project_integrations
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED

    integrations = resolve_project_integrations(project_root)
    if integrations.agent_handoff_mode != AGENT_HANDOFF_UNIFIED:
        return True, "skipped (not unified handoff)"

    from hive_planner.cl_runtime import requires_cursor_plugin, resolve_cl_runtime

    runtime = resolve_cl_runtime(project_root)
    findings = {item.code: item for item in scan_legacy_deployment(project_root).findings}
    if not requires_cursor_plugin(runtime):
        from hive_planner.cl_runtime import HEADLESS_CL_WORKFLOW_REL

        if not (project_root.resolve() / HEADLESS_CL_WORKFLOW_REL).is_file():
            return (
                False,
                f"missing {HEADLESS_CL_WORKFLOW_REL} — deploy agent handoff with --cl-runtime {runtime}",
            )
        if "learned_workspace_facts" in findings:
            return False, findings["learned_workspace_facts"].detail + " — run: py -3.11 -m hive_planner cl-migrate"
        if marketplace_cl_installed(root):
            cmd = "py -3.11 -m hive_planner cl-migrate"
            if hive_cl_installed(root):
                cmd += " --remove-marketplace-plugin"
            return (
                False,
                f"Marketplace Continual Learning plugin present on headless runtime ({runtime!r}) — run: {cmd}",
            )
        return True, f"continual learning runtime={runtime} (headless — no Cursor plugin required)"
    if "dual_cl_install" in findings:
        return False, findings["dual_cl_install"].detail + " — run: py -3.11 -m hive_planner cl-migrate --remove-marketplace-plugin"
    if "marketplace_cl_only" in findings:
        return False, findings["marketplace_cl_only"].detail + " — run: py -3.11 -m hive_planner cl-migrate"
    if "learned_workspace_facts" in findings:
        return False, findings["learned_workspace_facts"].detail + " — run: py -3.11 -m hive_planner cl-migrate"
    return True, "vendored hive-continual-learning (no marketplace conflict)"

from __future__ import annotations

import json
import re
from pathlib import Path

from hive_planner.agents_memory import EDITABLE_SECTION, parse_sections
from hive_planner.config import RepoPaths, validate_feature_id
from hive_planner.delta_emit import (
    DRAFT_MARKER,
    MANUAL_MARKER,
    _auto_sync_banner,
    _first_content_line,
    _should_skip_existing,
    _strip_leading_banner,
)

REQUIRED_PACK_FILES = (
    "manifest.json",
    "research-summary.md",
    "holistic.md",
    "macro.md",
    "memory.md",
    "source-context.md",
    "mappings/source-map.json",
)

RULE_SEED_DRAFT_BANNER = "<!-- DRAFT: rule seed — review before copying to .cursor/rules/*.mdc -->"


def _yaml_double_quoted(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _extract_section(body: str, heading: str) -> str:
    pattern = re.compile(rf"^## {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(body)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^## ", body[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(body)
    return body[start:end].strip()


def build_source_map(feature: str) -> dict:
    return {
        "schema_version": "source-map.v1",
        "feature": feature,
        "_auto_sync": True,
        "mappings": [
            {"cartridge": "cartridge/holistic.md", "delta": "docs/delta/00_holistic.md", "layer": "holistic"},
            {"cartridge": "cartridge/macro.md", "delta": "docs/delta/10_macro.md", "layer": "macro"},
            {
                "cartridge": f"cartridge/micro/{feature}.md",
                "delta": f"docs/delta/20_micro/{feature}.md",
                "layer": "micro",
            },
            {
                "cartridge": f"cartridge/specs/{feature}.specseed.md",
                "delta": f"docs/specs/{feature}/spec.md",
                "layer": "spec_seed",
            },
            {"cartridge": "cartridge/memory.md", "delta": "AGENTS.md", "layer": "memory"},
            {
                "cartridge": f"cartridge/rules/{feature}.mdc.seed",
                "delta": f"docs/delta/20_micro/{feature}.md",
                "layer": "cursor_rule_seed",
            },
            {"cartridge": "cartridge/source-context.md", "delta": "context-library/indexes", "layer": "tertiary"},
        ],
    }


def _build_research_summary(paths: RepoPaths, feature: str) -> str:
    micro_path = paths.root / "docs" / "delta" / "20_micro" / f"{feature}.md"
    spec_path = paths.root / "docs" / "specs" / feature / "spec.md"
    micro_body = micro_path.read_text(encoding="utf-8") if micro_path.exists() else ""
    spec_body = spec_path.read_text(encoding="utf-8") if spec_path.exists() else ""

    holistic = _extract_section(micro_body, "Holistic Link") or "See Delta holistic context."
    scope = _extract_section(micro_body, "Scope") or "See micro brief."
    validation = _extract_section(micro_body, "Validation") or "Run pytest and feature validation commands."
    what = _extract_section(spec_body, "What") or f"Cartridge context pack for `{feature}`."

    return "\n".join(
        [
            "# Research Summary",
            "",
            f"**Feature:** `{feature}`",
            "",
            "## Problem statement",
            "",
            what,
            "",
            "## Key findings",
            "",
            holistic,
            "",
            "## Constraints",
            "",
            scope,
            "",
            "## Risks",
            "",
            "- Draft cartridge files require human review before Delta promotion.",
            "",
            "## Open questions",
            "",
            validation,
            "",
        ]
    )


def _build_specseed_body(feature: str, spec_body: str) -> str:
    return "\n".join(
        [
            f"# Spec seed: {feature}",
            "",
            spec_body.strip(),
            "",
        ]
    )


def _extract_hook_line(micro_body: str) -> str:
    match = re.search(r"^\*\*Hook:\*\*\s*(.+)$", micro_body, re.MULTILINE)
    return match.group(1).strip() if match else "`cursor.rules`"


def _macro_excerpt(macro_body: str, *, max_lines: int = 12) -> str:
    body = _strip_leading_banner(macro_body).strip()
    if not body:
        return ""
    lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("# ") and lines:
            break
        if line.strip():
            lines.append(line)
        if len(lines) >= max_lines:
            break
    return "\n".join(lines).strip()


def build_rule_seed_body(paths: RepoPaths, feature: str) -> str:
    macro_path = paths.root / "docs" / "delta" / "10_macro.md"
    micro_path = paths.root / "docs" / "delta" / "20_micro" / f"{feature}.md"
    micro_body = micro_path.read_text(encoding="utf-8") if micro_path.exists() else ""
    macro_body = macro_path.read_text(encoding="utf-8") if macro_path.exists() else ""

    hook_line = _extract_hook_line(micro_body)
    feature_name = _extract_section(micro_body, "Feature Name") or feature
    scope = _extract_section(micro_body, "Scope") or "See micro brief."
    acceptance = _extract_section(micro_body, "Acceptance Criteria") or "See spec acceptance criteria."
    validation = _extract_section(micro_body, "Validation") or "Run feature validation commands."
    macro_summary = _macro_excerpt(macro_body) or "See Delta macro layer."
    description = f"Feature guardrails for {feature} (review seed — not auto-applied)"

    return "\n".join(
        [
            "---",
            f"description: {_yaml_double_quoted(description)}",
            "alwaysApply: false",
            "---",
            "",
            f"# {feature_name}",
            "",
            f"**Hook:** {hook_line}",
            "",
            "> Review this seed before copying to "
            f"`.cursor/rules/{feature}.mdc`. "
            "Remove this block and set `alwaysApply` as needed.",
            "",
            "## Architecture context",
            "",
            macro_summary,
            "",
            "## Scope",
            "",
            scope,
            "",
            "## Acceptance",
            "",
            acceptance,
            "",
            "## Validation",
            "",
            validation,
            "",
        ]
    )


def _should_skip_rules_seed(target: Path, *, force: bool) -> tuple[bool, str]:
    if force or not target.exists():
        return False, ""
    content = target.read_text(encoding="utf-8")
    first_line = _first_content_line(content)
    if first_line.startswith(MANUAL_MARKER) or MANUAL_MARKER in content.splitlines()[0:3]:
        return True, "manual banner"
    if first_line.startswith(DRAFT_MARKER) or first_line.startswith(RULE_SEED_DRAFT_BANNER):
        return False, ""
    return True, "exists without draft banner (treat as reviewed/manual)"


def emit_rules_seed(
    paths: RepoPaths,
    feature: str,
    *,
    force: bool = False,
) -> tuple[str, Path | None, list[str]]:
    validate_feature_id(feature)
    warnings: list[str] = []
    micro_path = paths.root / "docs" / "delta" / "20_micro" / f"{feature}.md"
    if not micro_path.exists():
        warnings.append(f"Missing micro brief for rule seed: docs/delta/20_micro/{feature}.md")
        return "missing", None, warnings

    target = paths.cartridge / "rules" / f"{feature}.mdc.seed"
    skip, reason = _should_skip_rules_seed(target, force=force)
    if skip:
        warnings.append(f"Skipped cartridge/rules/{feature}.mdc.seed ({reason})")
        return f"skipped ({reason})", None, warnings

    body = build_rule_seed_body(paths, feature)
    status = "updated" if target.exists() else "written"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{RULE_SEED_DRAFT_BANNER}\n\n{body.strip()}\n", encoding="utf-8")
    return status, target, warnings


def _should_skip_source_map(target: Path, *, force: bool) -> tuple[bool, str]:
    if force or not target.exists():
        return False, ""
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False, ""
    if data.get("_manual") is True:
        return True, "manual source map (_manual flag)"
    if data.get("_auto_sync") is True:
        return False, ""
    return True, "exists without auto-sync marker"


def _emit_auto_sync_derivative(
    paths: RepoPaths,
    target: Path,
    source: Path,
    body: str,
    *,
    force: bool,
) -> tuple[str, Path | None]:
    skip, reason = _should_skip_existing(target, force=force)
    if skip:
        return f"skipped ({reason})", None
    status = "updated" if target.exists() else "written"
    banner = _auto_sync_banner(source, paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{banner}\n\n{body.strip()}\n", encoding="utf-8")
    return status, target


def validate_pack_completeness(paths: RepoPaths) -> list[str]:
    missing: list[str] = []
    for rel in REQUIRED_PACK_FILES:
        if not (paths.cartridge / rel).exists():
            missing.append(f"cartridge/{rel}")
    return missing


def _agents_memory_section(paths: RepoPaths) -> str:
    agents_path = paths.root / "AGENTS.md"
    if not agents_path.exists():
        return ""
    sections = parse_sections(agents_path.read_text(encoding="utf-8", errors="replace"))
    for title, body in sections.items():
        if title.startswith(EDITABLE_SECTION):
            return body.strip()
    return ""


def emit_cartridge_pack(
    paths: RepoPaths,
    feature: str,
    *,
    force: bool = False,
    emit_rules_seeds: bool = False,
) -> tuple[dict[str, Path], dict[str, str], list[str]]:
    validate_feature_id(feature)
    warnings: list[str] = []
    results: dict[str, str] = {}
    written: dict[str, Path] = {}

    mappings_dir = paths.cartridge / "mappings"
    mappings_dir.mkdir(parents=True, exist_ok=True)
    source_map_path = mappings_dir / "source-map.json"
    skip_map, map_reason = _should_skip_source_map(source_map_path, force=force)
    if skip_map:
        results["source_map"] = f"skipped ({map_reason})"
        warnings.append(f"Skipped cartridge/mappings/source-map.json ({map_reason})")
    else:
        map_existed = source_map_path.exists()
        source_map_path.write_text(
            json.dumps(build_source_map(feature), indent=2) + "\n",
            encoding="utf-8",
        )
        written["source_map"] = source_map_path
        results["source_map"] = "updated" if map_existed else "written"

    micro_path = paths.root / "docs" / "delta" / "20_micro" / f"{feature}.md"
    research_path = paths.cartridge / "research-summary.md"
    if micro_path.exists():
        status, path = _emit_auto_sync_derivative(
            paths,
            research_path,
            micro_path,
            _build_research_summary(paths, feature),
            force=force,
        )
        results["research_summary"] = status
        if path:
            written["research_summary"] = path
        elif status.startswith("skipped"):
            warnings.append("Skipped cartridge/research-summary.md (draft/manual or exists without auto-sync)")
    else:
        results["research_summary"] = "missing"
        warnings.append(f"Missing micro brief: docs/delta/20_micro/{feature}.md")

    memory_target = paths.cartridge / "memory.md"
    memory_facts = _agents_memory_section(paths)
    if not memory_facts:
        results["memory"] = "missing"
        warnings.append("AGENTS.md has no Durable Workspace Facts section for memory.md")
    else:
        skip, _ = _should_skip_existing(memory_target, force=force)
        if skip:
            results["memory"] = "skipped"
            warnings.append(f"Skipped cartridge/memory.md (draft/manual or exists without auto-sync)")
        else:
            status = "updated" if memory_target.exists() else "written"
            banner = _auto_sync_banner(paths.root / "AGENTS.md", paths)
            memory_target.parent.mkdir(parents=True, exist_ok=True)
            memory_target.write_text(
                f"{banner}\n\n# Memory (from AGENTS.md)\n\n{memory_facts}\n",
                encoding="utf-8",
            )
            written["memory"] = memory_target
            results["memory"] = status

    spec_path = paths.root / "docs" / "specs" / feature / "spec.md"
    if spec_path.exists():
        specseed_path = paths.cartridge / "specs" / f"{feature}.specseed.md"
        status, path = _emit_auto_sync_derivative(
            paths,
            specseed_path,
            spec_path,
            _build_specseed_body(feature, spec_path.read_text(encoding="utf-8")),
            force=force,
        )
        results["specseed"] = status
        if path:
            written["specseed"] = path
    else:
        results["specseed"] = "missing"
        warnings.append(f"Missing spec seed source: docs/specs/{feature}/spec.md")

    if emit_rules_seeds:
        if not micro_path.exists():
            results["rules_seed"] = "missing"
        else:
            seed_status, seed_path, seed_warnings = emit_rules_seed(paths, feature, force=force)
            warnings.extend(seed_warnings)
            results["rules_seed"] = seed_status
            if seed_path:
                written["rules_seed"] = seed_path
    else:
        results["rules_seed"] = "disabled"

    return written, results, warnings

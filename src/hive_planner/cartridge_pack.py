from __future__ import annotations

import json
import re
from pathlib import Path

from hive_planner.agents_memory import EDITABLE_SECTION, parse_sections
from hive_planner.config import RepoPaths
from hive_planner.delta_emit import (
    _auto_sync_banner,
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
) -> tuple[dict[str, Path], dict[str, str], list[str]]:
    warnings: list[str] = []
    results: dict[str, str] = {}
    written: dict[str, Path] = {}

    mappings_dir = paths.cartridge / "mappings"
    mappings_dir.mkdir(parents=True, exist_ok=True)
    source_map_path = mappings_dir / "source-map.json"
    source_map_path.write_text(json.dumps(build_source_map(feature), indent=2), encoding="utf-8")
    written["source_map"] = source_map_path
    results["source_map"] = "written"

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

    return written, results, warnings

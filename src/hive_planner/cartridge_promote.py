"""Promote draft cartridge files into Delta / Spec Kit and stage CL candidates."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from hive_planner.bootstrap import BOOTSTRAP_BANNER
from hive_planner.config import RepoPaths, validate_feature_id
from hive_planner.delta_emit import (
    AUTO_SYNC_PREFIX,
    DRAFT_MARKER,
    MANUAL_MARKER,
    _first_content_line,
    _repo_relative,
    _strip_leading_banner,
)
from hive_planner.spec_drift import (
    check_memory_spec_drift,
    check_spec_handoff,
    classify_bullet,
    repair_agents_active_feature,
    repair_agents_rosetta_section,
)
from hive_planner.rosetta_nav import (
    ensure_handoff_rosetta_navigation,
    plan_navigation_block,
    spec_navigation_block,
    tasks_navigation_block,
)
from hive_planner.translator import DRAFT_BANNER

PROMOTED_BANNER = "<!-- PROMOTED: from cartridge — review before handoff -->"
HANDOFF_INCOMPLETE_MSG = (
    "Handoff incomplete — files saved but promotion/spec-drift needs review (see promote output above)."
)
TASKS_WIRING_AUDIT_HEADING = "## After each implementation task — Integration wiring audit (required)"


def _tasks_wiring_audit_block() -> str:
    return "\n".join(
        [
            TASKS_WIRING_AUDIT_HEADING,
            "",
            "- [ ] Traced caller → handler → core (no layer break)",
            "- [ ] No false success when a sub-step failed or was skipped",
            "- [ ] Integration-level validation evidence attached",
            "- [ ] See `.cursor/rules/integration-wiring-audit.mdc`",
            "",
        ]
    )


def _append_tasks_wiring_audit_if_missing(tasks_path: Path) -> bool:
    if not tasks_path.is_file():
        return False
    text = tasks_path.read_text(encoding="utf-8", errors="replace")
    if TASKS_WIRING_AUDIT_HEADING in text or "Integration wiring audit" in text:
        return False
    updated = text.rstrip() + "\n\n" + _tasks_wiring_audit_block()
    tasks_path.write_text(updated, encoding="utf-8")
    return True


@dataclass
class CartridgePromoteResult:
    feature: str
    promotions: dict[str, str] = field(default_factory=dict)
    candidates_path: str | None = None
    agents_repair: dict | None = None
    rosetta_repair: dict | None = None
    handoff: dict | None = None
    spec_drift: dict | None = None
    warnings: list[str] = field(default_factory=list)
    ok: bool = True

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "feature": self.feature,
            "promotions": self.promotions,
            "candidates_path": self.candidates_path,
            "agents_repair": self.agents_repair,
            "rosetta_repair": self.rosetta_repair,
            "handoff": self.handoff,
            "spec_drift": self.spec_drift,
            "warnings": self.warnings,
        }


def cartridge_promote_layer_paths(paths: RepoPaths, feature: str) -> dict[str, Path]:
    validate_feature_id(feature)
    return {
        "holistic": paths.cartridge / "holistic.md",
        "macro": paths.cartridge / "macro.md",
        "micro": paths.cartridge / "micro" / f"{feature}.md",
        "specseed": paths.cartridge / "specs" / f"{feature}.specseed.md",
        "memory": paths.cartridge / "memory.md",
    }


def mark_cartridge_layers_draft(
    paths: RepoPaths,
    feature: str,
    *,
    only_paths: Iterable[Path] | None = None,
) -> dict[str, str]:
    """Prepend the standard draft banner on promote-eligible cartridge files."""
    allowed = _resolved_path_set(only_paths)
    results: dict[str, str] = {}
    for name, path in cartridge_promote_layer_paths(paths, feature).items():
        if allowed is not None and path.resolve() not in allowed:
            results[name] = "skipped (not emitted)"
            continue
        if not path.is_file():
            results[name] = "skipped (missing)"
            continue
        if _is_cartridge_draft(path):
            results[name] = "already draft"
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        path.write_text(f"{DRAFT_BANNER}\n\n{content.lstrip()}", encoding="utf-8")
        results[name] = "marked draft"
    return results


def _resolved_path_set(paths: Iterable[Path] | None) -> set[Path] | None:
    if paths is None:
        return None
    return {path.resolve() for path in paths}


def _cartridge_source_emitted(path: Path, allowed: set[Path] | None) -> bool:
    if allowed is None:
        return True
    return path.resolve() in allowed


def _is_cartridge_draft(path: Path) -> bool:
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8", errors="replace")
    first = _first_content_line(content)
    if first.startswith(DRAFT_MARKER):
        return True
    for line in content.splitlines()[:3]:
        if DRAFT_MARKER in line:
            return True
    return False


def _target_writable(path: Path, *, force: bool) -> tuple[bool, str]:
    if force or not path.exists():
        return True, ""
    content = path.read_text(encoding="utf-8", errors="replace")
    if BOOTSTRAP_BANNER in content:
        return True, "bootstrap placeholder"
    if "Replace this spec with the first real feature" in content:
        return True, "bootstrap placeholder"
    first = _first_content_line(content)
    if first.startswith(DRAFT_MARKER) or first.startswith(MANUAL_MARKER):
        return True, "draft/manual target"
    if first.startswith(PROMOTED_BANNER):
        return True, "prior promotion"
    if first.startswith(AUTO_SYNC_PREFIX):
        return False, "auto-sync target (use --force to overwrite)"
    return False, "exists"


def _strip_draft_banner(content: str) -> str:
    lines = content.splitlines()
    while lines and (not lines[0].strip() or DRAFT_MARKER in lines[0]):
        lines.pop(0)
    while lines and not lines[0].strip():
        lines.pop(0)
    body = "\n".join(lines).strip()
    return f"{body}\n" if body else ""


def _promote_body(cartridge_path: Path) -> str:
    raw = cartridge_path.read_text(encoding="utf-8", errors="replace")
    body = raw
    for _ in range(8):
        stripped = _strip_draft_banner(_strip_leading_banner(body))
        if stripped == body:
            break
        body = stripped
    return body


def _promote_to_target(
    paths: RepoPaths,
    cartridge_path: Path,
    target_path: Path,
    *,
    force: bool,
) -> tuple[str, Path | None]:
    if not _is_cartridge_draft(cartridge_path):
        return "skipped (not draft)", None
    writable, reason = _target_writable(target_path, force=force)
    if not writable:
        return f"skipped ({reason})", None
    body = _promote_body(cartridge_path)
    if not body.strip():
        return "skipped (empty)", None
    banner = f"{PROMOTED_BANNER} source: {_repo_relative(paths, cartridge_path)} -->"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    status = "updated" if target_path.exists() else "written"
    target_path.write_text(f"{banner}\n\n{body.strip()}\n", encoding="utf-8")
    return status, target_path


def _extract_bullets(text: str) -> list[str]:
    bullets: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
    return [b for b in bullets if b]


def _write_memory_candidates(paths: RepoPaths, feature: str, bullets: list[str]) -> Path | None:
    if not bullets:
        return None
    operational: list[str] = []
    behavioral: list[str] = []
    ambiguous: list[str] = []
    for bullet in bullets:
        kind = classify_bullet(bullet).kind
        if kind == "behavioral":
            behavioral.append(bullet)
        elif kind == "ambiguous":
            ambiguous.append(bullet)
        else:
            operational.append(bullet)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = paths.root / "docs" / "proposals" / f"cartridge-memory-{feature}-{stamp}.md"
    lines = [
        f"# Cartridge memory candidates — {feature}",
        "",
        "Review before `agents-propose`. Behavioral lines belong in spec.md, not AGENTS.md.",
        "",
        "# operational",
        "",
    ]
    lines.extend(f"- {b}" for b in operational)
    if ambiguous:
        lines.extend(
            [
                "",
                "# ambiguous",
                "",
                "Add `# operational` or `# behavioral` to each bullet before agents-propose.",
                "",
            ]
        )
        lines.extend(f"- {b}" for b in ambiguous)
    lines.extend(["", "# behavioral", ""])
    lines.extend(f"- {b}" for b in behavioral)
    if not operational and not behavioral and not ambiguous:
        return None
    lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _ensure_spec_scaffold(paths: RepoPaths, feature: str) -> dict[str, str]:
    results: dict[str, str] = {}
    spec_dir = paths.root / "docs" / "specs" / feature
    spec_dir.mkdir(parents=True, exist_ok=True)
    plan_path = spec_dir / "plan.md"
    tasks_path = spec_dir / "tasks.md"
    if not plan_path.exists():
        plan_path.write_text(
            "\n".join(
                [
                    PROMOTED_BANNER,
                    "",
                    f"# Plan: {feature}",
                    "",
                    "**Hook:** `spec.flow`",
                    "**Spec:** [spec.md](./spec.md)",
                    "",
                    plan_navigation_block(feature),
                    "",
                    "## Approach",
                    "",
                    "Derived from cartridge promotion — review and expand.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        results["plan"] = "written"
    if not tasks_path.exists():
        tasks_path.write_text(
            "\n".join(
                [
                    PROMOTED_BANNER,
                    "",
                    f"# Tasks: {feature}",
                    "",
                    "**Hook:** `spec.flow`",
                    "",
                    tasks_navigation_block(feature),
                    "",
                    "- [ ] Review promoted spec and delta micro brief",
                    "- [ ] Run `py -3.11 -m hive_planner ci-check`",
                    "",
                    _tasks_wiring_audit_block().rstrip(),
                    "",
                ]
            ),
            encoding="utf-8",
        )
        results["tasks"] = "written"
    elif _append_tasks_wiring_audit_if_missing(tasks_path):
        results["tasks"] = "updated (wiring audit)"
    return results


def promote_cartridge_drafts(
    paths: RepoPaths,
    feature: str,
    *,
    force: bool = False,
    write_memory_candidates: bool = True,
    run_spec_drift: bool = True,
    repair_agents: bool = True,
    only_cartridge_paths: Iterable[Path] | None = None,
) -> CartridgePromoteResult:
    from hive_planner.project_profile import resolve_project_integrations

    validate_feature_id(feature)
    result = CartridgePromoteResult(feature=feature)
    integrations = resolve_project_integrations(paths.root)
    if not integrations.spec_kit_enabled:
        result.ok = False
        result.promotions["status"] = "skipped (agent handoff off)"
        result.warnings.append(
            "Agent handoff off — enable unified handoff (Deploy agent handoff) before promoting cartridge drafts."
        )
        return result

    layer_paths = cartridge_promote_layer_paths(paths, feature)
    allowed_sources = _resolved_path_set(only_cartridge_paths)
    layers = {
        "holistic": (
            layer_paths["holistic"],
            paths.root / "docs" / "delta" / "00_holistic.md",
        ),
        "macro": (
            layer_paths["macro"],
            paths.root / "docs" / "delta" / "10_macro.md",
        ),
        "micro": (
            layer_paths["micro"],
            paths.root / "docs" / "delta" / "20_micro" / f"{feature}.md",
        ),
    }
    for name, (src, dest) in layers.items():
        if not _cartridge_source_emitted(src, allowed_sources):
            result.promotions[name] = "skipped (not emitted)"
            continue
        status, _path = _promote_to_target(paths, src, dest, force=force)
        result.promotions[name] = status
        if status.startswith("skipped") and src.exists() and _is_cartridge_draft(src):
            result.warnings.append(f"{name}: {status}")

    specseed = layer_paths["specseed"]
    spec_path = paths.root / "docs" / "specs" / feature / "spec.md"
    if not _cartridge_source_emitted(specseed, allowed_sources):
        result.promotions["spec"] = "skipped (not emitted)"
    elif specseed.is_file() and _is_cartridge_draft(specseed):
        status, promoted = _promote_to_target(paths, specseed, spec_path, force=force)
        result.promotions["spec"] = status
        if not promoted and status.startswith("skipped"):
            result.warnings.append(f"spec: {status}")
    elif spec_path.exists():
        result.promotions["spec"] = "skipped (no draft specseed)"
    else:
        result.promotions["spec"] = "skipped (missing specseed)"

    memory_path = layer_paths["memory"]
    if not _cartridge_source_emitted(memory_path, allowed_sources):
        result.promotions["memory_candidates"] = "skipped (not emitted)"
    elif write_memory_candidates and memory_path.is_file() and _is_cartridge_draft(memory_path):
        bullets = _extract_bullets(_promote_body(memory_path))
        candidates = _write_memory_candidates(paths, feature, bullets)
        if candidates:
            result.promotions["memory_candidates"] = "written"
            result.candidates_path = candidates.relative_to(paths.root).as_posix()
        else:
            result.promotions["memory_candidates"] = "skipped (no bullets)"
    else:
        result.promotions["memory_candidates"] = "skipped (not draft)"

    if result.promotions.get("micro") in {"written", "updated"} and not spec_path.exists():
        micro_body = _promote_body(paths.cartridge / "micro" / f"{feature}.md")
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(
            "\n".join(
                [
                    PROMOTED_BANNER,
                    "",
                    f"# Spec: {feature}",
                    "",
                    "**Hook:** `spec.flow`",
                    f"**Delta:** [{feature}.md](../../delta/20_micro/{feature}.md)",
                    "",
                    spec_navigation_block(feature),
                    "",
                    "## What",
                    "",
                    "Promoted from cartridge micro draft — review and expand.",
                    "",
                    "## Requirements",
                    "",
                    micro_body.strip() or "### R1 — Review cartridge draft",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        result.promotions["spec"] = "written (from micro)"

    promoted_primary = any(
        str(result.promotions.get(key, "")).startswith("written") or result.promotions.get(key) == "updated"
        for key in ("holistic", "macro", "micro", "spec")
    )
    if promoted_primary:
        result.promotions.update(_ensure_spec_scaffold(paths, feature))

    rosetta_details: list[str] = []
    patched_files: list[str] = []
    if repair_agents:
        repair = repair_agents_active_feature(paths, feature)
        if repair.repaired:
            result.agents_repair = {"feature": repair.feature, "detail": repair.detail}
        rosetta = repair_agents_rosetta_section(paths)
        if rosetta.repaired:
            rosetta_details.append(rosetta.detail)

    promoted_layers = {
        name
        for name, status in result.promotions.items()
        if name not in {"status", "spec", "plan", "tasks", "memory_candidates"}
        and (str(status).startswith("written") or status == "updated")
    }
    if result.promotions.get("spec", "").startswith("written") or result.promotions.get("spec") == "updated":
        promoted_layers.add("micro")
    patched_files = ensure_handoff_rosetta_navigation(paths, feature, promoted_layers=promoted_layers)
    if patched_files:
        rosetta_details.append(f"patched navigation in {len(patched_files)} handoff file(s)")
    if rosetta_details or patched_files:
        result.rosetta_repair = {
            "detail": "; ".join(rosetta_details) if rosetta_details else "navigation updated",
            "patched": patched_files,
        }

    if run_spec_drift:
        handoff = check_spec_handoff(paths, feature)
        result.handoff = handoff.to_dict()
        drift = check_memory_spec_drift(
            paths,
            feature=feature,
            candidates_path=paths.root / result.candidates_path if result.candidates_path else None,
            include_agents_facts=True,
        )
        result.spec_drift = drift.to_dict()
        result.ok = drift.ok and handoff.ok

    return result


def promote_wrote_layers(promotions: dict[str, str]) -> bool:
    skip_keys = {"status"}
    return any(
        key not in skip_keys and (str(status).startswith("written") or status == "updated")
        for key, status in promotions.items()
    )


def promote_nothing_written_guidance(promote: CartridgePromoteResult | dict) -> str | None:
    data = promote.to_dict() if isinstance(promote, CartridgePromoteResult) else promote
    promotions = data.get("promotions") or {}
    if promotions.get("status") == "skipped (agent handoff off)":
        return None
    if promote_wrote_layers(promotions):
        return None
    feature = str(data.get("feature") or "your-feature-id")
    return (
        f"No cartridge layers were promoted for feature '{feature}'. "
        "Promote looks for draft files (starting with <!-- DRAFT: -->) at "
        f"cartridge/holistic.md, macro.md, micro/{feature}.md, "
        f"specs/{feature}.specseed.md, and optionally memory.md. "
        "After Sources ingest, enable **Mark emitted as draft** in Load cartridge "
        "(or add the draft banner manually). Translate mode adds drafts automatically. "
        "Import with Promote adapts custom filenames into that layout first; "
        "set Feature id or add layer_map / features to manifest.json to steer mapping."
    )


def promote_cli_exit_code(promote: CartridgePromoteResult | dict | None) -> int:
    """Return process exit code after an optional promote step."""
    if promote is None:
        return 0
    data = promote.to_dict() if isinstance(promote, CartridgePromoteResult) else promote
    if data.get("promotions", {}).get("status") == "skipped (agent handoff off)":
        return 0
    return 0 if data.get("ok", True) else 1

"""Rosetta Stone navigation blocks for agent handoff artifacts."""

from __future__ import annotations

import re
from pathlib import Path

ROSETTA_NAV_HEADING = "## Agent navigation (Rosetta Stone)"
ROSETTA_NAV_MARKER = "<!-- ROSETTA-NAV -->"
AGENTS_ROSETTA_HEADING = "## Planning Rosetta Stone"


def has_rosetta_navigation(text: str) -> bool:
    return ROSETTA_NAV_MARKER in text or ROSETTA_NAV_HEADING in text


def spec_navigation_block(feature: str) -> str:
    return f"""{ROSETTA_NAV_MARKER}

{ROSETTA_NAV_HEADING}

Before implementing, load the hook map — do not jump straight into requirements.

1. [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) — hook `planning.rosetta`
2. Follow **UNLOCKS**: `context.delta` → [`00_holistic.md`](../../delta/00_holistic.md), [`10_macro.md`](../../delta/10_macro.md)
3. This feature — hook `spec.flow`:
   - Delta micro: [`{feature}.md`](../../delta/20_micro/{feature}.md)
   - Plan: [`plan.md`](./plan.md)
   - Tasks: [`tasks.md`](./tasks.md)"""


def plan_navigation_block(feature: str) -> str:
    return f"""{ROSETTA_NAV_MARKER}

{ROSETTA_NAV_HEADING}

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before editing this plan.

- **Spec:** [`spec.md`](./spec.md)
- **Delta micro:** [`{feature}.md`](../../delta/20_micro/{feature}.md)
- **Hooks:** `spec.flow`, `context.delta`"""


def tasks_navigation_block(feature: str) -> str:
    return f"""{ROSETTA_NAV_MARKER}

{ROSETTA_NAV_HEADING}

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before executing tasks.

- **Spec:** [`spec.md`](./spec.md)
- **Plan:** [`plan.md`](./plan.md)
- **Delta micro:** [`{feature}.md`](../../delta/20_micro/{feature}.md)"""


def delta_micro_navigation_block(feature: str) -> str:
    return f"""{ROSETTA_NAV_MARKER}

{ROSETTA_NAV_HEADING}

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before coding from this brief.

- **Hooks:** `context.delta`, `spec.flow`
- **Spec Kit:** [`spec.md`](../../specs/{feature}/spec.md), [`plan.md`](../../specs/{feature}/plan.md), [`tasks.md`](../../specs/{feature}/tasks.md)"""


def delta_layer_navigation_block(layer: str) -> str:
    if layer == "holistic":
        unlocks = "macro / micro / spec alignment"
        delta_link = "[`10_macro.md`](../10_macro.md)"
    else:
        unlocks = "micro briefs and spec.flow"
        delta_link = "[`20_micro/`](./) feature briefs"
    return f"""{ROSETTA_NAV_MARKER}

{ROSETTA_NAV_HEADING}

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before using this Delta layer.

- **Hook:** `context.delta`
- **Unlocks:** {unlocks}
- **Next:** {delta_link}"""


AGENTS_ROSETTA_SECTION = """## Planning Rosetta Stone (required anchor)

Before planning or coding, load the hook map into normal context:

- **Search phrase:** `Planning Rosetta Stone`
- **Hook ID:** `planning.rosetta`
- **File:** `docs/planning-rosetta-stone.md`

Follow linked hooks (`context.delta`, `spec.flow`, `change.impact`, etc.) before diving into spec or Delta files.
"""

DEPLOY_HANDOFF_NAV_LAYERS = frozenset({"holistic", "macro", "micro"})


def inject_after_header(text: str, block: str) -> str:
    """Insert navigation block after title/hook lines and before first ## section."""
    if has_rosetta_navigation(text):
        return text
    lines = text.splitlines()
    insert_at = 0
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--"):
            insert_at = idx + 1
            continue
        if stripped.startswith("## "):
            break
        if stripped.startswith("# "):
            insert_at = idx + 1
            continue
        if stripped.startswith("**"):
            insert_at = idx + 1
            continue
        break
    prefix = "\n".join(lines[:insert_at]).rstrip()
    suffix = "\n".join(lines[insert_at:]).lstrip("\n")
    merged = f"{prefix}\n\n{block.strip()}\n"
    if suffix:
        merged += f"\n{suffix}"
    if not merged.endswith("\n"):
        merged += "\n"
    return merged


def ensure_file_rosetta_navigation(path: Path, block: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    updated = inject_after_header(text, block)
    if updated == text:
        return False
    path.write_text(updated, encoding="utf-8", newline="\n")
    return True


def ensure_handoff_rosetta_navigation(
    paths,
    feature: str,
    *,
    promoted_layers: set[str] | None = None,
) -> list[str]:
    """Patch promoted handoff files with Rosetta navigation when missing."""
    from hive_planner.config import RepoPaths

    root: RepoPaths = paths
    patched: list[str] = []
    layers = promoted_layers or set()
    spec_dir = root.root / "docs" / "specs" / feature
    checks: list[tuple[Path, str]] = [
        (spec_dir / "spec.md", spec_navigation_block(feature)),
        (spec_dir / "plan.md", plan_navigation_block(feature)),
        (spec_dir / "tasks.md", tasks_navigation_block(feature)),
    ]
    if "micro" in layers:
        checks.append(
            (root.root / "docs" / "delta" / "20_micro" / f"{feature}.md", delta_micro_navigation_block(feature))
        )
    if "holistic" in layers:
        checks.append((root.root / "docs" / "delta" / "00_holistic.md", delta_layer_navigation_block("holistic")))
    if "macro" in layers:
        checks.append((root.root / "docs" / "delta" / "10_macro.md", delta_layer_navigation_block("macro")))
    for path, block in checks:
        if ensure_file_rosetta_navigation(path, block):
            patched.append(path.relative_to(root.root).as_posix())
    return patched


def agents_has_rosetta_section(text: str) -> bool:
    match = re.search(
        rf"^{re.escape(AGENTS_ROSETTA_HEADING)}[^\n]*\n(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return False
    body = match.group(1)
    return bool(body.strip()) and "planning.rosetta" in body


def agents_missing_rosetta_section(text: str) -> bool:
    return not agents_has_rosetta_section(text)


def missing_handoff_rosetta_navigation(paths, feature: str) -> list[str]:
    """Return repo-relative labels for handoff files missing Rosetta navigation."""
    from hive_planner.config import RepoPaths

    root: RepoPaths = paths
    missing: list[str] = []
    checks = [
        f"docs/specs/{feature}/spec.md",
        f"docs/specs/{feature}/plan.md",
        f"docs/specs/{feature}/tasks.md",
        f"docs/delta/20_micro/{feature}.md",
    ]
    for rel in checks:
        path = root.root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not has_rosetta_navigation(text):
            missing.append(f"{rel} missing Rosetta navigation")
    return missing


def inject_agents_rosetta_section(text: str) -> str:
    if not agents_missing_rosetta_section(text):
        return text
    marker = "## Repository root"
    if marker in text:
        idx = text.index(marker)
        end = text.find("\n## ", idx + len(marker))
        if end == -1:
            end = len(text)
        return text[:end].rstrip() + f"\n\n{AGENTS_ROSETTA_SECTION.rstrip()}\n" + text[end:]
    lines = text.splitlines()
    insert_at = 1
    for idx, line in enumerate(lines):
        if line.startswith("# "):
            insert_at = idx + 1
            break
    block_lines = lines[:insert_at] + ["", AGENTS_ROSETTA_SECTION.rstrip(), ""] + lines[insert_at:]
    return "\n".join(block_lines).rstrip() + "\n"

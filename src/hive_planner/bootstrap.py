from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from hive_planner.config import RepoPaths, is_repo_root

BOOTSTRAP_BANNER = "<!-- BOOTSTRAP: hive_planner init -->"


class BootstrapError(Exception):
    """Project bootstrap failed."""


@dataclass
class BootstrapResult:
    target: Path
    project_name: str
    files_written: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "target": str(self.target),
            "project_name": self.project_name,
            "files_written": self.files_written,
            "warnings": self.warnings,
        }


def _starter_kit_dir(source_root: Path) -> Path:
    kit = source_root / "starter-kit"
    if kit.is_dir():
        return kit
    return Path(__file__).resolve().parent / "bootstrap_templates"


def _rules_dir(source_root: Path) -> Path:
    rules = source_root / ".cursor" / "rules"
    if rules.is_dir():
        return rules
    return _starter_kit_dir(source_root) / ".cursor" / "rules"


def _write_text(target: Path, rel: str, content: str, *, force: bool, written: list[str]) -> None:
    path = target / rel
    if path.exists() and not force:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    written.append(rel)


def _copy_file(source: Path, target: Path, rel: str, *, force: bool, written: list[str]) -> None:
    if not source.is_file():
        return
    dest = target / rel
    if dest.exists() and not force:
        return
    if source.resolve() == dest.resolve():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    written.append(rel)


def _start_here(project_name: str) -> str:
    return f"""{BOOTSTRAP_BANNER}

# START_HERE

Loader entrypoint for coding agents in **{project_name}**.

## First retrieval step

Search for **Planning Rosetta Stone** or hook `planning.rosetta`:

1. [`docs/planning-rosetta-stone.md`](docs/planning-rosetta-stone.md)
2. [`AGENTS.md`](AGENTS.md)

## Read order

1. `docs/planning-rosetta-stone.md`
2. `AGENTS.md`
3. `docs/delta/00_holistic.md` and `docs/delta/10_macro.md` (when present)
4. Active `docs/delta/20_micro/<feature>.md` and `docs/specs/<feature>/` trio (when present)

## Context priority

- **Primary:** Delta docs + active spec/plan/tasks
- **Secondary:** `AGENTS.md` + `.cursor/rules/`
- **Tertiary:** document-sourced excerpts (optional)

## Execution rule

Before editing code, identify the active feature, map work to a `HOOK_ID`, and read the active spec/plan/tasks.
"""


def _agents_md(project_name: str, repo_root: Path) -> str:
    root_display = repo_root.as_posix()
    return f"""{BOOTSTRAP_BANNER}

# AGENTS.md — {project_name}

Durable operating guidance for agentic coding in this repo.

## Repository root

`{root_display}`

## Planning Rosetta Stone (required anchor)

- **Search phrase:** `Planning Rosetta Stone`
- **Hook ID:** `planning.rosetta`
- **File:** `docs/planning-rosetta-stone.md`

## Startup read order

See [`START_HERE.md`](START_HERE.md).

## Delta model

- **Holistic** — mission, goals, constraints
- **Macro** — architecture, modules, workflows
- **Micro** — feature scope, tasks, files, tests

## Active feature

**None** — replace with your first feature (see `docs/specs/example-feature/`).

## Durable Workspace Facts

- Install Hive CLI from your Hive Code Planner repo: `py -3.11 -m pip install -e ".[dev]"` (run from that repo).
- Run `py -3.11 -m hive_planner ci-check` before handoff when Hive tooling is wired.
"""


def _planning_rosetta(project_name: str) -> str:
    return f"""{BOOTSTRAP_BANNER}

# Planning Rosetta Stone — {project_name}

Search phrase: **Planning Rosetta Stone** · Hook: `planning.rosetta`

## Core hooks

| HOOK_ID | Meaning |
|---------|---------|
| `planning.rosetta` | This legend |
| `context.delta` | Holistic / macro / micro docs |
| `spec.flow` | Spec Kit spec / plan / tasks |
| `cursor.rules` | `.cursor/rules/*.mdc` |
| `change.impact` | Impact packets before edits |
| `change.bugfix_mode` | Bugfix impact mode |
| `integration.cl_spec` | AGENTS memory vs spec behavioral truth |

## Primary files

- [`START_HERE.md`](../START_HERE.md)
- [`AGENTS.md`](../AGENTS.md)
- [`delta/00_holistic.md`](delta/00_holistic.md)
- [`delta/10_macro.md`](delta/10_macro.md)
- [`specs/example-feature/spec.md`](specs/example-feature/spec.md)
- [`change-impact/policy.md`](change-impact/policy.md)
- [`spec-kit-agent-integration.md`](../spec-kit-agent-integration.md)
"""


def _holistic(project_name: str) -> str:
    return f"""{BOOTSTRAP_BANNER}

# Holistic — {project_name}

## Mission

Describe the project mission and success criteria.

## Goals

- Goal 1

## Constraints

- Constraint 1

## Non-goals

- Non-goal 1
"""


def _macro(project_name: str) -> str:
    return f"""{BOOTSTRAP_BANNER}

# Macro — {project_name}

## Architecture

Describe modules, boundaries, and interfaces.

## Workflows

Describe planning → spec → implementation flow.

## Dependencies

| Component | Role |
|-----------|------|
| Spec Kit | Behavioral spec/plan/tasks |
| Cursor | Implementation + rules |
| Hive CLI | Optional validation (`ci-check`, impact packets) |
"""


def _micro_readme() -> str:
    return f"""{BOOTSTRAP_BANNER}

# Micro Briefs

One file per feature: `docs/delta/20_micro/<feature>.md`

**Starter feature:** [example-feature.md](./example-feature.md)
"""


def _micro_example() -> str:
    return f"""{BOOTSTRAP_BANNER}

# Feature Micro Brief: example-feature

**Hook:** `spec.flow`

## Feature Name

Example feature — replace with your first real feature.

## Scope

| In scope | Out of scope |
|----------|--------------|
| Scaffold only | Production behavior |

## Validation

```powershell
# Replace with project-specific checks
```
"""


def _example_spec() -> str:
    return f"""{BOOTSTRAP_BANNER}

# Spec: example-feature

**Hook:** `spec.flow`  
**Status:** draft  
**Delta:** [example-feature.md](../../delta/20_micro/example-feature.md)

## What

Replace this spec with the first real feature for your project.

## Requirements

### R1 — Placeholder

Define acceptance criteria here.

## Out of scope

Production implementation until spec is reviewed.
"""


def _example_plan() -> str:
    return f"""{BOOTSTRAP_BANNER}

# Plan: example-feature

**Hook:** `spec.flow`  
**Spec:** [spec.md](./spec.md)

## Approach

Describe technical approach after spec review.
"""


def _example_tasks() -> str:
    return f"""{BOOTSTRAP_BANNER}

# Tasks: example-feature

## Task 1 — Replace scaffold

- [ ] Update holistic/macro docs
- [ ] Rename `example-feature` to your feature id
- [ ] Set active feature in `AGENTS.md`

## Active task

**Task 1**
"""


def _change_impact_policy() -> str:
    return f"""{BOOTSTRAP_BANNER}

# Change Impact Policy

**Hook:** `change.impact`, `change.validation`

Generate an impact packet before non-trivial edits:

```powershell
py -3.11 -m hive_planner impact --feature <feature> --files <path>
py -3.11 -m hive_planner impact --feature <feature> --mode bugfix --files <path>
```
"""


def _project_map() -> str:
    return f"""{BOOTSTRAP_BANNER}

# Project Map

**Hook:** `change.impact`, `next.files`

| Module | Role | Spec / Delta deps |
|--------|------|-------------------|
| `docs/delta/*.md` | Primary planning truth | `context.delta` |
| `docs/planning-rosetta-stone.md` | Hook legend | `planning.rosetta` |
"""


def _test_map() -> str:
    return f"""{BOOTSTRAP_BANNER}

# Test Map

**Hook:** `change.impact`, `next.files`

| Source module | Tests |
|---------------|-------|
"""


def _readme(project_name: str) -> str:
    return f"""# {project_name}

Hive agentic coding profile (bootstrapped with `hive_planner init`).

## Agent startup

1. Read [`START_HERE.md`](START_HERE.md)
2. Load [`docs/planning-rosetta-stone.md`](docs/planning-rosetta-stone.md)
3. Read [`AGENTS.md`](AGENTS.md)

## Hive CLI

Install from your Hive Code Planner checkout, then run from this repo:

```powershell
py -3.11 -m hive_planner ci-check
py -3.11 -m hive_planner impact --feature example-feature --files src/
```

See the Hive Code Planner `docs/project-bootstrap-guide.md` in your Hive install for deployment notes.
"""


def _candidates_template() -> str:
    return """# operational
- Example operational fact (commands, paths, conventions).

# behavioral
- Example behavioral requirement (must update spec.md first).
"""


def _validate_target(source_paths: RepoPaths, target: Path) -> None:
    if target.exists() and not target.is_dir():
        raise BootstrapError(f"Target must be a directory, not a file: {target}")
    if target.resolve() == source_paths.root.resolve():
        raise BootstrapError(
            f"Target cannot be the Hive source repository: {target} — choose a separate project directory"
        )


def init_project(
    source_paths: RepoPaths,
    target: Path,
    *,
    name: str | None = None,
    force: bool = False,
) -> BootstrapResult:
    target = target.resolve()
    _validate_target(source_paths, target)
    project_name = (name or target.name).strip() or target.name
    written: list[str] = []
    warnings: list[str] = []

    if is_repo_root(target) and not force:
        raise BootstrapError(f"Target already initialized (START_HERE.md exists): {target}")

    if target.exists() and any(target.iterdir()) and not force:
        raise BootstrapError(f"Target not empty: {target} — use --force to scaffold anyway")

    target.mkdir(parents=True, exist_ok=True)

    templates: list[tuple[str, str]] = [
        ("START_HERE.md", _start_here(project_name)),
        ("AGENTS.md", _agents_md(project_name, target)),
        ("README.md", _readme(project_name)),
        ("docs/planning-rosetta-stone.md", _planning_rosetta(project_name)),
        ("docs/delta/00_holistic.md", _holistic(project_name)),
        ("docs/delta/10_macro.md", _macro(project_name)),
        ("docs/delta/20_micro/README.md", _micro_readme()),
        ("docs/delta/20_micro/example-feature.md", _micro_example()),
        ("docs/specs/example-feature/spec.md", _example_spec()),
        ("docs/specs/example-feature/plan.md", _example_plan()),
        ("docs/specs/example-feature/tasks.md", _example_tasks()),
        ("docs/change-impact/policy.md", _change_impact_policy()),
        ("docs/change-impact/project-map.md", _project_map()),
        ("docs/change-impact/test-map.md", _test_map()),
        ("docs/proposals/candidates-template.md", _candidates_template()),
        ("context-library/indexes/document-index.json", json.dumps({"documents": []}, indent=2) + "\n"),
        ("context-library/indexes/chunk-index.json", json.dumps({"chunks": []}, indent=2) + "\n"),
        ("context-library/indexes/embedding-index.json", json.dumps({"embeddings": [], "model_id": None}, indent=2) + "\n"),
    ]
    for rel, content in templates:
        _write_text(target, rel, content, force=force, written=written)

    for rel in (
        "context-library/sources/.gitkeep",
        "context-library/normalized/markdown/.gitkeep",
        "context-library/normalized/metadata/.gitkeep",
        "docs/change-impact/impact-packets/.gitkeep",
    ):
        path = target / rel
        if path.exists() and not force:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        written.append(rel)

    kit = _starter_kit_dir(source_paths.root)
    _copy_file(kit / "spec-kit-agent-integration.md", target, "spec-kit-agent-integration.md", force=force, written=written)
    if not (target / "spec-kit-agent-integration.md").exists():
        warnings.append("Missing starter-kit/spec-kit-agent-integration.md — skipped copy")

    rules = _rules_dir(source_paths.root)
    for rule_name in ("architecture.mdc", "task-execution.mdc", "validation.mdc"):
        _copy_file(rules / rule_name, target, f".cursor/rules/{rule_name}", force=force, written=written)
        if not (target / ".cursor/rules" / rule_name).exists():
            warnings.append(f"Missing rule template {rule_name} — not copied")

    if not is_repo_root(target):
        raise BootstrapError("Bootstrap incomplete — missing START_HERE.md or planning rosetta")

    return BootstrapResult(target=target, project_name=project_name, files_written=sorted(written), warnings=warnings)

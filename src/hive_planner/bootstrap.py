from __future__ import annotations

import json
import keyword
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from hive_planner.config import RepoPaths, is_repo_root

BOOTSTRAP_BANNER = "<!-- BOOTSTRAP: hive_planner init -->"
BOOTSTRAP_COMMENT = "# BOOTSTRAP: hive_planner init"
BOOTSTRAP_PROFILES = frozenset({"minimal", "full"})


class BootstrapError(Exception):
    """Project bootstrap failed."""


@dataclass
class BootstrapResult:
    target: Path
    project_name: str
    profile: str = "minimal"
    git_initialized: bool = False
    files_written: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "target": str(self.target),
            "project_name": self.project_name,
            "profile": self.profile,
            "git_initialized": self.git_initialized,
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

None — set to your first feature id (see `docs/specs/example-feature/`).

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


def _package_slug(folder_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", folder_name.lower()).strip("_")
    if not slug or slug[0].isdigit():
        slug = f"app_{slug}" if slug else "app"
    if not slug.isidentifier() or keyword.iskeyword(slug):
        slug = f"{slug}_pkg"
    return slug


def _toml_basic_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _pyproject_toml(project_name: str, package_slug: str) -> str:
    return f"""{BOOTSTRAP_COMMENT}

[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "{package_slug}"
version = "0.1.0"
description = {_toml_basic_string(project_name)}
readme = "README.md"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=7.0"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
"""


def _gitignore() -> str:
    return """# Python
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
dist/
build/
.venv/
venv/

# Test / tooling
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Hive / agent artifacts (optional local)
cartridge/
"""


def _github_ci_workflow() -> str:
    return """name: CI

on:
  push:
  pull_request:
  workflow_dispatch:

jobs:
  hive-handoff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Hive CLI
        env:
          HIVE_PLANNER_PATH: ${{ vars.HIVE_PLANNER_PATH }}
        run: |
          if [ -z "$HIVE_PLANNER_PATH" ]; then
            echo "Set repository variable HIVE_PLANNER_PATH to your Hive Code Planner checkout"
            exit 1
          fi
          pip install -e "$HIVE_PLANNER_PATH[dev]"

      - name: Sync impact maps
        run: python -m hive_planner impact-sync-maps

      - name: Hive handoff check
        run: python -m hive_planner ci-check

  project-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dev dependencies
        run: pip install -e ".[dev]"

      - name: Run tests
        run: pytest -q
"""


def _src_init(package_slug: str, project_name: str) -> str:
    return f'''{BOOTSTRAP_COMMENT}
"""{project_name} application package."""
'''


def _test_placeholder(package_slug: str) -> str:
    return f"""{BOOTSTRAP_COMMENT}

def test_package_importable() -> None:
    import {package_slug}

    assert {package_slug}.__doc__
"""


def _write_full_profile(
    target: Path,
    *,
    project_name: str,
    package_slug: str,
    force: bool,
    written: list[str],
) -> None:
    full_templates: list[tuple[str, str]] = [
        ("pyproject.toml", _pyproject_toml(project_name, package_slug)),
        (".gitignore", _gitignore()),
        (f"src/{package_slug}/__init__.py", _src_init(package_slug, project_name)),
        ("tests/test_placeholder.py", _test_placeholder(package_slug)),
        (".github/workflows/ci.yml", _github_ci_workflow()),
    ]
    for rel, content in full_templates:
        _write_text(target, rel, content, force=force, written=written)


def _run_git_init(target: Path, warnings: list[str]) -> bool:
    if (target / ".git").exists():
        warnings.append("Git repository already exists — skipped git init")
        return False
    try:
        proc = subprocess.run(
            ["git", "init"],
            cwd=target,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        warnings.append(f"git init failed: {exc}")
        return False
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        warnings.append(f"git init failed: {detail}")
        return False
    return True


def _validate_target(source_paths: RepoPaths, target: Path) -> None:
    if target.exists() and not target.is_dir():
        raise BootstrapError(f"Target must be a directory, not a file: {target}")
    source_root = source_paths.root.resolve()
    target_resolved = target.resolve()
    if target_resolved == source_root:
        raise BootstrapError(
            f"Target cannot be the Hive source repository: {target} — choose a separate project directory"
        )
    try:
        target_resolved.relative_to(source_root)
    except ValueError:
        return
    raise BootstrapError(
        f"Target cannot be inside the Hive source repository: {target} — choose a separate project directory"
    )


def init_project(
    source_paths: RepoPaths,
    target: Path,
    *,
    name: str | None = None,
    force: bool = False,
    profile: str = "minimal",
    git_init: bool = False,
) -> BootstrapResult:
    if profile not in BOOTSTRAP_PROFILES:
        allowed = ", ".join(sorted(BOOTSTRAP_PROFILES))
        raise BootstrapError(f"Unknown bootstrap profile '{profile}' — use one of: {allowed}")

    target = target.resolve()
    _validate_target(source_paths, target)
    project_name = (name or target.name).strip() or target.name
    if any(ch in project_name for ch in "\n\r"):
        raise BootstrapError("Project name cannot contain line breaks")
    written: list[str] = []
    warnings: list[str] = []

    if is_repo_root(target) and not force:
        raise BootstrapError(f"Target already initialized (START_HERE.md exists): {target}")

    if target.exists() and any(target.iterdir()) and not force:
        raise BootstrapError(f"Target not empty: {target} — use --force to scaffold anyway")

    target.mkdir(parents=True, exist_ok=True)

    try:
        _write_bootstrap_tree(
            source_paths,
            target,
            project_name=project_name,
            profile=profile,
            force=force,
            written=written,
            warnings=warnings,
        )
    except OSError as exc:
        raise BootstrapError(f"Failed to write bootstrap files: {exc}") from exc

    if not is_repo_root(target):
        raise BootstrapError("Bootstrap incomplete — missing START_HERE.md or planning rosetta")

    git_initialized = False
    if git_init:
        git_initialized = _run_git_init(target, warnings)

    return BootstrapResult(
        target=target,
        project_name=project_name,
        profile=profile,
        git_initialized=git_initialized,
        files_written=sorted(set(written)),
        warnings=warnings,
    )


def _write_bootstrap_tree(
    source_paths: RepoPaths,
    target: Path,
    *,
    project_name: str,
    profile: str,
    force: bool,
    written: list[str],
    warnings: list[str],
) -> None:
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

    if profile == "full":
        _write_full_profile(
            target,
            project_name=project_name,
            package_slug=_package_slug(target.name),
            force=force,
            written=written,
        )

    from hive_planner.project_profile import write_project_profile

    try:
        import importlib.metadata

        hive_version = importlib.metadata.version("hive-planner")
    except Exception:
        hive_version = None
    meta_path = write_project_profile(
        target,
        profile=profile,
        project_name=project_name,
        hive_planner_version=hive_version,
    )
    written.append(meta_path.relative_to(target).as_posix())

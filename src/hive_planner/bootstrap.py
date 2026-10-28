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
    packaged = Path(__file__).resolve().parent / "bootstrap_templates"
    kit = source_root / "starter-kit"
    if kit.is_dir() and (kit / "spec-kit-agent-integration.md").is_file():
        return kit
    return packaged


def _cl_spec_integration_doc_path(source_root: Path) -> Path | None:
    primary = source_root / "docs" / "cl-spec-integration.md"
    if primary.is_file():
        return primary
    packaged = Path(__file__).resolve().parent / "bootstrap_templates" / "cl-spec-integration.md"
    if packaged.is_file():
        return packaged
    return None


def _copy_cl_spec_integration_doc(
    source_paths: RepoPaths,
    target: Path,
    *,
    force: bool,
    written: list[str],
    warnings: list[str],
) -> None:
    source = _cl_spec_integration_doc_path(source_paths.root)
    if source is None:
        warnings.append("Missing docs/cl-spec-integration.md — not copied")
        return
    _copy_file(source, target, "docs/cl-spec-integration.md", force=force, written=written)
    if not (target / "docs" / "cl-spec-integration.md").is_file():
        warnings.append("Missing docs/cl-spec-integration.md — not copied")


def _rules_dir(source_root: Path) -> Path:
    rules = source_root / ".cursor" / "rules"
    if rules.is_dir():
        return rules
    return Path(__file__).resolve().parent / "bootstrap_templates" / ".cursor" / "rules"


_BASE_BOOTSTRAP_RULES = ("architecture.mdc", "task-execution.mdc", "validation.mdc")
_SPEC_KIT_BOOTSTRAP_RULES = ("integration-wiring-audit.mdc",)
_UNIFIED_HANDOFF_BOOTSTRAP_RULES = ("cl-spec-integration.mdc",)


def _bootstrap_rule_names(*, spec_kit: bool, continual_learning: bool) -> tuple[str, ...]:
    names = list(_BASE_BOOTSTRAP_RULES)
    if spec_kit:
        names.extend(_SPEC_KIT_BOOTSTRAP_RULES)
    if spec_kit and continual_learning:
        names.extend(_UNIFIED_HANDOFF_BOOTSTRAP_RULES)
    return tuple(names)


def _rule_template_path(source_paths: RepoPaths, rule_name: str) -> Path:
    primary = _rules_dir(source_paths.root) / rule_name
    if primary.is_file():
        return primary
    return Path(__file__).resolve().parent / "bootstrap_templates" / ".cursor" / "rules" / rule_name


def _copy_bootstrap_rules(
    source_paths: RepoPaths,
    target: Path,
    *,
    force: bool,
    written: list[str],
    warnings: list[str],
    spec_kit: bool,
    continual_learning: bool,
) -> None:
    for rule_name in _bootstrap_rule_names(spec_kit=spec_kit, continual_learning=continual_learning):
        source = _rule_template_path(source_paths, rule_name)
        _copy_file(source, target, f".cursor/rules/{rule_name}", force=force, written=written)
        if not (target / ".cursor/rules" / rule_name).exists():
            warnings.append(f"Missing rule template {rule_name} — not copied")


def _cursor_hooks_template_dir() -> Path:
    return Path(__file__).resolve().parent / "bootstrap_templates" / ".cursor"


_WORKSPACE_OPEN_COMMAND = "py -3.11 .cursor/hooks/hive_workspace_open.py"
_WORKSPACE_OPEN_MARKER = "hive_workspace_open.py"


def _ensure_workspace_open_hooks_json(
    target: Path,
    *,
    force: bool,
    written: list[str],
    warnings: list[str],
) -> None:
    """Add workspaceOpen without replacing other Cursor hook events already on disk."""
    rel = ".cursor/hooks.json"
    dest = target / rel
    templates = _cursor_hooks_template_dir()
    template_path = templates / "hooks.json"
    if not dest.is_file():
        _copy_file(template_path, target, rel, force=True, written=written)
        return
    try:
        data = json.loads(dest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        if force:
            _copy_file(template_path, target, rel, force=True, written=written)
        else:
            warnings.append("Existing .cursor/hooks.json is not valid JSON — workspaceOpen not merged")
        return
    if not isinstance(data, dict):
        if force:
            _copy_file(template_path, target, rel, force=True, written=written)
        else:
            warnings.append("Existing .cursor/hooks.json is not a JSON object — workspaceOpen not merged")
        return
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks
    events = hooks.get("workspaceOpen")
    if not isinstance(events, list):
        events = []
        hooks["workspaceOpen"] = events
    already = any(
        isinstance(item, dict) and _WORKSPACE_OPEN_MARKER in str(item.get("command", ""))
        for item in events
    )
    if already:
        return
    events.append({"command": _WORKSPACE_OPEN_COMMAND})
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    if rel not in written:
        written.append(rel)


def _copy_cursor_workspace_plugin_hooks(
    target: Path,
    *,
    force: bool,
    written: list[str],
    warnings: list[str],
) -> None:
    """Deploy workspaceOpen so Cursor 3.x loads `.cursor/plugins/hive-continual-learning`."""
    templates = _cursor_hooks_template_dir()
    hook_script = templates / "hooks" / "hive_workspace_open.py"
    _ensure_workspace_open_hooks_json(target, force=force, written=written, warnings=warnings)
    _copy_file(
        hook_script,
        target,
        ".cursor/hooks/hive_workspace_open.py",
        force=force,
        written=written,
    )
    if not (target / ".cursor" / "hooks.json").is_file():
        warnings.append("Missing Cursor workspaceOpen hooks.json — plugin may not load on Cursor 3.x")
    if not (target / ".cursor" / "hooks" / "hive_workspace_open.py").is_file():
        warnings.append("Missing hive_workspace_open.py — plugin may not load on Cursor 3.x")


def _install_bug_hunt_artifacts(
    target: Path,
    *,
    force: bool,
    written: list[str],
    warnings: list[str],
) -> None:
    """Install the chat-triggered bug-hunt command + always-on rule (core Hive feature)."""
    from hive_planner.bug_hunt import BugHuntError, install_bug_hunt

    try:
        # Generated trigger files must refresh even when init/deploy force=False,
        # or upgraded Hive Planner leaves a stale "one bug then wait" rule.
        result = install_bug_hunt(target, force=True)
    except BugHuntError as exc:
        warnings.append(f"Bug-hunt install skipped: {exc}")
        return
    for rel in result.files_written:
        if rel not in written:
            written.append(rel)


def _install_implementation_loop_artifacts(
    target: Path,
    pack: str,
    *,
    force: bool,
    written: list[str],
    warnings: list[str],
) -> None:
    """Install the post-spec coding loop when an explicit pack is given."""
    from hive_planner.implementation_loop import install_implementation_loop

    try:
        files = install_implementation_loop(target, pack, force_pack=force)
    except (ValueError, OSError) as exc:
        raise BootstrapError(f"Implementation-loop install failed: {exc}") from exc
    for rel in files:
        if rel not in written:
            written.append(rel)


def _install_agnostic_loop_artifacts(
    target: Path,
    *,
    written: list[str],
    warnings: list[str],
) -> None:
    from hive_planner.agnostic_loop import install_agnostic_loop, missing_agnostic_loop_artifacts

    try:
        files = install_agnostic_loop(target)
    except OSError as exc:
        raise BootstrapError(f"Agnostic-loop install failed: {exc}") from exc
    missing = missing_agnostic_loop_artifacts(target)
    if missing:
        raise BootstrapError("Agnostic-loop install incomplete — missing: " + ", ".join(missing))
    for rel in files:
        if rel not in written:
            written.append(rel)


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


def _agents_md(project_name: str, repo_root: Path, *, spec_kit: bool, continual_learning: bool) -> str:
    root_display = repo_root.as_posix()
    if spec_kit and continual_learning:
        active_feature = "**example-feature** — unified Spec Kit + Continual Learning scaffold; replace when real work begins."
        symbiotic = (
            "- **Symbiotic handoff:** behavioral truth in Spec Kit (`docs/specs/`), operational truth in this file "
            "(Continual Learning / `agents-propose`). See `docs/cl-spec-integration.md`."
        )
    elif spec_kit:
        active_feature = "**example-feature** — starter scaffold from bootstrap; replace when you begin real work."
        symbiotic = ""
    else:
        active_feature = "**none** — enable unified agent handoff in Hive Planner when you want Spec Kit + memory."
        symbiotic = ""
    symbiotic_block = f"\n{symbiotic}\n" if symbiotic else "\n"
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

{active_feature}

## Durable Workspace Facts
{symbiotic_block}
- Install Hive CLI from your Hive Code Planner repo: `py -3.11 -m pip install -e ".[dev]"` (run from that repo).
- Run `py -3.11 -m hive_planner ci-check` before handoff when Hive tooling is wired.
"""


def _planning_rosetta(project_name: str, *, spec_kit: bool, continual_learning: bool) -> str:
    optional_rows = ""
    primary_files = """- [`START_HERE.md`](../START_HERE.md)
- [`AGENTS.md`](../AGENTS.md)
- [`delta/00_holistic.md`](delta/00_holistic.md)
- [`delta/10_macro.md`](delta/10_macro.md)
- [`change-impact/policy.md`](change-impact/policy.md)"""
    if spec_kit:
        optional_rows += "| `spec.flow` | Spec Kit spec / plan / tasks |\n"
        primary_files += """
- [`specs/example-feature/spec.md`](specs/example-feature/spec.md)
- [`spec-kit-agent-integration.md`](../spec-kit-agent-integration.md)"""
    if continual_learning or spec_kit:
        optional_rows += "| `integration.cl_spec` | Spec Kit (behavioral) + Continual Learning (operational) |\n"
        primary_files += """
- [`cl-spec-integration.md`](cl-spec-integration.md)"""
    return f"""{BOOTSTRAP_BANNER}

# Planning Rosetta Stone — {project_name}

Search phrase: **Planning Rosetta Stone** · Hook: `planning.rosetta`

## Core hooks

| HOOK_ID | Meaning |
|---------|---------|
| `planning.rosetta` | This legend |
| `context.delta` | Holistic / macro / micro docs |
| `cursor.rules` | `.cursor/rules/*.mdc` |
| `change.impact` | Impact packets before edits |
| `change.bugfix_mode` | Bugfix impact mode |
{optional_rows}
## Primary files

{primary_files}
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


def _micro_readme(*, spec_kit: bool) -> str:
    starter = ""
    if spec_kit:
        starter = "\n**Starter feature:** [example-feature.md](./example-feature.md)\n"
    else:
        starter = "\nAdd feature briefs here when Spec Kit is enabled.\n"
    return f"""{BOOTSTRAP_BANNER}

# Micro Briefs

One file per feature: `docs/delta/20_micro/<feature>.md`
{starter}"""


def _micro_example() -> str:
    from hive_planner.rosetta_nav import delta_micro_navigation_block

    return f"""{BOOTSTRAP_BANNER}

# Feature Micro Brief: example-feature

**Hook:** `spec.flow`

{delta_micro_navigation_block("example-feature")}

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
    from hive_planner.rosetta_nav import spec_navigation_block

    return f"""{BOOTSTRAP_BANNER}

# Spec: example-feature

**Hook:** `spec.flow`  
**Status:** draft  
**Delta:** [example-feature.md](../../delta/20_micro/example-feature.md)

{spec_navigation_block("example-feature")}

## What

Replace this spec with the first real feature for your project.

## Requirements

### R1 — Placeholder

Define acceptance criteria here.

## Out of scope

Production implementation until spec is reviewed.
"""


def _example_plan() -> str:
    from hive_planner.rosetta_nav import plan_navigation_block

    return f"""{BOOTSTRAP_BANNER}

# Plan: example-feature

**Hook:** `spec.flow`  
**Spec:** [spec.md](./spec.md)

{plan_navigation_block("example-feature")}

## Approach

Describe technical approach after spec review.
"""


def _example_tasks() -> str:
    from hive_planner.rosetta_nav import tasks_navigation_block

    return f"""{BOOTSTRAP_BANNER}

# Tasks: example-feature

{tasks_navigation_block("example-feature")}

## Task 1 — Replace scaffold

- [ ] Update holistic/macro docs
- [ ] Rename `example-feature` to your feature id
- [ ] Set active feature in `AGENTS.md`

## After each implementation task — Integration wiring audit (required)

- [ ] Traced caller → handler → core (no layer break)
- [ ] No false success when a sub-step failed or was skipped
- [ ] Integration-level validation evidence attached
- [ ] See `.cursor/rules/integration-wiring-audit.mdc`

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
    agent_handoff: str | None = None,
    spec_kit: bool | None = None,
    continual_learning: bool | None = None,
    cl_runtime: str | None = None,
    implementation_loop_pack: str | None = None,
    agnostic_loop: bool = False,
) -> BootstrapResult:
    from hive_planner.agent_handoff import AGENT_HANDOFF_OFF, AGENT_HANDOFF_UNIFIED, integrations_from_mode, normalize_agent_handoff_mode
    from hive_planner.cl_runtime import CL_RUNTIME_CURSOR, normalize_cl_runtime

    resolved_cl_runtime = normalize_cl_runtime(cl_runtime or CL_RUNTIME_CURSOR)
    if agent_handoff is not None:
        mode = normalize_agent_handoff_mode(agent_handoff)
        spec_kit_enabled, continual_learning_enabled = integrations_from_mode(mode)
    elif spec_kit is not None or continual_learning is not None:
        spec_kit_enabled = bool(spec_kit)
        continual_learning_enabled = bool(continual_learning) if continual_learning is not None else spec_kit_enabled
        if continual_learning_enabled and not spec_kit_enabled:
            continual_learning_enabled = False
        if spec_kit_enabled:
            continual_learning_enabled = True
            mode = AGENT_HANDOFF_UNIFIED
        else:
            mode = AGENT_HANDOFF_OFF
    else:
        mode = AGENT_HANDOFF_UNIFIED
        spec_kit_enabled, continual_learning_enabled = integrations_from_mode(mode)
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

    partial_hive = (target / "START_HERE.md").is_file() or (target / "docs" / "planning-rosetta-stone.md").is_file()
    if target.exists() and any(target.iterdir()) and not force and not partial_hive:
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
            spec_kit=spec_kit_enabled,
            continual_learning=continual_learning_enabled,
            cl_runtime=resolved_cl_runtime,
            implementation_loop_pack=implementation_loop_pack,
            agnostic_loop=agnostic_loop,
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
    spec_kit: bool,
    continual_learning: bool,
    cl_runtime: str = "cursor",
    implementation_loop_pack: str | None = None,
    agnostic_loop: bool = False,
) -> None:
    from hive_planner.cl_runtime import CL_RUNTIME_CURSOR, normalize_cl_runtime
    from hive_planner.vendor_sync import deploy_unified_vendor_artifacts

    resolved_cl_runtime = normalize_cl_runtime(cl_runtime or CL_RUNTIME_CURSOR)
    templates: list[tuple[str, str]] = [
        ("START_HERE.md", _start_here(project_name)),
        ("AGENTS.md", _agents_md(project_name, target, spec_kit=spec_kit, continual_learning=continual_learning)),
        ("README.md", _readme(project_name)),
        (
            "docs/planning-rosetta-stone.md",
            _planning_rosetta(project_name, spec_kit=spec_kit, continual_learning=continual_learning),
        ),
        ("docs/delta/00_holistic.md", _holistic(project_name)),
        ("docs/delta/10_macro.md", _macro(project_name)),
        ("docs/delta/20_micro/README.md", _micro_readme(spec_kit=spec_kit)),
        ("docs/change-impact/policy.md", _change_impact_policy()),
        ("docs/change-impact/project-map.md", _project_map()),
        ("docs/change-impact/test-map.md", _test_map()),
        ("context-library/indexes/document-index.json", json.dumps({"documents": []}, indent=2) + "\n"),
        ("context-library/indexes/chunk-index.json", json.dumps({"chunks": []}, indent=2) + "\n"),
        ("context-library/indexes/embedding-index.json", json.dumps({"embeddings": [], "model_id": None}, indent=2) + "\n"),
    ]
    if spec_kit:
        templates.extend(
            [
                ("docs/delta/20_micro/example-feature.md", _micro_example()),
                ("docs/specs/example-feature/spec.md", _example_spec()),
                ("docs/specs/example-feature/plan.md", _example_plan()),
                ("docs/specs/example-feature/tasks.md", _example_tasks()),
            ]
        )
    if continual_learning:
        templates.append(("docs/proposals/candidates-template.md", _candidates_template()))
    if spec_kit and continual_learning:
        _copy_cl_spec_integration_doc(
            source_paths,
            target,
            force=force,
            written=written,
            warnings=warnings,
        )
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
    if spec_kit:
        _copy_file(kit / "spec-kit-agent-integration.md", target, "spec-kit-agent-integration.md", force=force, written=written)
        if not (target / "spec-kit-agent-integration.md").exists():
            warnings.append("Missing starter-kit/spec-kit-agent-integration.md — skipped copy")

    _copy_bootstrap_rules(
        source_paths,
        target,
        force=force,
        written=written,
        warnings=warnings,
        spec_kit=spec_kit,
        continual_learning=continual_learning,
    )
    if implementation_loop_pack is not None:
        _install_implementation_loop_artifacts(target, implementation_loop_pack, force=force, written=written, warnings=warnings)
    if agnostic_loop:
        _install_agnostic_loop_artifacts(target, written=written, warnings=warnings)

    if profile == "full":
        _write_full_profile(
            target,
            project_name=project_name,
            package_slug=_package_slug(target.name),
            force=force,
            written=written,
        )

    from hive_planner.agent_handoff import AGENT_HANDOFF_OFF, AGENT_HANDOFF_UNIFIED
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
        agent_handoff_mode=AGENT_HANDOFF_UNIFIED if (spec_kit and continual_learning) else AGENT_HANDOFF_OFF,
        cl_runtime=resolved_cl_runtime if (spec_kit and continual_learning) else None,
    )
    written.append(meta_path.relative_to(target).as_posix())
    if spec_kit and continual_learning:
        from hive_planner.cl_runtime import requires_cursor_plugin
        from hive_planner.project_profile import set_project_cl_source

        deploy_unified_vendor_artifacts(
            source_paths.root,
            target,
            force=force,
            written=written,
            warnings=warnings,
            cl_runtime=resolved_cl_runtime,
        )
        if requires_cursor_plugin(resolved_cl_runtime):
            _copy_cursor_workspace_plugin_hooks(
                target,
                force=force,
                written=written,
                warnings=warnings,
            )
            try:
                set_project_cl_source(target, "vendored")
            except ValueError:
                pass
        from hive_planner.cl_runtime import set_project_cl_runtime

        try:
            set_project_cl_runtime(target, resolved_cl_runtime)
            if ".hive/project.json" not in written:
                written.append(".hive/project.json")
        except ValueError:
            pass

    _install_bug_hunt_artifacts(target, force=force, written=written, warnings=warnings)


def deploy_agent_handoff_scaffold(
    source_paths: RepoPaths,
    target: Path,
    *,
    project_name: str | None = None,
    force: bool = False,
    cl_runtime: str | None = None,
) -> tuple[list[str], list[str]]:
    """Deploy unified Spec Kit + Continual Learning artifacts into an existing Hive project."""
    from hive_planner.agent_handoff import AGENT_HANDOFF_UNIFIED, apply_agent_handoff_mode
    from hive_planner.cl_runtime import CL_RUNTIME_CURSOR, normalize_cl_runtime, requires_cursor_plugin, resolve_cl_runtime
    from hive_planner.project_profile import read_project_profile, resolve_project_profile

    target = target.resolve()
    resolved_cl_runtime = normalize_cl_runtime(cl_runtime or resolve_cl_runtime(target) or CL_RUNTIME_CURSOR)
    if not (target / "START_HERE.md").is_file():
        raise BootstrapError(f"Not a Hive project (missing START_HERE.md): {target}")
    meta = resolve_project_profile(target)
    name = project_name or (meta.project_name if meta else target.name)
    written: list[str] = []
    warnings: list[str] = []
    templates: list[tuple[str, str]] = [
        ("docs/delta/20_micro/example-feature.md", _micro_example()),
        ("docs/specs/example-feature/spec.md", _example_spec()),
        ("docs/specs/example-feature/plan.md", _example_plan()),
        ("docs/specs/example-feature/tasks.md", _example_tasks()),
        ("docs/proposals/candidates-template.md", _candidates_template()),
    ]
    for rel, content in templates:
        _write_text(target, rel, content, force=force, written=written)
    kit = _starter_kit_dir(source_paths.root)
    _copy_file(kit / "spec-kit-agent-integration.md", target, "spec-kit-agent-integration.md", force=force, written=written)
    if not (target / "spec-kit-agent-integration.md").is_file():
        warnings.append("Missing starter-kit/spec-kit-agent-integration.md — not copied")
    _copy_cl_spec_integration_doc(
        source_paths,
        target,
        force=force,
        written=written,
        warnings=warnings,
    )
    _copy_bootstrap_rules(
        source_paths,
        target,
        force=force,
        written=written,
        warnings=warnings,
        spec_kit=True,
        continual_learning=True,
    )
    from hive_planner.cartridge_promote import _append_tasks_wiring_audit_if_missing

    example_tasks = target / "docs" / "specs" / "example-feature" / "tasks.md"
    if _append_tasks_wiring_audit_if_missing(example_tasks):
        rel = "docs/specs/example-feature/tasks.md"
        if rel not in written:
            written.append(rel)
    existing = read_project_profile(target)
    apply_agent_handoff_mode(
        target,
        AGENT_HANDOFF_UNIFIED,
        hive_planner_version=existing.hive_planner_version if existing else None,
    )
    from hive_planner.project_profile import set_project_cl_source

    if requires_cursor_plugin(resolved_cl_runtime):
        try:
            set_project_cl_source(target, "vendored")
        except ValueError:
            pass
    written.append(".hive/project.json")
    from hive_planner.cl_runtime import set_project_cl_runtime
    from hive_planner.vendor_sync import deploy_unified_vendor_artifacts

    try:
        set_project_cl_runtime(target, resolved_cl_runtime)
    except ValueError:
        pass
    deploy_unified_vendor_artifacts(
        source_paths.root,
        target,
        force=force,
        written=written,
        warnings=warnings,
        cl_runtime=resolved_cl_runtime,
    )
    if requires_cursor_plugin(resolved_cl_runtime):
        _copy_cursor_workspace_plugin_hooks(
            target,
            force=force,
            written=written,
            warnings=warnings,
        )
    _install_bug_hunt_artifacts(target, force=force, written=written, warnings=warnings)
    return sorted(set(written)), warnings

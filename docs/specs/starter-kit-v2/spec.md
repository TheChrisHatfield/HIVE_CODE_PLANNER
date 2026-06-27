# Spec: starter-kit-v2

**Hook:** `workflow.project_bootstrap`, `repo.starter_files`  
**Status:** active  
**Delta:** [starter-kit-v2.md](../../delta/20_micro/starter-kit-v2.md)

## What

Extend `hive_planner init` with a **full** starter-kit profile: Python project layout, CI stub, optional git init.

## Requirements

### R1 — Profile flag

`hive_planner init --profile full` adds starter-kit v2 artifacts on top of v1 scaffold.

Default `--profile minimal` preserves v1 behavior unchanged.

### R2 — Full profile artifacts

Write:

- `pyproject.toml` (setuptools + pytest dev extra)
- `.gitignore` (Python + Hive artifact paths)
- `src/<package>/__init__.py` (slug from target folder name)
- `tests/test_placeholder.py` (import smoke test)
- `.github/workflows/ci.yml` (Hive handoff job + project pytest job)

### R3 — Git init (optional)

`--git-init` runs `git init` after scaffold when git is on PATH.

Skip with warning when `.git` already exists or git fails.

### R4 — Safety

All v1 safety rules unchanged (non-empty target, Hive source tree guard).

### R5 — Docs

`docs/project-bootstrap-guide.md` documents profiles and CI variable setup.

## Out of scope

Auto `pip install` in target, cloning Hive into target, cloud deploy, multiple profile presets beyond minimal/full.

# Spec: project-bootstrap-v1

**Hook:** `workflow.project_bootstrap`  
**Status:** active  
**Delta:** [project-bootstrap-v1.md](../../delta/20_micro/project-bootstrap-v1.md)

## What

CLI to bootstrap a new Hive agent profile directory from starter templates.

## Requirements

### R1 — init command

`hive_planner init --target PATH [--name NAME] [--force]`

### R2 — Scaffold

Write START_HERE, AGENTS, slim Rosetta, Delta/spec/change-impact/context-library skeleton, Cursor rules.

### R3 — Detectability

Bootstrapped root must pass `is_repo_root()`.

### R4 — Safety

Fail on non-empty target unless `--force`; fail when already initialized unless `--force`.

### R5 — Docs

`docs/project-bootstrap-guide.md` documents one-folder-one-profile workflow.

## Out of scope

Auto `pip install` in target, git init, cloud deploy.

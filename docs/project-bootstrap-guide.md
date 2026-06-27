# Project Bootstrap Guide

**Hook:** `workflow.project_bootstrap`

One folder = one Cursor/Hive profile. Use `hive_planner init` to scaffold a new project root that agents can load via `START_HERE.md` and the Planning Rosetta Stone.

## Command

From your Hive Code Planner checkout:

```powershell
cd d:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER
py -3.11 -m hive_planner init --target D:\projects\my-app --name "My App"
```

Optional `--force` rewrites bootstrap-managed files in a non-empty directory.

## Profiles

| Profile | Flag | Adds |
|---------|------|------|
| **minimal** (default) | `--profile minimal` | v1 scaffold only (START_HERE, Delta, rules, context-library) |
| **full** (starter-kit v2) | `--profile full` | `pyproject.toml`, `src/<pkg>/`, `tests/`, `.gitignore`, `.github/workflows/ci.yml` |

Full profile example:

```powershell
py -3.11 -m hive_planner init --target D:\projects\my-app --name "My App" --profile full --git-init
```

`--git-init` runs `git init` when git is available (skips with warning if `.git` already exists).

### CI on bootstrapped repos

The generated workflow expects a GitHub repository variable **`HIVE_PLANNER_PATH`** pointing to your Hive Code Planner checkout (absolute path on the runner or a checked-out sibling path).

Set it under **Settings → Secrets and variables → Actions → Variables**, then push to enable Hive handoff checks in CI.

## What gets created

| Path | Purpose |
|------|---------|
| `START_HERE.md` | Agent loader entrypoint |
| `AGENTS.md` | Durable operating guidance |
| `docs/planning-rosetta-stone.md` | Hook legend (project-scoped) |
| `docs/delta/` | Holistic, macro, micro briefs |
| `docs/specs/example-feature/` | Spec Kit starter trio |
| `docs/change-impact/` | Impact policy + maps |
| `.cursor/rules/` | Architecture, task, validation rules |
| `context-library/` | Empty ingest scaffold |
| `pyproject.toml` | **full profile only** — setuptools + pytest |
| `src/<package>/` | **full profile only** — importable package stub |
| `tests/` | **full profile only** — placeholder pytest |
| `.github/workflows/ci.yml` | **full profile only** — Hive handoff + project tests |

## Hive CLI on the new project

Install Hive once from the planner repo:

```powershell
cd d:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER
py -3.11 -m pip install -e ".[dev]"
```

Run commands from the **new project root** with `--root` or after `cd` into it:

```powershell
cd D:\projects\my-app
py -3.11 -m hive_planner --root . ci-check
py -3.11 -m hive_planner --root . impact --feature example-feature --files src/
```

## Perplexity thread → project mapping

- One Perplexity planning thread → one bootstrapped repo folder
- Rename `example-feature` to your feature id before active development
- Set **Active feature** in `AGENTS.md` when Spec Kit artifacts are ready

## Validation

After init:

```powershell
py -3.11 -m hive_planner init --target /tmp/hive-test --name demo
# In Python/tests: is_repo_root(target) is True
```

# Hive Code Planner

**Hive Code Planner** is a local desktop app and CLI that helps you run **Cursor** coding projects with a clear planning layout before agents write code.

It scaffolds and maintains:

- **Spec Kit** — specs, plans, and tasks (`docs/specs/`)
- **Continual Learning** — durable operational memory in `AGENTS.md`
- **Hive Delta docs** — holistic / macro / micro planning layers
- **Cartridge compile** — turn research/docs into agent-ready context

Think of it as a **control panel** for agentic coding: create or link a project, open it in Cursor, run health checks, and keep planning files aligned with the code.

## Using the desktop app (plain-English guide)

Full walkthrough: **[`scripts/README.md`](scripts/README.md)** (same guide appears on the **Home** tab inside the app).

Quick launch: double-click `scripts\HivePlanner.lnk`, or run the portable build from `dist\HivePlannerPortable\HivePlanner.exe`.

## Repository root

```
d:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER
```

## Agent startup

1. Read [`START_HERE.md`](START_HERE.md)
2. Load [`docs/planning-rosetta-stone.md`](docs/planning-rosetta-stone.md) — search **Planning Rosetta Stone** or hook `planning.rosetta`
3. Read [`AGENTS.md`](AGENTS.md)

## Active development

**Feature:** `roadmap-complete-v4` — **v1.3.0 — Stage 9 complete (22/22)**

| Stage | Hooks | Command |
|-------|-------|---------|
| 9B | `workflow.tools` | `py -3.11 -m hive_planner roadmap-status` |
| 9A | `integration.unified_handoff` | `py -3.11 -m hive_planner init --agent-handoff unified --target <path>` |
| 9A | `integration.unified_handoff` | `py -3.11 -m hive_planner unified-verify` |
| 8B | `workflow.tools` | `py -3.11 -m hive_planner roadmap-status` |
| 8A | `workflow.project_bootstrap` | `py -3.11 -m hive_planner init --profile full --git-init --target <path>` |
| 7F | `workflow.tools` | `py -3.11 -m hive_planner ci-check` |
| 7E | `workflow.project_bootstrap` | `py -3.11 -m hive_planner init --target <path> --name "My App"` |

```powershell
py -3.11 -m pytest -v
py -3.11 -m hive_planner roadmap-status
py -3.11 -m hive_planner ci-check
```

See [docs/delta/STAGE_ROADMAP.md](docs/delta/STAGE_ROADMAP.md).

## Layout

| Path | Purpose |
|------|---------|
| `START_HERE.md` | Agent context loader and read order |
| `AGENTS.md` | Durable agent operating guidance |
| `docs/planning-rosetta-stone.md` | Planning Rosetta Stone — hook legend |
| `docs/thread-outline-with-metatags.md` | Meta-tag anchor map |
| `docs/HIVE_PLANNING_DEV.md` | Full planning thread archive |
| `docs/` | Architecture, decisions, and reference notes |
| `plans/` | Planning artifacts, specs, and task breakdowns |
| `src/` | Source code and scripts |
| `.cursor/` | Cursor IDE rules and project guidance |

## Local Git workflow

```powershell
cd d:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER

# Check status
git status

# Stage and commit changes
git add .
git commit -m "Describe your change"

# View history
git log --oneline --graph --decorate
```

## Notes

- Treat this folder as the canonical project root.
- Do not scatter project files outside this directory unless explicitly required.
- Add a remote later with `git remote add origin <url>` if you want GitHub sync.

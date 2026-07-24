# Hive Code Planner

**Hive Code Planner is a local context compiler for AI coding agents** — not another chatbot wrapper.

Long planning threads (Perplexity, research chats, PDFs) are too noisy for Cursor to use directly. Agents lose the thread between mission, architecture, and the next file to edit. Hive turns that noise into **Git-native, reviewable structure** agents can load in one hop.

## What’s novel

| Idea | Why it matters |
|------|----------------|
| **Planning Rosetta Stone** | Hook IDs (`planning.rosetta`, `context.delta`, …) map any question to the right docs — agents don’t guess. |
| **Delta layers** | Holistic → Macro → Micro → code stays traceable; primary truth is always the active layer + spec/plan/tasks. |
| **Cartridge compile** | Research and source docs compile into a portable `cartridge/` pack agents can reload from Git. |
| **Symbiotic Spec Kit + Continual Learning** | Behavioral truth lives in Spec Kit; operational memory in `AGENTS.md` — with wiring audits so “done” means actually wired. |

It ships as a **desktop app + CLI** that scaffolds Cursor projects, opens them, runs health checks, and keeps planning files aligned with the code — all on your machine.

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

## GitHub

Remote: https://github.com/TheChrisHatfield/HIVE_CODE_PLANNER

```powershell
cd d:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER
git status
git add .
git commit -m "Describe your change"
git push
```

## Notes

- Treat this folder as the canonical project root.
- Do not scatter project files outside this directory unless explicitly required.

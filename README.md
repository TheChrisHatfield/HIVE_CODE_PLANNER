# Hive Code Planner

A strict prompt does not give a coding agent enough information to build the correct software. GitHub Spec Kit closes that gap. Spec Kit turns the prompt into three artifacts: a specification, a technical plan, and a task list. The coding agent implements those artifacts.

The specification still depends on the context the agent has when it writes the specification. Hive Planner supplies that context. Three inputs feed the specification:

- **Project memory.** Continual memory records how this project specifies and builds software. The agent reads that record when it writes the next specification.
- **Source documents.** You can add text files and PDFs. Hive Planner indexes the text, runs optical character recognition (OCR) on scanned pages, and uses embedding search to return the passages that match the current question.
- **Long ideation.** You can develop an idea in another system. That text is often too long for an agent to load in one pass. The Rosetta Stone indexes the text by concept. The agent opens the section that matches the question. A search system does this job with embeddings. The Rosetta Stone does it with a structured index.

Hive Planner passes this context to Spec Kit. Spec Kit writes the specification, the plan, and the tasks. The coding agent implements the tasks.

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

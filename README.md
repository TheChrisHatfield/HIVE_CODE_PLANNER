# HIVE — ( Hierarchical, Inference, Versatile Engine ) Code Planner

Prompting alone does not give an agentic coding agent enough context for successful deployment in the software development process. Spec-Driven Development closes the gap by providing a reviewable baseline before an agent begins to code. HIVE Code Planner ( Hierarchical, Inference, Versatile, Engine )
provides the next steps by giving users the ability to effectively ideate and cross correlate source documents in software development process. 

Specification still depends on the context the agent has when it writes. Hive Code Planner supplies the context with three input feeds.

- **Project memory.** Continual memory records how this project specifies and builds software. The agent reads that record when it writes the next specification.
- **Source documents.** You can add text files and PDFs. Hive Code Planner indexes the text, runs optical character recognition (OCR) on scanned pages, and uses embedding search to return the passages that match the current question.
- **Long ideation.** You can develop an idea in another system. That text is often too long for an agent to load in one pass. The Rosetta Stone indexes the text by concept. The agent opens the section that matches the question. A search system does this job with embeddings. The Rosetta Stone does it with a structured index.

The system passes the context to Spec Kit. Spec Kit writes the specification, the plan, and the tasks. The coding agent implements the tasks.

## Using the desktop app 

Full walkthrough: **[`scripts/README.md`](scripts/README.md)** (same guide appears on the **Home** tab inside the app).

Quick launch: double-click `scripts\HivePlanner.lnk`, or run the portable build from `dist\HivePlannerPortable\HivePlanner.exe`.

## Agent startup

1. Read [`START_HERE.md`](START_HERE.md)
2. Load [`docs/planning-rosetta-stone.md`](docs/planning-rosetta-stone.md) — search **Planning Rosetta Stone** or hook `planning.rosetta`
3. Read [`AGENTS.md`](AGENTS.md)

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



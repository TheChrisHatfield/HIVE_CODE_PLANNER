# Holistic Context

**Hook:** `context.delta` | **Feature:** repo-wide

## Mission

Hive Code Planner is a local, Git-native system that turns upstream planning research into structured, agent-readable context so coding agents can implement with less drift.

## Problem

Raw planning threads (Perplexity exports, long chats) are too noisy for direct coding. Agents lose alignment between mission, architecture, and task-level work.

## Success Criteria

- Agents load **Planning Rosetta Stone** (`planning.rosetta`) and find the right context layer in one step.
- Source documents in `context-library/` compile into reviewable cartridge artifacts.
- Delta docs, specs, and tasks stay traceable from holistic → macro → micro → code.
- The repo runs locally without requiring a GitHub remote.
- Stages 1–6 compiler roadmap is complete (v1.0.0); validate with `roadmap-status`.

## Non-Goals

- Cloud-hosted multi-user platform (v1).
- Optional hybrid embedding retrieval (`ingest --embed`); keyword-only fallback when index empty.
- Replacing Spec Kit or Cursor — this repo orchestrates context for them.

## Invariants

- Primary truth = active Delta + spec/plan/tasks.
- Secondary truth = `AGENTS.md` + `.cursor/rules/`.
- Tertiary truth = `source-context.md` and context-library excerpts (optional, never overrides primary).
- All project files live under `d:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`.

## Constraints

- Local Windows development environment.
- Python 3.10+ for compiler tooling.
- Markdown-first artifacts for Git review and agent loading.

## Core Terms

| Term | Meaning |
|------|---------|
| **Delta** | Holistic / Macro / Micro context layers |
| **Cartridge** | Portable context pack under `cartridge/` |
| **Rosetta Stone** | `docs/planning-rosetta-stone.md` hook legend |
| **Compiler** | `src/hive_planner` — ingests sources, emits cartridge |

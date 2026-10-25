<!-- DRAFT: review before promoting -->

<!-- AUTO-SYNC: from docs/delta/10_macro.md -->

# Macro Architecture

**Hook:** `context.delta`, `compiler.pipeline`

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before using this Delta layer.

- **Hook:** `context.delta`
- **Unlocks:** micro briefs and spec.flow
- **Next:** [`20_micro/`](./) feature briefs

## System Overview

Hive Code Planner has five cooperating subsystems: **agent loader**, **context library**, **cartridge compiler**, **cartridge output**, and **shared graph memory**. Planning docs and Rosetta hooks define behavior; Python tooling automates ingestion and emission.

## Subsystems

### Agent Loader

| | |
|--|--|
| **Purpose** | Tell coding agents what to read and in what order |
| **Inputs** | Rosetta Stone, START_HERE, AGENTS.md, active spec/tasks |
| **Outputs** | Scoped context loading decisions |
| **Dependencies** | Delta docs, `.cursor/rules/` |
| **Failure modes** | Agent reads raw archive instead of distilled files |

### Context Library

| | |
|--|--|
| **Purpose** | Store tertiary source documents |
| **Inputs** | `.md`, `.txt`, `.pdf`, `.docx` (PDF/DOCX require optional deps) |
| **Outputs** | Normalized markdown, metadata, chunk indexes |
| **Dependencies** | `context-library/sources/` layout |
| **Failure modes** | Tertiary context overrides active spec |

Path: `context-library/` — see [context-library-structure-guide.md](../context-library-structure-guide.md).

### Cartridge Compiler

| | |
|--|--|
| **Purpose** | Discover → normalize → chunk → index → emit cartridge |
| **Inputs** | Source files, optional feature query |
| **Outputs** | `cartridge/manifest.json`, indexes, `source-context.md` |
| **Dependencies** | `src/hive_planner/` |
| **Failure modes** | Stale indexes after source updates |

### Cartridge Output

| | |
|--|--|
| **Purpose** | Git-carried context pack for agents |
| **Inputs** | Compiler emission |
| **Outputs** | `cartridge/*` per [cartridge-schema-v1.md](../cartridge-schema-v1.md) |
| **Dependencies** | Compiler, Delta docs |
| **Failure modes** | Draft cartridge promoted without review |

### Shared Graph Memory

| | |
|--|--|
| **Purpose** | Staging + permanent typed node/edge store for cross-cutting knowledge (`memory.shared_graph`) |
| **Inputs** | Repo reflection bundles (JSON/JSONL graph records) |
| **Outputs** | `.hive/shared-memory/staging/` + `permanent/` JSONL, `manifest.json` |
| **Dependencies** | `src/hive_planner/graph_store.py`, CLI `graph *` |
| **Failure modes** | Dangling edges; unvalidated dumps into permanent without promote |

See [shared-graph-memory-v1.md](./20_micro/shared-graph-memory-v1.md).

## Data Contracts

- **doc_id**: stable hash prefix from relative source path
- **manifest.json**: `schema_version: cartridge.v1`
- **chunk-index.json**: list of `{ chunk_id, doc_id, heading_path, text, keywords }`
- **document-index.json**: list of `{ doc_id, source_path, format, title, content_hash }`
- **graph node/edge**: JSONL lines per [shared-graph-memory-v1 spec](../specs/shared-graph-memory-v1/spec.md); store manifest `schema_version: shared-graph.v1`

## Agent Roles

| Agent | Role |
|-------|------|
| Planning (Perplexity) | Upstream research and blueprint |
| Spec (Spec Kit) | spec.md / plan.md / tasks.md |
| Coding (Cursor) | Implementation against active task |
| Compiler (automated) | Ingest sources, emit cartridge |

## Workflow Graph

```text
Perplexity research
  -> Delta docs + specs (manual or assisted)
  -> context-library/sources/ (reference docs)
  -> hive_planner ingest (compiler)
  -> cartridge/ + indexes
  -> Cursor reads START_HERE + Rosetta + active task
  -> implement one micro task
  -> validate -> optional AGENTS.md promotion
```

## Risks

- Over-scoping v1 with PDF/DOCX before MD/TXT pipeline is stable.
- Cartridge emission without human review of distilled content.
- Duplicate truth between `HIVE_PLANNING_DEV.md` and extracted docs.

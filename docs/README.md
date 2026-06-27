# Docs

Planning and architecture reference for Hive Code Planner.

## Agent entry points

| File | Hook / search | Role |
|------|---------------|------|
| [planning-rosetta-stone.md](./planning-rosetta-stone.md) | `planning.rosetta`, **Planning Rosetta Stone** | Top-level legend and hook index |
| [thread-outline-with-metatags.md](./thread-outline-with-metatags.md) | meta tags / `HOOK_ID` | Condensed anchor map |
| [HIVE_PLANNING_DEV.md](./HIVE_PLANNING_DEV.md) | — | Full Perplexity planning thread archive |

Repo loader: [`../START_HERE.md`](../START_HERE.md)

## Extracted planning artifacts

| File | Hook |
|------|------|
| [agentic-coding-blueprint.md](./agentic-coding-blueprint.md) | `workflow.tools` |
| [context-handoff-and-automation.md](./context-handoff-and-automation.md) | `workflow.git_handoff` |
| [cartridge-schema-v1.md](./cartridge-schema-v1.md) | `context.cartridge_schema` |
| [cartridge-schema-v1-updated.md](./cartridge-schema-v1-updated.md) | `context.cartridge_schema` |
| [cartridge-document-sourcing-extension.md](./cartridge-document-sourcing-extension.md) | `context.document_sourcing` |
| [context-library-structure-guide.md](./context-library-structure-guide.md) | `context.library` |
| [document-context-metadata-standard.md](./document-context-metadata-standard.md) | `context.metadata` |
| [cartridge-compiler-implementation.md](./cartridge-compiler-implementation.md) | `compiler.pipeline` |
| [change-impact-lift.md](./change-impact-lift.md) | `change.impact` |

Starter kit: [`../starter-kit/`](../starter-kit/)

## Usage

Tell the coding agent: **Find Planning Rosetta Stone** or **Use hook `planning.rosetta`**.

Load `planning-rosetta-stone.md` into normal context, then follow `PRIMARY FILES` and `UNLOCKS`.

## Other

- [ARCHITECTURE.md](./ARCHITECTURE.md) — system architecture overview

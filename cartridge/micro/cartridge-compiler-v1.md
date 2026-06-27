<!-- AUTO-SYNC: from docs/delta/20_micro/cartridge-compiler-v1.md -->

# Feature Micro Brief: cartridge-compiler-v1

**Hook:** `compiler.pipeline`, `context.cartridge`

## Feature Name

Cartridge Compiler v1 — ingest MD/TXT sources, build indexes, emit cartridge skeleton.

## Holistic Link

Supports mission: structured context transport from planning sources to agent-loadable cartridge.

## Macro Link

Implements the **Cartridge Compiler** subsystem (discover, normalize, chunk, index, emit).

## Scope

| In scope | Out of scope |
|----------|--------------|
| `src/hive_planner/` Python package | PDF/DOCX normalization |
| MD + TXT under `context-library/sources/` | Embedding / vector DB |
| JSON document + chunk indexes | Auto-promotion to AGENTS.md |
| CLI: `ingest`, `emit` | Full Spec Kit artifact generation |

**Files:** `src/hive_planner/*`, `tests/*`, `pyproject.toml`, `context-library/**`, `cartridge/**`

## Inputs / Outputs

- **In:** Files in `context-library/sources/**/*.md|txt`
- **Out:** `context-library/normalized/`, `context-library/indexes/`, `cartridge/manifest.json`, `cartridge/source-context.md`

## Acceptance Criteria

- [x] `python -m hive_planner ingest` processes all MD/TXT sources
- [x] Normalized files and metadata written under `context-library/normalized/`
- [x] `document-index.json` and `chunk-index.json` updated
- [x] `python -m hive_planner emit --feature cartridge-compiler-v1` writes cartridge manifest + source-context
- [x] `pytest` passes for discovery, chunker, and ingest integration

## Edge Cases

- Empty source directory → graceful message, no crash
- Binary or unreadable file → skip with warning
- Re-ingest same file → update doc_id hash, replace chunks

## Validation

```powershell
cd d:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER
py -3.11 -m pip install -e ".[dev]"
py -3.11 -m pytest
py -3.11 -m hive_planner ingest
py -3.11 -m hive_planner emit --feature cartridge-compiler-v1
```

> Use `py -3.11` (or 3.12+) — default `python` on this machine may be 3.9.

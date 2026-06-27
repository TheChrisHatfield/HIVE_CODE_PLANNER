# Feature Micro Brief: cartridge-compiler-v2

**Hook:** `context.document_sourcing`, `compiler.pipeline`, `context.metadata`

## Feature Name

Cartridge Compiler v2 — add PDF and DOCX ingestion with enriched chunk metadata and emitter limits.

## Holistic Link

Extends tertiary context sourcing so planning reference docs in common formats enter the same cartridge pipeline as MD/TXT.

## Macro Link

Extends **Context Library** and **Cartridge Compiler** subsystems per [10_macro.md](../10_macro.md).

## Scope

| In scope | Out of scope |
|----------|--------------|
| `.pdf`, `.docx` under `context-library/sources/` | HTML, CSV, PPTX |
| Optional deps: `pymupdf`, `python-docx` | Embeddings / vector DB |
| Nested `heading_path` (e.g. `Alpha > Beta`) | Full cartridge translator |
| Optional `page` on PDF chunks | Auto Delta seeding |
| Emitter: max 3 docs, max 8 excerpts | |

**Files:** `src/hive_planner/normalizers/*`, `chunker.py`, `emitter.py`, `config.py`, `models.py`, tests

## Inputs / Outputs

- **In:** PDF/DOCX in context library (+ existing MD/TXT)
- **Out:** Same normalized/indexed/cartridge flow as v1

## Acceptance Criteria

- [x] PDF and DOCX discovered and normalized when optional deps installed
- [x] Missing optional dep → clear warning for that format only; MD/TXT unaffected
- [x] Nested heading paths in chunk index
- [x] PDF chunks include `page` when available
- [x] Emitter respects max 3 docs / max 8 excerpts
- [x] Shared bug gate B1–B8 still pass
- [x] Stage 2 checks S2-B1 through S2-B5 pass

## Validation

```powershell
py -3.11 -m pip install -e ".[dev,pdf,docx]"
py -3.11 -m pytest -v
py -3.11 -m hive_planner ingest
py -3.11 -m hive_planner emit --feature cartridge-compiler-v2
```

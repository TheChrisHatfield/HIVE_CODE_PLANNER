# Feature Micro Brief: cartridge-compiler-v3

**Hook:** `context.document_sourcing`, `compiler.pipeline`, `context.metadata`

## Feature Name

Cartridge Compiler v3 — add HTML, CSV, and PPTX ingestion to the existing normalizer pipeline.

## Holistic Link

Completes the first-wave format set from [cartridge-compiler-implementation.md](../../cartridge-compiler-implementation.md) while keeping keyword retrieval (embeddings deferred to Stage 4D).

## Macro Link

Extends **Context Library** and **Cartridge Compiler** subsystems per [10_macro.md](../10_macro.md).

## Scope

| In scope | Out of scope |
|----------|--------------|
| `.html`, `.htm`, `.csv`, `.pptx` under `context-library/sources/` | Embeddings / vector DB |
| Optional deps: `beautifulsoup4` (HTML), `python-pptx` (PPTX) | Cartridge holistic/macro auto-emission |
| CSV via stdlib (no extra) | CI AGENTS.md automation |
| Same emitter limits (3 docs / 8 excerpts) | HTML/CSV/PPTX split across sub-stages |

**Files:** `src/hive_planner/normalizers/*`, `normalizer.py`, `config.py`, `chunker.py`, `pyproject.toml`, tests

## Inputs / Outputs

- **In:** HTML, CSV, PPTX in context library (+ existing MD/TXT/PDF/DOCX)
- **Out:** Same normalized/indexed/cartridge flow as v2

## Acceptance Criteria

- [x] HTML, CSV, PPTX discovered and normalized when deps available
- [x] Missing optional dep → warning for that format only; other formats unaffected
- [x] Empty HTML → skip with warning (S4A-B1)
- [x] Corrupt file or missing dep → skip, no crash (S4A-B2)
- [x] Headerless CSV → chunks under document body (S4A-B3)
- [x] Re-ingest preserves stable `doc_id` (S4A-B4)
- [x] Shared bug gate B1–B8 + all prior tests pass (S4A-B5)
- [x] Stage 4A checks S4A-B1 through S4A-B5 pass

## Validation

```powershell
py -3.11 -m pip install -e ".[dev,pdf,docx,html,pptx]"
py -3.11 -m pytest -v
py -3.11 -m hive_planner ingest
py -3.11 -m hive_planner emit --feature cartridge-compiler-v3
```

# Feature Micro Brief: cartridge-translator-v1

**Hook:** `context.cartridge`, `context.cartridge_schema`, `compiler.pipeline`

## Feature Name

Cartridge Translator v1 — rule-based classification of research text into cartridge draft files.

## Holistic Link

Bridges upstream research and structured Delta/spec artifacts without LLM dependency in v1.

## Macro Link

Adds **Translator** stage after compiler per [cartridge-schema-v1.md](../../cartridge-schema-v1.md) five-stage pipeline.

## Scope

| In scope | Out of scope |
|----------|--------------|
| Rule/keyword classifier: Holistic, Macro, Micro, Memory, Reject | LLM-based translation |
| CLI `hive_planner translate --input PATH --feature NAME` | Auto-promote to `docs/delta/` or specs |
| Draft emit under `cartridge/` | Overwrite existing primary truth files |
| JSON status contract per schema | Full Perplexity paste UI |

**Files:** `src/hive_planner/translator.py`, `cli.py`, tests (future)

## Inputs / Outputs

- **In:** Normalized markdown, chunk index, or raw research `.md`
- **Out:** Draft `cartridge/holistic.md`, `macro.md`, `micro/<feature>.md`, `memory.md`, optional `specs/<feature>.specseed.md`, translator status JSON

## Acceptance Criteria

- [x] Segments classified into five buckets using keyword rules from schema
- [x] Rejected segments excluded from emitted files
- [x] Draft files marked as proposals (header banner)
- [x] Does not modify `docs/delta/` or `docs/specs/` without explicit merge step
- [x] Unknown input path → clear error

## Validation

```powershell
py -3.11 -m hive_planner translate --input docs/delta/20_micro/cartridge-compiler-v3.md --feature cartridge-translator-v1
```

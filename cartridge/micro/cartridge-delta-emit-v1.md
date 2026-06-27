<!-- AUTO-SYNC: from docs/delta/20_micro/cartridge-delta-emit-v1.md -->

# Feature Micro Brief: cartridge-delta-emit-v1

**Hook:** `context.cartridge`, `context.delta`, `compiler.pipeline`

## Feature Name

Cartridge Delta Emit v1 — sync primary Delta docs into cartridge holistic/macro/micro on emit.

## Holistic Link

Completes deferred holistic/macro cartridge emission from compiler v1/v2 out-of-scope list while preserving Delta as primary truth.

## Macro Link

Extends **Cartridge emitter** per [cartridge-compiler-implementation.md](../../cartridge-compiler-implementation.md) and [cartridge-schema-v1.md](../../cartridge-schema-v1.md).

## Scope

| In scope | Out of scope |
|----------|--------------|
| `emit` writes `holistic.md`, `macro.md`, `micro/<feature>.md` from Delta | Reverse sync (cartridge → Delta) |
| AUTO-SYNC banner + skip draft/manual files | LLM summarization |
| `--force-delta` overwrite flag | Auto-write `AGENTS.md` or rules |
| Manifest `stats.delta_sync` status | Translator replacement |

**Files:** `src/hive_planner/delta_emit.py`, `emitter.py`, `cli.py`, `tests/test_delta_emit.py`

## Inputs / Outputs

- **In:** `docs/delta/00_holistic.md`, `10_macro.md`, `20_micro/<feature>.md`
- **Out:** `cartridge/holistic.md`, `macro.md`, `micro/<feature>.md`, manifest stats

## Acceptance Criteria

- [x] Emit syncs holistic + macro from Delta when targets missing or auto-sync marked
- [x] Skips files with draft/manual banners unless `--force-delta`
- [x] Micro brief synced when Delta micro file exists
- [x] Existing source-context + hybrid retrieval unchanged
- [x] Bug gate + full pytest regression

## Validation

```powershell
py -3.11 -m pytest tests/test_delta_emit.py -v
py -3.11 -m hive_planner emit --feature cartridge-delta-emit-v1
py -3.11 -m pytest -v
```

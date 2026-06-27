<!-- AUTO-SYNC: from docs/delta/20_micro/cartridge-pack-v1.md -->

# Feature Micro Brief: cartridge-pack-v1

**Hook:** `context.cartridge`, `context.cartridge_schema`, `compiler.pipeline`

## Feature Name

Cartridge Pack v1 — complete schema-aligned cartridge files on emit.

## Holistic Link

Fulfills cartridge schema required files beyond delta sync (Stage 5A).

## Macro Link

Extends **Cartridge emitter** per [cartridge-schema-v1.md](../../cartridge-schema-v1.md).

## Scope

| In scope | Out of scope |
|----------|--------------|
| `research-summary.md` from micro/spec | LLM summarization |
| `memory.md` from AGENTS durable facts | Auto-write AGENTS.md |
| `specs/<feature>.specseed.md` from spec | Reverse Delta promotion |
| `mappings/source-map.json` | Translator rewrite |
| Manifest `files` + `pack_sync` stats | Cloud hosting |

**Files:** `src/hive_planner/cartridge_pack.py`, `emitter.py`, `tests/test_cartridge_pack.py`

## Acceptance Criteria

- [x] Emit writes research-summary, memory, specseed, source-map
- [x] Skips draft/manual cartridge files unless `--force-delta`
- [x] Manifest lists emitted files and pack stats
- [x] Full pytest + ci-check regression

## Validation

```powershell
py -3.11 -m hive_planner emit --feature cartridge-pack-v1 --force-delta
py -3.11 -m pytest tests/test_cartridge_pack.py -v
```

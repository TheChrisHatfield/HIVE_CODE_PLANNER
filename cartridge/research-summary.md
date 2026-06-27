<!-- AUTO-SYNC: from docs/delta/20_micro/cartridge-pack-v1.md -->

# Research Summary

**Feature:** `cartridge-pack-v1`

## Problem statement

Extend `emit` to produce remaining cartridge schema files alongside delta sync and source-context.

## Key findings

Fulfills cartridge schema required files beyond delta sync (Stage 5A).

## Constraints

| In scope | Out of scope |
|----------|--------------|
| `research-summary.md` from micro/spec | LLM summarization |
| `memory.md` from AGENTS durable facts | Auto-write AGENTS.md |
| `specs/<feature>.specseed.md` from spec | Reverse Delta promotion |
| `mappings/source-map.json` | Translator rewrite |
| Manifest `files` + `pack_sync` stats | Cloud hosting |

**Files:** `src/hive_planner/cartridge_pack.py`, `emitter.py`, `tests/test_cartridge_pack.py`

## Risks

- Draft cartridge files require human review before Delta promotion.

## Open questions

```powershell
py -3.11 -m hive_planner emit --feature cartridge-pack-v1 --force-delta
py -3.11 -m pytest tests/test_cartridge_pack.py -v
```

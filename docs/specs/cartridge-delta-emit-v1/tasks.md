# Tasks: cartridge-delta-emit-v1

**Hook:** `spec.flow`

## Task 1 — Delta + spec ✅

- [x] Micro brief, spec, plan, tasks
- [x] Update loaders

## Task 2 — delta_emit module ✅

- [x] AUTO-SYNC banner + skip draft/manual
- [x] Holistic/macro/micro sync
- [x] `--force-delta` CLI flag

## Task 3 — Emitter integration ✅

- [x] `stats.delta_sync` in manifest
- [x] Return delta paths from emit

## Task 4 — Tests + bug gate ✅

- [x] `tests/test_delta_emit.py`
- [x] Embedding model_id mismatch fix
- [x] S5A-B1: skip draft
- [x] S5A-B2: auto-sync update
- [x] S5A-B3: full pytest regression

## Active task

**None** — Stage 5A complete. Next: `change-impact-v2` (Stage 5B).

## Bug gate (Stage 5A)

| Check | Test |
|-------|------|
| S5A-B1 skip draft | `test_sync_skips_draft_banner` |
| S5A-B2 auto-sync update | `test_auto_sync_updates_on_reemit` |
| S5A-B3 embedding model match | `test_select_chunks_respects_embedding_model_id` |
| S5A-B4 regression | full pytest |

## Validation log

```text
2026-06-21 — Stage 5A bug gate
- S5A-B1: test_sync_skips_draft_banner PASS
- S5A-B2: test_auto_sync_updates_on_reemit PASS
- S5A-B3: test_select_chunks_respects_embedding_model_id PASS
- S5A-B4: 79/79 pytest PASS
- Smoke: emit --feature cartridge-delta-emit-v1 --force-delta OK
2026-06-21 — post-v1.0.0 bug audit (Stage 5A)
- test_delta_emit.py: 7/7 PASS; S5A-B1..B4 verified
- Smoke: emit --force-delta OK
```

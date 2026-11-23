# Impact packet — PersonaPlex PP-T5 encoder last hop

**Date:** 2026-11-23  
**Hook:** `change.impact`, `change.validation`  
**Spec:** `docs/specs/PersonaPlex_migrate/spec.md` PP18 / PP-T5

## Change

Working-copy `ServerState._async_update_reference` posts `/embed`, holds frames at default 1, and calls `update_streaming_sum_tensors`. HTTP failure leaves duplex running. No `\x07` UI. RAGManager trigger remains PP-T6.

## Primary

- `code-improvements/personaplex-migrate/moshi/moshi/server.py`

## Secondary

- `tests/test_personaplex_migrate.py`

## Tests

- `py -3.11 -m pytest tests/test_personaplex_migrate.py -q`

Loop auto-continue after commit is a separate implementation-loop spec R12 amendment (`continue.json` `next-task`).

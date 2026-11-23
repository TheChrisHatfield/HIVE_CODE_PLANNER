# Impact packet — PersonaPlex PP-T6 RAGManager trigger

**Date:** 2026-11-23  
**Hook:** `change.impact`, `change.validation`  
**Spec:** `docs/specs/PersonaPlex_migrate/spec.md` PP6 / PP-T6

## Change

`handle_chat` hosts a session `TaskGroup`. Rule B (user→model text-token change with a non-empty last `user:` line) calls `RAGManager.trigger(..., wait_steps=0)` then `_async_update_reference`. `RAGManager.step()` clocks wait only; it is not the LLM. No `rag_token_id` 4. No R44/R45 VAD.

## Primary

- `code-improvements/personaplex-migrate/moshi/moshi/inference_utils/session_rag.py`
- `code-improvements/personaplex-migrate/moshi/moshi/server.py`

## Secondary

- `tests/test_personaplex_migrate.py`
- `code-improvements/personaplex-migrate/moshi/moshi/inference_utils/rag_manager.py` (unchanged API)

## Tests

- `py -3.11 -m pytest tests/test_personaplex_migrate.py -q`

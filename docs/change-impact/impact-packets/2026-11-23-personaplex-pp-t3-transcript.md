# Impact packet — PersonaPlex PP-T3 duplex transcript

**Date:** 2026-11-23  
**Hook:** `change.impact`, `change.validation`  
**Spec:** `docs/specs/PersonaPlex_migrate/spec.md` PP8 / PP-T3

## Change

Working-copy RAG context is `user:` / `moshi:` lines built from duplex LM text tokens (`TurnManager`), not moshi-rag `stt/`. `opus_loop` feeds decoded codebook pieces; speaker change is text-token attribution or `user:` / `moshi:` prefixes. RAGManager trigger remains PP-T6.

## Primary

- `code-improvements/personaplex-migrate/moshi/moshi/inference_utils/turn_manager.py`
- `code-improvements/personaplex-migrate/moshi/moshi/inference_utils/__init__.py`
- `code-improvements/personaplex-migrate/moshi/moshi/server.py`

## Secondary

- `tests/test_personaplex_migrate.py`

## Tests

- `py -3.11 -m pytest tests/test_personaplex_migrate.py -q`

## Spec

PP8 / FR-007. Empty context skips the LLM (PP3). Do not port `stt/` or Channel. R38 STT stays tools. R43 A/B wiring is PP-T6.

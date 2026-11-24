# Impact packet — PersonaPlex PP-T16 prefill abort (PP17)

**Date:** 2026-11-23  
**Hook:** `change.impact`, `change.validation`  
**Spec:** `docs/specs/PersonaPlex_migrate` Story 6 / FR-013 / SC-PP10

## Change

Hive handshake wait polls `abort` and closes the in-flight websocket so working-copy NVIDIA `is_alive` (`ws.closed`) stops `step_system_prompts_async` and releases slot 1. Live SC-PP10 remains fail-closed without operator 7B flags.

## Primary

- `src/hive_planner/voice_personaplex_prefill_abort.py`
- `src/hive_planner/voice_moshi.py` (`_connect_handshake` / probes)
- `code-improvements/personaplex-migrate/moshi/moshi/hive_is_alive.py`
- `code-improvements/personaplex-migrate/moshi/moshi/server.py`

## Secondary

- `tests/test_personaplex_pp_t16.py`
- `docs/specs/PersonaPlex_migrate/pp-t16-sc-pp10.json`

## Tests

- `tests/test_personaplex_pp_t16.py`

## Spec

No new product behavior beyond PP17 / FR-013. Default `speech_child` unchanged.

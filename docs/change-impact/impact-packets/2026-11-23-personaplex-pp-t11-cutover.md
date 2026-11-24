# Impact packet — PP-T11 cutover gate

**Date:** 2026-11-23  
**Hook:** `change.impact`, `change.validation`  
**Spec:** `docs/specs/PersonaPlex_migrate` PP13 / SC-PP8 / PP-T11

## Change

Default `speech_child` is computed from PP13 gates. Current record is fail-closed (`moshi_q8`). Encoder stays. moshika-rag speech weights are not required. SC-PP9/10 do not block.

## Primary

- `src/hive_planner/voice_personaplex_cutover.py`
- `src/hive_planner/voice_bot.py`

## Secondary

- `tests/test_personaplex_pp_t11.py`
- `docs/specs/PersonaPlex_migrate/pp-t11-cutover-gates.json`

## Tests

- `tests/test_personaplex_pp_t11.py`
- `tests/test_voice_bot_config.py`

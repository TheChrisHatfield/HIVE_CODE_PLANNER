# Impact packet — PP-T8 Hive step-in

**Date:** 2026-11-23  
**Hook:** `change.impact`, `change.validation`  
**Spec:** `docs/specs/PersonaPlex_migrate` PP10 / PP20 / PP23 / PP-T8

## Change

Voice_Bot listen gate branches on `speech_child`. Default remains `moshi_q8`. PersonaPlex uses NVIDIA argv, query URL, PYTHONPATH overlay, and `scripts/personaplex_server.py`. q8 launcher is unchanged.

## Primary

- `src/hive_planner/voice_bot.py`
- `src/hive_planner/voice_moshi.py`
- `src/hive_planner/voice_moshi_server.py`
- `src/hive_planner/launcher/voice_panel_controller.py`
- `scripts/personaplex_server.py`

## Secondary

- `tests/test_personaplex_pp_t8.py`
- `tests/test_voice_bot_config.py`
- `tests/test_voice_moshi.py`
- `tests/test_voice_moshi_server.py`

## Tests

- `tests/test_personaplex_pp_t8.py`
- `tests/test_voice_moshi_server.py::test_gate_with_q8_keys_starts_the_q8_launcher_not_the_bare_command`
- `tests/test_voice_moshi_server.py::test_pp_t8_gate_with_leftover_q8_keys_starts_personaplex`

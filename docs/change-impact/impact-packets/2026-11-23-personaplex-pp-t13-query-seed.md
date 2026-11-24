# Impact packet — PP-T13 query seed / skip HF

**Date:** 2026-11-23  
**Hook:** `change.impact`, `change.validation`  
**Spec:** `docs/specs/PersonaPlex_migrate` G27 / G143 / G181 / PP-T13

## Change

Working-copy `seed` reads `request.query`. Local argv (`--moshi-weight` + `--mimi-weight` + `--tokenizer`, `--static none`) skips HF `config.json` / `voices.tgz` / `dist.tgz`. Empty `voice_prompt` skips load and does not KeyError. Hive handshake still always sends both query keys. No Vite idle-timeout patch.

## Primary

- `code-improvements/personaplex-migrate/moshi/moshi/server.py`

## Secondary

- `tests/test_personaplex_pp_t13.py`
- `src/hive_planner/voice_moshi_server.py` (`personaplex_handshake_url`)

## Tests

- `tests/test_personaplex_pp_t13.py`

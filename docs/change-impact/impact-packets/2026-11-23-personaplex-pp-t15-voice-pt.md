# Impact packet — PP-T15 local .pt / wav persona

**Date:** 2026-11-23  
**Hook:** `change.impact`, `change.validation`  
**Spec:** `docs/specs/PersonaPlex_migrate` PP16 / G182 / PP-T15

## Change

Working-copy connect loads `.pt` embeddings or wav. Voice change is a new handshake basename, not a mid-call opcode. Offline export helper writes `.pt` from a local wav with no HF download. Hive still refuses a missing configured voice file before spawn.

## Primary

- `code-improvements/personaplex-migrate/moshi/moshi/export_voice_pt.py`
- `code-improvements/personaplex-migrate/moshi/moshi/server.py`

## Secondary

- `tests/test_personaplex_pp_t15.py`

## Tests

- `tests/test_personaplex_pp_t15.py`

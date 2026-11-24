# Impact packet — PP-T9 opus_loop skip + SC-PP11 fail-closed

**Date:** 2026-11-23  
**Hook:** `change.impact`, `change.validation`  
**Spec:** `docs/specs/PersonaPlex_migrate` PP21 / SC-PP11 / PP-T9

## Change

Live `opus_loop` no longer runs discarded `other_mimi` encode/decode. Catch-up yields. Live 12.5 Hz / PP-E1 remain fail-closed until a measured row exists.

## Primary

- `code-improvements/personaplex-migrate/moshi/moshi/server.py`
- `scripts/personaplex_sc_pp11_judge.py`

## Secondary

- `tests/test_personaplex_pp_t9.py`
- `docs/specs/PersonaPlex_migrate/pp-t9-sc-pp11-record.md`

## Tests

- `tests/test_personaplex_pp_t9.py`

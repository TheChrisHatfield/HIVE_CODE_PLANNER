# Impact packet — PersonaPlex PP-T4 LLM + retrieve wrap

**Date:** 2026-11-23  
**Hook:** `change.impact`, `change.validation`  
**Spec:** `docs/specs/PersonaPlex_migrate/spec.md` PP3 / PP-T4

## Change

Working-copy `llm/` + `reference/` (templates, `LLMClient`, `LLMReferenceGenerator`, `clean_reference_text`) is the retrieve-then-LLM hop. Empty `user:` context skips the LLM. Hive `voice_moshi_retrieval.install_from_env` wraps the working-copy class so `collect_lines` prepends `BLOCK_LABEL` into `process_reference_text`. No `scripts/personaplex_server.py` (PP-T8). RAGManager trigger stays PP-T6.

## Primary

- `code-improvements/personaplex-migrate/moshi/moshi/reference/llm_reference_generator.py`
- `code-improvements/personaplex-migrate/moshi/moshi/reference/__init__.py`
- `code-improvements/personaplex-migrate/moshi/moshi/llm/` (already ported; templates + client)

## Secondary

- `tests/test_personaplex_migrate.py`
- `src/hive_planner/voice_moshi_retrieval.py` (unchanged wrap; proven on working-copy class)

## Tests

- `py -3.11 -m pytest tests/test_personaplex_migrate.py -q`

## Spec

PP3 / FR-002 / I9. Caps 96 and temperature 0 remain Hive launcher wraps (PP-T8).

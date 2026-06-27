# Tasks: cartridge-translator-v1

**Hook:** `spec.flow`

## Task 1 — Delta + spec ✅

- [x] Micro brief, spec, plan, tasks
- [x] Review and approve before implementation

## Task 2 — translator.py core ✅

- [x] `segment_text`, `classify_segment`, `compress_segment`
- [x] Keyword rule tables from schema

## Task 3 — Draft emit + CLI ✅

- [x] `emit_draft_cartridge` with draft banners
- [x] `hive_planner translate --input --feature`
- [x] Status JSON output

## Task 4 — Tests + bug gate ✅

- [x] `tests/test_translator.py`
- [x] S4B-B1: reject noise segments
- [x] S4B-B2: no writes outside cartridge/
- [x] S4B-B3: full pytest regression

## Active task

**None** — Stage 4B complete. Next: `agents-memory-ci-v1` (Stage 4C).

## Bug gate (Stage 4B)

| Check | Test |
|-------|------|
| S4B-B1 reject noise | `test_classify_reject_noise_segment`, `test_reject_segments_excluded_from_output` |
| S4B-B2 cartridge only | `test_translate_writes_only_under_cartridge` |
| S4B-B3 regression | full pytest |

## Validation log

```text
2026-06-21 — Stage 4B bug gate
  py -3.11 -m pytest -v → 47 passed (B1–B8 + S2 + S3 + S4A + S4B)
  S4B-B1 reject noise → test_classify_reject_noise_segment, test_reject_segments_excluded_from_output
  S4B-B2 cartridge only → test_translate_writes_only_under_cartridge
  S4B-B3 regression → 47 passed
  translate --input docs/delta/20_micro/cartridge-compiler-v3.md --feature cartridge-translator-v1
2026-06-21 — post-v1.0.0 bug audit (Stage 4B)
- test_translator.py: 13/13 PASS; S4B-B1..B3 verified
- Smoke: translate cartridge-compiler-v3 OK
```

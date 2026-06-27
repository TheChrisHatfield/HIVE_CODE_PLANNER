# Tasks: change-impact-v1

## Task 1 — Docs scaffold ✅

- [x] Delta micro brief, spec, plan, tasks
- [x] `docs/change-impact/*`, `change-impact.mdc`
- [x] Update START_HERE read order

## Task 2 — impact.py + CLI ✅

- [x] Packet builder + test-map parser
- [x] `impact` command
- [x] Invalid packet warnings on ingest/emit (non-blocking)

## Task 3 — Bug gate ✅

- [x] `tests/test_impact.py` (S3-B1..S3-B5)
- [x] Full pytest 28 passed + ingest/emit regression

## Active task

**None** — Stages 2–3 complete per Rosetta plan.

## Validation log

```text
2026-06-21 — Stage 3 bug gate
  py -3.11 -m pytest -v → 28 passed (B1–B8 + S2 + S3)
  S3-B1 unknown feature → test_unknown_feature_errors_without_packet
  S3-B2 src target tests → test_impact_lists_tests_for_src_target
  S3-B3 delta tertiary → test_delta_edit_flagged_tertiary
  S3-B4 invalid packet warn → test_invalid_packet_load_warns_not_blocks
  S3-B5 packet write/load → test_impact_cli_writes_packet
  Example: impact --feature cartridge-compiler-v2 --files src/hive_planner/emitter.py
2026-06-21 — post-v1.0.0 bug audit (Stage 3)
- test_impact.py: 15/15 PASS; S3-B1..B5 verified
- Smoke: impact --feature change-impact-v1 OK
```

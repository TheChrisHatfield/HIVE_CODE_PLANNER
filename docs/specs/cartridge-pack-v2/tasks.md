# Tasks: cartridge-pack-v2

## Task 1 — Delta + spec ✅

## Task 2 — emit_rules_seed module ✅

## Task 3 — CLI + manifest integration ✅

## Task 4 — Tests ✅

## Active task

**None** — Phase 3 complete pending validation log.

## Validation log

```text
2026-06-26 — Phase 3 gate
- emit --emit-rules-seeds writes cartridge/rules/<feature>.mdc.seed
- .cursor/rules/ untouched; MANUAL seeds skipped
- manifest targets.cursor_rules = "seed" when flag set
- test_cartridge_pack.py: 13/13 PASS
- Full pytest: 129/129 PASS
- ci-check: 5/5 PASS
```

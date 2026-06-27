# Plan: cartridge-delta-emit-v1

**Hook:** `context.cartridge`  
**Spec:** [spec.md](./spec.md)

## Approach

Add `delta_emit.py` with skip/force logic. Call from `emit_cartridge` after manifest assembly, before final manifest write.

## Module map

```text
src/hive_planner/
  delta_emit.py   # sync_delta_file, sync_delta_cartridge
  emitter.py      # integrate delta sync + manifest stats
  cli.py          # --force-delta
tests/
  test_delta_emit.py
```

## Risks

| Risk | Mitigation |
|------|------------|
| Overwrite translator drafts | Skip DRAFT banner; warn in emit |
| Stale cartridge after Delta edit | AUTO-SYNC files update on re-emit |
| Missing Delta files | Warn; continue emit |

## Validation

- Unit tests for skip/force/auto-update
- Full pytest regression
- Smoke emit on repo feature

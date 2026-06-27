# Feature Micro Brief: cartridge-pack-v2

**Hook:** `context.cartridge`, `cursor.rules`, `compiler.pipeline`

## Feature Name

Cartridge Pack v2 — optional Cursor rule seed emit.

## Holistic Link

Closes partial cartridge → Cursor rules gap from HIVE_PLANNING_V1 without auto-compiling live rules.

## Macro Link

Extends **Cartridge emitter** per [cartridge-schema-v1.md](../../cartridge-schema-v1.md) compilation targets.

## Scope

| In scope | Out of scope |
|----------|--------------|
| `--emit-rules-seeds` flag | Auto-write `.cursor/rules/` |
| `cartridge/rules/<feature>.mdc.seed` | LLM rule generation |
| Manifest `cursor_rules: seed` | Cursor auto-attach hooks |
| Source-map `cursor_rule_seed` layer | Overwriting reviewed rules |

**Files:** `src/hive_planner/cartridge_pack.py`, `emitter.py`, `cli.py`, `tests/test_cartridge_pack.py`

## Acceptance Criteria

- [x] Flag writes draft rule seed from macro/micro
- [x] `.cursor/rules/` never modified by emit
- [x] Manifest reflects seed target when flag set
- [x] Tests cover write, skip, and manifest

## Validation

```powershell
py -3.11 -m hive_planner emit --feature cartridge-pack-v2 --emit-rules-seeds --force-delta
py -3.11 -m pytest tests/test_cartridge_pack.py -v
```

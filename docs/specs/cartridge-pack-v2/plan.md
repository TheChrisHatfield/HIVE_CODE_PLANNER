# Plan: cartridge-pack-v2

**Hook:** `context.cartridge`, `cursor.rules`  
**Spec:** [spec.md](./spec.md)

## Approach

Extend `cartridge_pack.py` with `emit_rules_seed()`; wire `--emit-rules-seeds` through `emit_cartridge` and CLI.

## Promotion workflow

1. `py -3.11 -m hive_planner emit --feature <feature> --emit-rules-seeds`
2. Review `cartridge/rules/<feature>.mdc.seed`
3. Copy to `.cursor/rules/<feature>.mdc`, edit frontmatter, remove draft banner
4. Commit rule separately from cartridge seed

## Validation

- Unit tests with temp repo fixtures
- Confirm `.cursor/rules/` untouched after emit

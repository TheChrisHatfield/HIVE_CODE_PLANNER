# Plan: cartridge-pack-v1

**Hook:** `context.cartridge`  
**Spec:** [spec.md](./spec.md)

## Approach

Add `cartridge_pack.py`; call from `emit_cartridge` after delta sync; defer manifest write until end.

## Validation

- Unit tests with temp repo fixtures
- Smoke emit on active feature

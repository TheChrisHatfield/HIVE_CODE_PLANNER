# Plan: cartridge-translator-v1

**Hook:** `context.cartridge_schema`  
**Spec:** [spec.md](./spec.md)

## Approach

New module `src/hive_planner/translator.py` with pure functions: `segment_text`, `classify_segment`, `compress_segment`, `emit_draft_cartridge`. CLI subcommand `translate` in `cli.py`.

## Module map

```text
src/hive_planner/
  translator.py     # segment, classify, compress, emit
  cli.py              # translate subcommand
tests/
  test_translator.py
```

## Classification v1 rules (sketch)

| Bucket | Trigger keywords (case-insensitive) |
|--------|-------------------------------------|
| Holistic | mission, goal, non-goal, invariant, success criteria, constraint |
| Macro | subsystem, architecture, workflow, module, interface, data contract |
| Micro | feature, task, acceptance, file scope, edge case, test |
| Memory | durable, always, never, guardrail, AGENTS.md, rule |
| Reject | default |

## Risks

| Risk | Mitigation |
|------|------------|
| Over-classification noise | Conservative keywords; Reject default |
| Draft mistaken for truth | Banner + no writes outside cartridge/ |
| Duplicate content | Dedupe on compress step |

## Validation

- Unit tests for each bucket with fixture paragraphs
- Integration: translate sample micro brief → cartridge drafts exist
- Regression: ingest/emit/impact unchanged

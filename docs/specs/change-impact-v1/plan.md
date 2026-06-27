# Plan: change-impact-v1

**Spec:** [spec.md](./spec.md)

## Modules

- `src/hive_planner/impact.py` — packet builder, test-map lookup, packet load
- `cli.py` — `impact` subcommand
- Manual maps in `docs/change-impact/`

## Packet flow

```text
active feature spec → classify --files → lookup test-map → write impact-packets/chg_*.json
```

## Risk scoring (v1 simple)

- 1 file, tests mapped → low
- multiple src files → medium
- delta/spec edits included → medium-high

# Change Impact Policy

**Hook:** `change.impact`, `change.validation`

## Purpose

Require agents to identify primary, secondary, and tertiary effects before editing code or docs.

## Levels

| Level | Meaning | Example |
|-------|---------|---------|
| Primary | Direct edit target | `src/hive_planner/emitter.py` |
| Secondary | Connected tests, imports, configs | `tests/test_formats.py` |
| Tertiary | Docs, specs, architecture, memory | `docs/delta/10_macro.md` |

## Rules

1. Generate or read an impact packet before non-trivial edits.
2. Run validations listed in the packet before marking a task complete.
3. Impact packets are **secondary context** — they do not override active spec/tasks.

## Rosetta hooks

- `change.impact` — this policy
- `change.levels` — primary/secondary/tertiary model
- `change.validation` — validation requirements
- `next.files` — packet schema and maps

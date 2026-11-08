# Impact packet: implementation-loop blocker recovery

## Scope

Diagnose common checker failures deterministically and hand repairable failures
to the coder with bounded retry metadata. No checker failure bypasses a gate.

## Primary effects

- `src/hive_planner/implementation_loop.py`: blocker classification, runtime
  record, coder handoff context, four-cycle cap, and nine-second pause metadata.
- `tests/test_implementation_loop_coordinator.py`: repairable and
  fail-closed blocker coverage.

## Secondary effects

- `docs/specs/implementation-loop/spec.md`, `plan.md`, and `tasks.md` document
  the repair handoff contract.
- `.hive/implementation-loop/blocker.json` is runtime-only and is cleared
  after a successful checker pass.

## Risks and validation

Unrecognized, high-risk, or exhausted failures remain human-escalated.
Validate with coordinator tests, spec drift, linter, and wiring audit.

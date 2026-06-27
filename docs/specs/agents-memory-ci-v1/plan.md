# Plan: agents-memory-ci-v1

**Hook:** `automation.ci_memory`  
**Spec:** [spec.md](./spec.md)

## Approach

New module `src/hive_planner/agents_memory.py`. Parse AGENTS.md by `##` headings. Reuse validation rules from handoff doc. Proposal writer appends to editable subsection only.

## Module map

```text
src/hive_planner/
  agents_memory.py   # parse, lint, dedupe, propose
  cli.py             # agents-lint, agents-propose
docs/proposals/      # output directory (git-tracked)
tests/
  test_agents_memory.py
```

## Editable subsection

Restrict automated proposals to a dedicated section:

```markdown
## Durable Workspace Facts
```

If missing, lint warns and propose step can scaffold it.

## Risks

| Risk | Mitigation |
|------|------------|
| Accidental AGENTS overwrite | Default proposal-only; --apply blocked in v1 |
| False duplicate detection | Normalize bullets; allow override list in config |
| CI scope creep | Local script first; Actions in v2 spec |

## Validation

- Fixture AGENTS.md with duplicates → lint fails
- Valid candidates → proposal file created, AGENTS unchanged
- Full pytest regression

# Plan: unified-handoff-v2

**Hook:** `integration.unified_handoff`  
**Spec:** [spec.md](./spec.md)

## Approach

Phase the work so Stage 7 contract stays stable while upstream coupling lands incrementally.

### Phase 1 — Spec + vendor skeleton (no runtime behavior change)

1. Add `docs/unified-handoff-upstream-forks.md` (pins, patch list, sync commands).
2. Add `vendor/README.md` + `vendor/manifest.json` with placeholder pins (document initial SHAs after first sync).
3. Add Stage 9 entries to `STAGE_ROADMAP.md`; keep `ROADMAP_FEATURES` at 20 until `roadmap-complete-v4`.

### Phase 2 — Vendor import

1. Git submodule or scripted vendor sync for `github/spec-kit` and `cursor/plugins` subtree `continual-learning/`.
2. Create `vendor/patches/` with documented diffs (or fork branches `hive/spec-kit`, `hive/continual-learning` on GitHub org — preferred for multi-user deploy).
3. Apply Hive patch set (see upstream forks doc); record patched version in manifest.

### Phase 3 — Bootstrap deploy

1. `vendor_sync.py` module: read manifest, copy plugin + spec-kit overlay to target.
2. Wire `init` / `deploy_agent_handoff_scaffold` to call vendor deploy when `agent_handoff=unified`.
3. Write `.hive/upstream-pins.json` into bootstrapped projects.

### Phase 4 — Contract alignment

1. Patch CL subagent prompt: `Durable Workspace Facts`, behavioral rejection, wiring audit gate.
2. Patch Spec Kit templates: wiring audit in `tasks.md`, Rosetta placeholder in `spec.md`.
3. Add candidate export path from CL hook → `docs/proposals/` for CI parity.

### Phase 5 — CLI, tests, docs closure

1. `hive_planner vendor-sync` / `unified-verify` commands.
2. `tests/test_unified_handoff.py` + optional `ci-check` step.
3. Update bootstrap guide + starter-kit integration doc.
4. `roadmap-complete-v4` spec when Stage 9 ships.

## Module map (planned)

| Module | Responsibility |
|--------|----------------|
| `vendor_sync.py` | Pin manifest, copy overlays, drift check |
| `bootstrap.py` | Call vendor deploy in unified handoff path |
| `agent_handoff.py` | Extend `unified_handoff_artifacts()` with vendor paths |
| `ci_handoff.py` | Optional `unified-vendor` step |

## Risk mitigations

| Risk | Mitigation |
|------|------------|
| Upstream breaking changes | Pin SHAs; vendor-sync tests fail on unexpected diff |
| Cursor plugin API drift | Isolate copy logic; document Cursor min version |
| Dual CL (marketplace + vendored) | Bootstrap warning + `.hive/project.json` flag `cl_source: vendored` |
| Section name drift | Single mapping table in CL subagent + `agents_memory.py` |

## Dependencies

- Stage 7 complete (`cl-spec-integration-v1`, wiring audit rule)
- `project-bootstrap-v1` unified handoff scaffold
- Operator access to fork repos (recommended: Hive org forks)

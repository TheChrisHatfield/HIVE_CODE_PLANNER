# Plan: cl-spec-integration-v1

**Hook:** `integration.cl_spec`  
**Spec:** [spec.md](./spec.md)

## Approach

1. Add `spec_drift.py` with classification, handoff validation, and drift detection.
2. Wire `spec-drift-check` CLI and `ci-check` spec-drift step.
3. Integrate `classify_bullet` into `agents_memory.propose_candidates`.
4. Document contract in `docs/cl-spec-integration.md` and Cursor rule.

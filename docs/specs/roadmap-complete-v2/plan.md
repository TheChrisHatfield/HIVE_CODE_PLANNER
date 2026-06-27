# Plan: roadmap-complete-v2

**Hook:** `workflow.tools`  
**Spec:** [spec.md](./spec.md)

## Approach

1. Extend `ROADMAP_FEATURES` in `roadmap_status.py` with Stage 7 feature ids.
2. Add missing spec trios (cl-spec-integration-v1, roadmap-complete-v2).
3. Update `STAGE_ROADMAP.md` and rosetta stone hooks.
4. Gate with `roadmap-status`, `ci-check`, and pytest.

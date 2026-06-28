# Stage Roadmap — Complete

**Hook:** `workflow.tools`, `workflow.blueprint_first`

Hive Code Planner compiler roadmap (Stages 1–6) is **complete** as of v1.0.0.  
**Stage 7** (CL/spec integration, memory v2, rule seeds, impact v3, bootstrap) is **complete** as of v1.1.0.  
**Stage 8** (starter-kit v2 full profile, security hardening) is **complete** as of v1.2.0.  
**Stage 9** (unified upstream forks — Spec Kit + Continual Learning vendored deploy) is **planned** — spec drafted 2026-06-26.

**Post-v1.0.0 bug audit:** 2026-06-21 — stage-by-stage audit complete; 103/103 pytest, ci-check 5/5.

**Stage 7 closure:** 2026-06-26 — 18/18 roadmap artifacts, ci-check 5/5.

**Stage 8 closure:** 2026-06-26 — 20/20 roadmap artifacts, 166 pytest, ci-check 5/5.

| Stage | Feature | Status |
|-------|---------|--------|
| 1 | cartridge-compiler-v1 | ✅ |
| 2 | cartridge-compiler-v2 | ✅ |
| 3 | change-impact-v1 | ✅ |
| 4A | cartridge-compiler-v3 | ✅ |
| 4B | cartridge-translator-v1 | ✅ |
| 4C | agents-memory-ci-v1 | ✅ |
| 4D | embedding-retrieval-v1 | ✅ |
| 5A | cartridge-delta-emit-v1 | ✅ |
| 5B | change-impact-v2 | ✅ |
| 5C | git-handoff-ci-v1 | ✅ |
| 6A | cartridge-pack-v1 | ✅ |
| 6B | roadmap-complete-v1 | ✅ |
| 7A | cl-spec-integration-v1 | ✅ |
| 7B | agents-memory-ci-v2 | ✅ |
| 7C | cartridge-pack-v2 | ✅ |
| 7D | change-impact-v3 | ✅ |
| 7E | project-bootstrap-v1 | ✅ |
| 7F | roadmap-complete-v2 | ✅ |
| 8A | starter-kit-v2 | ✅ |
| 8B | roadmap-complete-v3 | ✅ |
| 9A | unified-handoff-v2 | 📋 planned |
| 9B | roadmap-complete-v4 | 📋 planned |

### Stage 9 — Unified upstream forks

Vendored, pinned forks of [github/spec-kit](https://github.com/github/spec-kit) and [cursor/plugins/continual-learning](https://github.com/cursor/plugins/tree/main/continual-learning) with Hive symbiotic patches. Bootstrap deploys both; IDE CL plugin and Hive CLI share one contract.

- **Spec:** [specs/unified-handoff-v2/spec.md](../specs/unified-handoff-v2/spec.md)
- **Operator guide:** [unified-handoff-upstream-forks.md](../unified-handoff-upstream-forks.md)
- **Active task:** Task 2 — vendor manifest skeleton (`docs/specs/unified-handoff-v2/tasks.md`)

`ROADMAP_FEATURES` remains at 20 features until Stage 9 implementation closes via `roadmap-complete-v4`.

Validate anytime:

```powershell
py -3.11 -m hive_planner roadmap-status
py -3.11 -m hive_planner ci-check
```

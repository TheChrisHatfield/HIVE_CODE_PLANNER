# Plan: bug-hunt

**Hook:** `change.bugfix_mode`, `integration.wiring_audit`  
**Spec:** [spec.md](./spec.md)

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before editing this plan.

- **Spec:** [`spec.md`](./spec.md)
- **Delta micro:** [`bug-hunt.md`](../../delta/20_micro/bug-hunt.md)
- **Hooks:** `change.bugfix_mode`, `integration.wiring_audit`, `spec.flow`

## Approach

Keep the script text and chat-trigger matcher in `bug_hunt.py`. The CLI, project bootstrap, handoff deploy, and Controls **Bug hunt → Enable** all call `install_bug_hunt` so the Cursor command + always-on rule land in the project. The rule matches derivative "perform a bug hunt" phrasing; `is_bug_hunt_request` is the testable contract.

R9 attention lives in the same module as the six-weight rebuild. `advance_rank_pass` rebuilds six-signal mean, detector trust, and per-folder place means from `rank-rows.jsonl` (including `findings`). It draws once per six slope, once for trust, and once per candidate folder, scores the R9 mix, then adds the bounded R10 uncertainty/coverage bonus after `rank_queue_score`. Draws are discarded as learning inputs; an audit copy may remain in pass state and the selected row. Append `findings`, the final `score`, and valid attribution on each rank row, copied from `rank-pass.json` **before** the queue rewrite. Surprise reads those stored scores. Rebuilds use stored row `findings`; this pass's finding bit uses this pass's detector scan. Score all qualifying unopened files, then persist the top 50. Trust seed 1.0; place seed 0.0; same twenty imaginary votes and 0.9 decay as R5. Surprise scale `1+m` on the last ten voted rows vs stored queue scores. Do not add epsilon, every-Nth, or a fixed findings bonus. Ranking robustness (NaN on read, integer digit strings, junk opened entries, case-insensitive cache skip, Signals as a type, MemoryError, finally temp cleanup, jsonl findings/score) is a separate task and does not change the sampled mix. Tests in `tests/test_bug_hunt.py` cover trust falling after empty-on-finding rows, folder mass moving after empty rows, and equal six-draws where a finding file does not always win. Prompt text from `render_agent_prompt` describes the extra draws and R10 attribution the same way it describes the six-draw. Logic rotation and `FINDINGS_PRESENT_BONUS` go away when this lands.

R10 implementation follows R9 in the same module and hook path. Add the evidence-based exploration bonus, the versioned attribution schema, the bounded `.hive/bug-hunt/calibration.jsonl` audit record, and validated `requested_file` / `requested_line` direct overrides. Legacy rows remain readable and do not vote through attribution. Add fixture tests before enabling the new score in installed prompt copies.

R11 adds a bounded recovery controller after the existing empty threshold. Keep the current posterior learner and stop-hook ownership, but persist recovery state, rotate through unused review lenses, exclude recently empty locations/folders while alternatives remain, and scale empty-row negative learning by `empty_confidence`. Recovery has a three-pass cap and exits on a real outcome, the fix ceiling, an exhausted qualifying queue, or an atomic recovery-state write failure; it must not become a second neural model or an unbounded loop. The normal two-empty rule is therefore a recovery trigger when alternatives exist, not an unconditional stop.

Until the R11 implementation tasks are complete, the installed command, generated prompt, and stop hook intentionally retain the pre-R11 two-empty stop behavior. They must be updated together in one implementation task; updating prompt text alone would create a false-success wiring gap.

## File targets

| File | Change |
|------|--------|
| `src/hive_planner/bug_hunt.py` | R10 scoring, attribution, calibration, and confidence-weighted empty learning |
| `src/hive_planner/bug_hunt_continue.py` | direct override, recovery state, hook metadata, atomic state validation, and recovery stop/error reporting |
| `.cursor/commands/bug-hunt.md`, `scripts/bug-hunt.md`, and `.hive/bug-hunt/AGENT_PROMPT.md` | generated R11 recovery instructions, updated only with the runtime implementation |
| `tests/test_bug_hunt.py` | R10 and R11 unit/integration coverage |
| `docs/specs/bug-hunt/spec.md` | R10/R11 contract updates |
| `docs/specs/bug-hunt/tasks.md` | R10/R11 task state |

## Validation

R10 and R11 remain documentation-only until their implementation tasks are completed. When implementation
begins, validate score, attribution, calibration, direct-override, recovery-state, lens-rotation,
confidence-weighted updates, malformed-state handling, reset semantics, and stop-hook wiring together;
do not treat fixture-only arithmetic as sufficient integration evidence.

```powershell
py -3.11 -m pytest tests/test_bug_hunt.py -v
py -3.11 -m hive_planner spec-drift-check --feature bug-hunt
```

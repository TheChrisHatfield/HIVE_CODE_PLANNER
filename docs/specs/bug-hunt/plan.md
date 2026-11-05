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

R9 attention lives in the same module as the six-weight rebuild. `advance_rank_pass` rebuilds six-signal mean, detector trust, and per-folder place means from `rank-rows.jsonl` (including `findings`). It draws once per six slope, once for trust, and once per candidate folder, scores `six_draw·x + trust_draw·1_finding + place_draw[folder]`, and stores none of the draws. Append `findings` and that pass's mix `score` on each rank row, copied from `rank-pass.json` **before** the queue rewrite. Surprise reads those stored scores. Rebuilds use stored row `findings`; this pass's finding bit uses this pass's detector scan. Score all qualifying unopened files, then persist the top 50. Trust seed 1.0; place seed 0.0; same twenty imaginary votes and 0.9 decay as R5. Surprise scale `1+m` on the last ten voted rows vs stored queue scores. Do not add epsilon, every-Nth, or a fixed findings bonus. Ranking robustness (NaN on read, integer digit strings, junk opened entries, case-insensitive cache skip, Signals as a type, MemoryError, finally temp cleanup, jsonl findings/score) is a separate task and does not change the sampled mix. Tests in `tests/test_bug_hunt.py` cover trust falling after empty-on-finding rows, folder mass moving after empty rows, and equal six-draws where a finding file does not always win. Prompt text from `render_agent_prompt` describes the extra draws the same way it describes the six-draw. Logic rotation and `FINDINGS_PRESENT_BONUS` go away when this lands.

## Validation

```powershell
py -3.11 -m pytest tests/test_bug_hunt.py -v
py -3.11 -m hive_planner spec-drift-check --feature bug-hunt
```

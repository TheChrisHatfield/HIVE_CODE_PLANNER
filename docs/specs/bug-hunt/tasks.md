# Tasks: bug-hunt

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Load [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) (`planning.rosetta`) before executing tasks.

- **Spec:** [`spec.md`](./spec.md)
- **Plan:** [`plan.md`](./plan.md)
- **Delta micro:** [`bug-hunt.md`](../../delta/20_micro/bug-hunt.md)

- [x] Spec and micro brief
- [x] `bug_hunt.py` script render and install
- [x] CLI `bug-hunt`
- [x] `tests/test_bug_hunt.py`
- [x] R4 chat-trigger matcher for derivative hunt phrases
- [x] R3 bootstrap + handoff deploy install
- [x] R3 Home **Loop controls** → Bug hunt Enable → `run_project_bug_hunt_install`
- [x] Ranking robustness: NaN-on-read, integer digit strings (`2.0`), skip junk opened entries, case-insensitive cache skip, Signals as a type not a factory, MemoryError on ranking paths, finally-block temp cleanup, persist findings and score on jsonl
- [ ] R5 and R6 rolling ranker: rebuild the six score weights from `.hive/bug-hunt/rank-rows.jsonl`, decay them by row order, and draw one Thompson sample per pass. Replace the fixed slopes in `bug_hunt.py` and the logistic-regression-after-30-rows instruction in the hunt script
- [ ] R9 attention (US4): spec written; implement sibling posteriors in `src/hive_planner/bug_hunt.py` — detector trust and place attention, discarded draws mixed into `rank_queue_score` / `score_unopened` / `advance_rank_pass`. No epsilon, no every-Nth, no `FINDINGS_PRESENT_BONUS`, no three-commit rotation. Persist `findings` and mix `score` on each jsonl row. Hook copies those from `rank-pass.json`; do not require them on `continue.json`.
- [ ] R9 tests: `tests/test_bug_hunt.py` — empty-on-finding lowers trust vs seed; empty-in-folder lowers that folder vs seed; equal six-score does not force findings-first; residual mismatch widens the next draw; skipped rows do not vote on attention; missing `score`/`findings` keys; root-folder `.`; single-folder queue; append copies queue fields before rewrite; list-shaped findings count as 0; all-missing scores leave `m` at 0.
- [ ] R9 prompt: `render_agent_prompt` and installed hunt script describe rebuild / sample / discard for trust and place attention. Drop the 30-row logistic instruction when R9/R6 land.

## Active task

**R9 attention** — sampled detector trust and place attention are live in `bug_hunt.py`. Findings bonus and three-commit rotation are gone. Jsonl persists `findings`/`score`. Folder identity is the first slash part. Queue persists the top 50.

## Validation log

```text
2026-10-20
- tests/test_bug_hunt.py + bootstrap init + launcher bug_hunt/agent templates: 34 passed
- hive_planner spec-drift-check --feature bug-hunt: ok
- Installed command, always-on rule, packet, and scripts/bug-hunt.md into this repo
```

## After each implementation task — Integration wiring audit (required)

- [x] Traced caller → handler → core (no layer break)
- [x] No false success when a sub-step failed or was skipped
- [x] Integration-level validation evidence attached
- [x] See `.cursor/rules/integration-wiring-audit.mdc`

Before Continual Learning promotion, run `py -3.11 -m hive_planner spec-drift-check` (see `.hive/spec-kit/WORKFLOW.md`).

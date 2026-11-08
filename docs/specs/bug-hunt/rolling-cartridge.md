<!--
meta:title: Bug-hunt adaptive weights rolling cartridge
meta:hook_id: planning.rosetta
meta:search: Planning Rosetta Stone bug-hunt dials
meta:purpose: Append-only transcript and Rosetta legend for the adaptive per-repo weight session
meta:audience: Agentic coding agents, human maintainers
meta:usage: Load before updating docs/specs/bug-hunt; append new segments at the end
meta:format: semantic-markdown-with-hook-tags
meta:status: draft
meta:scope: bug-hunt
meta:priority: high
meta:anchor_version: v1
-->
# Planning Rosetta Stone — Bug-hunt adaptive weights

Search phrase: **Planning Rosetta Stone** · Root hook: `planning.rosetta`

This file is the rolling cartridge for the 2026-11-02 session on Hive Planner bug-hunt weights. The Rosetta section is the legend. The transcript section is the thread. Later turns append at the end. Earlier segments stay as written.

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Before implementing, load the hook map — do not jump straight into requirements.

1. [docs/planning-rosetta-stone.md](../../planning-rosetta-stone.md) — hook `planning.rosetta`
2. This cartridge — hook `planning.rosetta` for the session legend below
3. Feature spec — hook `spec.flow`: [spec.md](./spec.md), [plan.md](./plan.md), [tasks.md](./tasks.md)

## Purpose

Legend for the decisions in this session: how bug hunt ranks files today, and the adaptive per-repo weight design that should replace the fixed hand weights. Coding agents load this legend first, then the linked spec. Execution truth stays in [spec.md](./spec.md) (hook: `spec.flow`).

## How to use

1. Find the concept or hook below.
2. Open PRIMARY FILES.
3. Follow UNLOCKS only when deeper detail is needed.
4. Mine a decision in the transcript by its `[CTX:…]` heading.
5. To extend this cartridge, append a new transcript segment and any new `## [HOOK:…]` block at the end of the file. Do not rewrite earlier segments.

## Legend conventions

- **HOOK_ID** — stable anchor (`domain.name`)
- **PRIMARY FILES** — first files to open
- **UNLOCKS** — related hooks next
- **THREAD COVERAGE** — what this hook summarizes
- **CTX** — one context member per decision inside the transcript

***

## [HOOK:planning.rosetta]

**HOOK_ID:** `planning.rosetta`

**Meaning:** Legend for this session's bug-hunt weight thread.

**PRIMARY FILES:**

- [rolling-cartridge.md](./rolling-cartridge.md)
- [planning-rosetta-stone.md](../../planning-rosetta-stone.md)
- [ROSETTA-PLANNING-SESSION-CONTRACT.md](../../ROSETTA-PLANNING-SESSION-CONTRACT.md)

**UNLOCKS:**

- `bug_hunt.rule_first`
- `bug_hunt.shared_weights`
- `bug_hunt.anchor_votes`
- `bug_hunt.per_repo_dials`
- `bug_hunt.hand_weight_evidence`
- `spec.flow`

**THREAD COVERAGE:** Navigation for the 2026-11-02 bug-hunt weight session.

***

## [HOOK:bug_hunt.rule_first]

**HOOK_ID:** `bug_hunt.rule_first`

**Meaning:** Chat trigger only. Typing "bug hunt" hits the always-on rule, which then opens the command script. This marker does not cover install, pause, or phrase exclusions.

**PRIMARY FILES:**

- [bug-hunt.mdc](../../../.cursor/rules/bug-hunt.mdc)
- [bug-hunt.md](../../../.cursor/commands/bug-hunt.md)
- [bug_hunt.py](../../../src/hive_planner/bug_hunt.py)

**UNLOCKS:**

- `bug_hunt.markdown_split`
- `change.bugfix_mode`

**THREAD COVERAGE:** Chat start only. Install layout and the stop hook are outside this marker.

***

## [HOOK:bug_hunt.markdown_split]

**HOOK_ID:** `bug_hunt.markdown_split`

**Meaning:** The hunt procedure is Markdown the agent reads. Python installs it, loops it, and commits.

**PRIMARY FILES:**

- [bug_hunt.py](../../../src/hive_planner/bug_hunt.py)
- [bug_hunt_continue.py](../../../src/hive_planner/bug_hunt_continue.py)

**UNLOCKS:**

- `bug_hunt.rule_first`
- `bug_hunt.predictor_is_prompt`

**THREAD COVERAGE:** Which files are Python, which are Markdown, and that the split does not change speed.

***

## [HOOK:bug_hunt.rank_row_append]

**HOOK_ID:** `bug_hunt.rank_row_append`

**Meaning:** A rank row is appended at step 6, after the outcome is chosen.

**PRIMARY FILES:**

- [bug-hunt.md](../../../.cursor/commands/bug-hunt.md)
- [rank-rows.jsonl](../../../.hive/bug-hunt/rank-rows.jsonl)

**UNLOCKS:**

- `bug_hunt.rank_rows_grow`
- `bug_hunt.outcome_votes`

**THREAD COVERAGE:** Open, inspect, classify, maybe edit, choose an outcome, then append.

***

## [HOOK:bug_hunt.rank_rows_grow]

**HOOK_ID:** `bug_hunt.rank_rows_grow`

**Meaning:** Nothing in the engine truncates, rotates, or deletes rank-rows.jsonl.

**PRIMARY FILES:**

- [bug_hunt.py](../../../src/hive_planner/bug_hunt.py)
- [rank-rows.jsonl](../../../.hive/bug-hunt/rank-rows.jsonl)

**UNLOCKS:**

- `bug_hunt.outcome_decay`
- `bug_hunt.no_hard_stop`

**THREAD COVERAGE:** The file grows by one line per opened location across hunts.

***

## [HOOK:bug_hunt.predictor_is_prompt]

**HOOK_ID:** `bug_hunt.predictor_is_prompt`

**Meaning:** The current ranker and classifier are sentences in the agent script. Python does not fit or store a model.

**PRIMARY FILES:**

- [bug_hunt.py](../../../src/hive_planner/bug_hunt.py)
- [spec.md](./spec.md)

**UNLOCKS:**

- `bug_hunt.shared_weights`
- `bug_hunt.hand_weight_evidence`

**THREAD COVERAGE:** Weighted sum until 30 rows, then a logistic regression the agent is told to fit. The active score is `score_signals` on the fitted slopes.

***

## [HOOK:bug_hunt.shared_weights]

**HOOK_ID:** `bug_hunt.shared_weights`

**Meaning:** One shared six-signal weight vector. Other files' results move files that have not been opened yet.

**PRIMARY FILES:**

- [spec.md](./spec.md)
- [rolling-cartridge.md](./rolling-cartridge.md)

**UNLOCKS:**

- `bug_hunt.anchor_votes`
- `bug_hunt.per_repo_dials`

**THREAD COVERAGE:** Rejection of an independent Beta per file, because a file is usually opened once per hunt.

***

## [HOOK:bug_hunt.anchor_votes]

**HOOK_ID:** `bug_hunt.anchor_votes`

**Meaning:** Twenty imaginary votes sit on the slopes 0.7118, 3.3024, 1.0245, -0.1424, 0, 0. The first multiplies log1p of the fix-commit count.

**PRIMARY FILES:**

- [spec.md](./spec.md)
- [bug_hunt.py](../../../src/hive_planner/bug_hunt.py)

**UNLOCKS:**

- `bug_hunt.outcome_decay`
- `bug_hunt.outcome_votes`

**THREAD COVERAGE:** Prior mean. One new row moves a slope by about a third of its credit. The seed stays an offset.

***

## [HOOK:bug_hunt.outcome_decay]

**HOOK_ID:** `bug_hunt.outcome_decay`

**Meaning:** Older rows lose influence by file order, factor 0.9 per step. There is no timestamp.

**PRIMARY FILES:**

- [rank-rows.jsonl](../../../.hive/bug-hunt/rank-rows.jsonl)
- [rolling-cartridge.md](./rolling-cartridge.md)

**UNLOCKS:**

- `bug_hunt.anchor_votes`
- `bug_hunt.no_hard_stop`

**THREAD COVERAGE:** Geometric decay and the rebuilt prior formula.

***

## [HOOK:bug_hunt.same_hunt_update]

**HOOK_ID:** `bug_hunt.same_hunt_update`

**Meaning:** The next pass in the same hunt rebuilds the prior from rank-rows, including the row just appended.

**PRIMARY FILES:**

- [bug_hunt_continue.py](../../../src/hive_planner/bug_hunt_continue.py)
- [rank-rows.jsonl](../../../.hive/bug-hunt/rank-rows.jsonl)

**UNLOCKS:**

- `bug_hunt.per_repo_dials`
- `bug_hunt.outcome_votes`

**THREAD COVERAGE:** The sample is not saved as the model. The mean is recomputed. The draw is used once.

***

## [HOOK:bug_hunt.outcome_votes]

**HOOK_ID:** `bug_hunt.outcome_votes`

**Meaning:** Weight votes only. Committed and review-failed pull weights toward that file's signals. Empty pulls away. Skipped casts no vote. This marker does not decide commit, restore, skip, or review-failed.

**PRIMARY FILES:**

- [spec.md](./spec.md)
- [rolling-cartridge.md](./rolling-cartridge.md)

**UNLOCKS:**

- `bug_hunt.anchor_votes`
- `bug_hunt.rank_row_append`

**THREAD COVERAGE:** Label rule for the shared weight update. Outcome policy stays in the spec.

***

## [HOOK:bug_hunt.no_hard_stop]

**HOOK_ID:** `bug_hunt.no_hard_stop`

**Meaning:** The hunt stops at the committed-fix ceiling, after two empty searches, or when no unopened location qualifies. The ceiling is a cap, not a quota. Enable writes it into the script. Iterations are 1 through 200. An unopened file is not an empty search. Record-and-skip and review-failed are not empty searches. An empty outcome restores that pass's edits and does not commit. Committed, skipped, and review-failed each reset the empty-search count.

**PRIMARY FILES:**

- [spec.md](./spec.md)
- [sandbox_rank_weights.py](../../../scripts/sandbox_rank_weights.py)

**UNLOCKS:**

- `bug_hunt.refit_threshold`
- `bug_hunt.outcome_decay`

**THREAD COVERAGE:** The spec's stop rules. Dial decay is a separate session note and is not these stop rules.

***

## [HOOK:bug_hunt.per_repo_dials]

**HOOK_ID:** `bug_hunt.per_repo_dials`

**Meaning:** Each repo inherits the hand weights as its seed and keeps its own posterior from its own rank-rows.

**PRIMARY FILES:**

- [spec.md](./spec.md)
- [rank-rows.jsonl](../../../.hive/bug-hunt/rank-rows.jsonl)

**UNLOCKS:**

- `bug_hunt.shared_weights`
- `bug_hunt.anchor_votes`

**THREAD COVERAGE:** Per-repo rolling dials. Snapshot path `.hive/bug-hunt/dials.json` is (planned). The log that feeds it is rank-rows.jsonl.

***

## [HOOK:bug_hunt.hand_weight_evidence]

**HOOK_ID:** `bug_hunt.hand_weight_evidence`

**Meaning:** On this repo's opened files, the hand weights rank real bugs worse than chance.

**PRIMARY FILES:**

- [sandbox_rank_weights.py](../../../scripts/sandbox_rank_weights.py)
- [rank-rows.jsonl](../../../.hive/bug-hunt/rank-rows.jsonl)

**UNLOCKS:**

- `bug_hunt.refit_threshold`
- `bug_hunt.signal_coercion`

**THREAD COVERAGE:** AUC 0.387 after coercion, top fifth holds about 15 percent of bugs, recent-fix commits overweighted, thin test underweighted.

***

## [HOOK:bug_hunt.refit_threshold]

**HOOK_ID:** `bug_hunt.refit_threshold`

**Meaning:** A six-weight recovery from a stable process is trustworthy at about 400 rows.

**PRIMARY FILES:**

- [sandbox_rank_weights.py](../../../scripts/sandbox_rank_weights.py)

**UNLOCKS:**

- `bug_hunt.no_hard_stop`
- `bug_hunt.hand_weight_evidence`

**THREAD COVERAGE:** Synthetic truth (1, 6, 2, 5, 3, 4). Cosine at least 0.95 on 80 percent of 40 trials first holds at 400 rows.

***

## [HOOK:bug_hunt.signal_coercion]

**HOOK_ID:** `bug_hunt.signal_coercion`

**Meaning:** Seven rank rows store signals as name tags. Those tags map onto the six numeric signals as ones.

**PRIMARY FILES:**

- [sandbox_rank_weights.py](../../../scripts/sandbox_rank_weights.py)
- [rank-rows.jsonl](../../../.hive/bug-hunt/rank-rows.jsonl)

**UNLOCKS:**

- `bug_hunt.hand_weight_evidence`
- `bug_hunt.rank_row_append`

**THREAD COVERAGE:** Coercion tally 389 rows, 386 labeled, 302 bugs, 84 empty, 3 skipped.

***

## [HOOK:bug_hunt.spec_foundation]

**HOOK_ID:** `bug_hunt.spec_foundation`

**Meaning:** Behavior for the new dials belongs in the bug-hunt spec before it is treated as execution truth.

**PRIMARY FILES:**

- [spec.md](./spec.md)
- [plan.md](./plan.md)
- [tasks.md](./tasks.md)

**UNLOCKS:**

- `spec.flow`
- `bug_hunt.per_repo_dials`

**THREAD COVERAGE:** Spec Kit stays the foundation. This cartridge is the mine, not the spec.

***

## [HOOK:bug_hunt.rolling_cartridge]

**HOOK_ID:** `bug_hunt.rolling_cartridge`

**Meaning:** This session's transcript and legend live in one append-only file beside the bug-hunt spec.

**PRIMARY FILES:**

- [rolling-cartridge.md](./rolling-cartridge.md)
- [ROSETTA-PLANNING-SESSION-CONTRACT.md](../../ROSETTA-PLANNING-SESSION-CONTRACT.md)

**UNLOCKS:**

- `planning.rosetta`
- `context.cartridge`

**THREAD COVERAGE:** Eject contract is the marker template. The canonical stone is the section layout. New material is appended.

***

## [HOOK:bug_hunt.continue_token]

**HOOK_ID:** `bug_hunt.continue_token`

**Meaning:** The pause and the continue token. A value of 10.0 or 0.0 counts. A wait longer than a day raises the hook timeout. A missing pause is read from the script before it falls back to 10. Active may be 1 or the word true. A crash that leaves active true still stops at the ceiling or at two empty searches. Active false at the start of a pass means the token was used.

**PRIMARY FILES:**

- [spec.md](./spec.md)
- [bug_hunt_continue.py](../../../src/hive_planner/bug_hunt_continue.py)

**UNLOCKS:**

- `bug_hunt.no_hard_stop`
- `change.bugfix_mode`

**THREAD COVERAGE:** R1 and R3 continue-token edges that the stop-rule marker does not state.

***

## [HOOK:bug_hunt.review_restore]

**HOOK_ID:** `bug_hunt.review_restore`

**Meaning:** Review and restore. A confirmed bug stays fix with no harness. A secret, a product decision, or a missing harness is record-and-skip before any edit, and the 0.65 classifier must not override that. Self-review runs only when a patch exists. A failed review is skipped only if that outcome was already skipped. Every other failure, including a failed commit, restores the edits and is review-failed. Invented bugs are forbidden.

**PRIMARY FILES:**

- [spec.md](./spec.md)
- [bug-hunt.md](../../../.cursor/commands/bug-hunt.md)

**UNLOCKS:**

- `bug_hunt.outcome_votes`
- `bug_hunt.rank_row_append`

**THREAD COVERAGE:** R1 classify, self-review, restore, and the ban on invented bugs.

***

## [HOOK:bug_hunt.install_edges]

**HOOK_ID:** `bug_hunt.install_edges`

**Meaning:** Install edges. Print mode writes nothing. A broken hooks file fails before the script is replaced. An omitted Home pause keeps the pause already in the script.

**PRIMARY FILES:**

- [spec.md](./spec.md)
- [bug_hunt.py](../../../src/hive_planner/bug_hunt.py)

**UNLOCKS:**

- `bug_hunt.rule_first`
- `bug_hunt.continue_token`

**THREAD COVERAGE:** R2 and R3 install edges outside the chat-trigger marker.

***

## [HOOK:bug_hunt.phrase_exclusions]

**HOOK_ID:** `bug_hunt.phrase_exclusions`

**Meaning:** Phrase exclusions. A question, a review, or a negation is not a start. End to end, and a start after another clause, are starts. The fallback script is scripts/bug-hunt.md. The agent does not answer by explaining how to invoke the command.

**PRIMARY FILES:**

- [spec.md](./spec.md)
- [bug-hunt.mdc](../../../.cursor/rules/bug-hunt.mdc)

**UNLOCKS:**

- `bug_hunt.rule_first`

**THREAD COVERAGE:** R4 exclusions and the positive exceptions around the chat trigger.

***

## [HOOK:bug_hunt.out_of_scope]

**HOOK_ID:** `bug_hunt.out_of_scope`

**Meaning:** Running the hunt inside Hive, auto-commit of product code, and remote upload are out of scope.

**PRIMARY FILES:**

- [spec.md](./spec.md)

**UNLOCKS:**

- `bug_hunt.spec_foundation`

**THREAD COVERAGE:** The spec's out-of-scope list.

***

## Coverage check

| Strand | HOOK_ID |
|---|---|
| Session legend | `planning.rosetta` |
| Chat trigger only | `bug_hunt.rule_first` |
| Python versus Markdown | `bug_hunt.markdown_split` |
| When a row is written | `bug_hunt.rank_row_append` |
| Rows are never pruned | `bug_hunt.rank_rows_grow` |
| Current predictor is prompt text | `bug_hunt.predictor_is_prompt` |
| Shared six-signal vector | `bug_hunt.shared_weights` |
| Twenty-vote hand-weight anchor | `bug_hunt.anchor_votes` |
| Decay by row order | `bug_hunt.outcome_decay` |
| Update on the next pass | `bug_hunt.same_hunt_update` |
| Weight votes only | `bug_hunt.outcome_votes` |
| Hunt stop rules | `bug_hunt.no_hard_stop` |
| Per-repo dials | `bug_hunt.per_repo_dials` |
| Hand weights vs this history | `bug_hunt.hand_weight_evidence` |
| Sample size for a trustworthy refit | `bug_hunt.refit_threshold` |
| Tag lists coerced to numbers | `bug_hunt.signal_coercion` |
| Spec Kit is execution truth | `bug_hunt.spec_foundation` |
| This append-only file | `bug_hunt.rolling_cartridge` |
| Continue token | `bug_hunt.continue_token` |
| Review and restore | `bug_hunt.review_restore` |
| Install edges | `bug_hunt.install_edges` |
| Phrase exclusions | `bug_hunt.phrase_exclusions` |
| Out of scope | `bug_hunt.out_of_scope` |

## Transcript

Append new segments below this line. Each decision already mined has one `[CTX:…]` member.

### [CTX:bug_hunt.rule_first]

**HOOK_ID:** `bug_hunt.rule_first`  
**Member type:** workflow  
**Promote to:** `docs/specs/bug-hunt/spec.md`

User asked how bug hunt works and how many files install. The always-on rule `.cursor/rules/bug-hunt.mdc` matches the phrase and tells the agent to read `.cursor/commands/bug-hunt.md` for one pass. Python `is_bug_hunt_request` does not see the keystroke. Install writes five files plus `.cursor/hooks.json`: the command, the rule, `.hive/bug-hunt/AGENT_PROMPT.md`, `scripts/bug-hunt.md`, and `.cursor/hooks/bug_hunt_continue.py`. The stop hook waits the pause, then starts the next pass. A hunt stops after 50 committed fixes, two empty searches, or no qualifying file. It does not push.

### [CTX:bug_hunt.markdown_split]

**HOOK_ID:** `bug_hunt.markdown_split`  
**Member type:** macro  
**Promote to:** `docs/specs/bug-hunt/spec.md`

Eight Python files install, loop, test, and commit. Twelve Markdown files are the script, the fallback, the packet, the rule, and the docs. The command, the fallback, and the packet are one generated text. Each pass reads one script. The packet is not opened during a run. Reading that Markdown does not change speed or memory in a meaningful way.

### [CTX:bug_hunt.rank_row_append]

**HOOK_ID:** `bug_hunt.rank_row_append`  
**Member type:** workflow  
**Promote to:** `docs/specs/bug-hunt/spec.md`

The append is step 6 of the script `bug_hunt.py` writes. The agent picks a file, inspects it, classifies it, edits only on fix, chooses `committed`, `skipped`, `empty`, or `review-failed`, and only then appends one row. Opening a file does not append. Python does not write the line.

### [CTX:bug_hunt.rank_rows_grow]

**HOOK_ID:** `bug_hunt.rank_rows_grow`  
**Member type:** constraint  
**Promote to:** `docs/specs/bug-hunt/spec.md`

`bug_hunt.py` and the stop hook never truncate, clear, rotate, or delete `.hive/bug-hunt/rank-rows.jsonl`. Python never opens that file. Later hunts may append another row for the same file. The 30-row line in the current script is a read threshold for a classifier, not a size cap.

### [CTX:bug_hunt.predictor_is_prompt]

**HOOK_ID:** `bug_hunt.predictor_is_prompt`  
**Member type:** macro  
**Promote to:** `docs/specs/bug-hunt/spec.md`

Before 30 completed rows the script tells the agent to rank by the installed slopes: log1p of recent fix commits × 0.7118, thin test × 3.3024, unwired hop × 1.0245, unread setting × -0.1424, reverted commit × 0, split stores × 0. `score_signals` in `bug_hunt.py` computes that score. After 30 rows with at least one `committed` and one other outcome, it tells the agent to fit a logistic regression and use probability 0.35 as the floor. A second scorer uses 0.65 and 0.35 for fix, record-and-skip, and empty. The fitted slopes are the active scoring weights. `score_signals` in `bug_hunt.py` applies them, with log1p on the fix-commit count.

### [CTX:bug_hunt.shared_weights]

**HOOK_ID:** `bug_hunt.shared_weights`  
**Member type:** requirement  
**Promote to:** `docs/specs/bug-hunt/spec.md`

An independent Beta per file does not help the rest of a hunt, because a file is usually opened once. The decision is one shared weight vector over the six signals. Each pass draws one vector, scores every unopened file, and opens the highest. A per-file residual is not identifiable when most files have a single row. The main risk is the first handful of outcomes swinging a loose prior.

### [CTX:bug_hunt.anchor_votes]

**HOOK_ID:** `bug_hunt.anchor_votes`  
**Member type:** requirement  
**Promote to:** `docs/specs/bug-hunt/spec.md`

Seed slopes μ = (0.7118, 3.3024, 1.0245, -0.1424, 0, 0). The first component multiplies log1p of the fix-commit count when a file is scored. Twenty imaginary votes set the draw width only. Newest row weight is 1. Each older row multiplies by 0.9. Skipped rows cast no vote. y is +1 for `committed` or `review-failed` and −1 for `empty`. The mean is μ plus the decayed signed signals divided by (2 + the sum of those weights). One new row moves a slope by about a third of its credit. A non-negative seed is not taken below 0.

### [CTX:bug_hunt.outcome_decay]

**HOOK_ID:** `bug_hunt.outcome_decay`  
**Member type:** constraint  
**Promote to:** `docs/specs/bug-hunt/spec.md`

Decay follows row order in `.hive/bug-hunt/rank-rows.jsonl`, because a row has no timestamp. The prior is rebuilt every pass. Nothing is saved as a fitted model except the rows themselves.

### [CTX:bug_hunt.same_hunt_update]

**HOOK_ID:** `bug_hunt.same_hunt_update`  
**Member type:** workflow  
**Promote to:** `docs/specs/bug-hunt/spec.md`

After the outcome row is appended, the next pass in the same hunt rebuilds the mean with that row included. The update does not wait for the next hunt. The drawn weights are used once and not written as the source of truth.

### [CTX:bug_hunt.outcome_votes]

**HOOK_ID:** `bug_hunt.outcome_votes`  
**Member type:** requirement  
**Promote to:** `docs/specs/bug-hunt/spec.md`

`committed` and `review-failed` add a success on the file's signals. `empty` adds a failure on those signals. `skipped` does not update the weights. The row is still logged.

### [CTX:bug_hunt.no_hard_stop]

**HOOK_ID:** `bug_hunt.no_hard_stop`  
**Member type:** requirement  
**Promote to:** `docs/specs/bug-hunt/spec.md`

There is no row count that freezes the dials. Decay is the forgetting mechanism. The hunt still stops on its existing rules: committed-fix ceiling, two empty searches, or no qualifying file.

### [CTX:bug_hunt.per_repo_dials]

**HOOK_ID:** `bug_hunt.per_repo_dials`  
**Member type:** macro  
**Promote to:** `docs/specs/bug-hunt/spec.md`

Each deployment inherits the global hand weights as the seed. Each repo's own `.hive/bug-hunt/rank-rows.jsonl` is the history. The intended snapshot of the current posterior is `.hive/bug-hunt/dials.json` (planned). Repos do not share a posterior.

### [CTX:bug_hunt.hand_weight_evidence]

**HOOK_ID:** `bug_hunt.hand_weight_evidence`  
**Member type:** validation  
**Promote to:** `docs/specs/bug-hunt/spec.md`

`scripts/sandbox_rank_weights.py` scored the real history. After coercion, the retired hand weights (3, 5, 5, 4, 4, 4) had AUC 0.387. Those numbers are not the scoring weights. The top 20 percent of that score holds about 15 percent of the bugs. `recent_fix_commits` alone is AUC 0.328. `thin_test` alone is AUC 0.688. `reverted` never appears. `dead_setting` appears six times. A later-row holdout preferred a refit (AUC 0.674) whose positive weights, scaled to sum to 25, were about (0, 17.6, 0, 0, 0, 7.4). These rows are files the hunt already opened.

### [CTX:bug_hunt.refit_threshold]

**HOOK_ID:** `bug_hunt.refit_threshold`  
**Member type:** validation  
**Promote to:** `docs/specs/bug-hunt/spec.md`

Synthetic rows used truth (1, 6, 2, 5, 3, 4), 40 trials, tolerance cosine at least 0.95 on 80 percent of trials. Median cosine was 0.52 at 10 rows, 0.84 at 30, 0.95 at 100 with only 48 percent of trials inside the tolerance, and 0.98 at 400 with 98 percent inside. The trust line is about 400 rows from a stable process.

### [CTX:bug_hunt.signal_coercion]

**HOOK_ID:** `bug_hunt.signal_coercion`  
**Member type:** constraint  
**Promote to:** `docs/specs/bug-hunt/spec.md`

Seven `signals` fields are lists of name tags, not numbers. The sandbox maps `prior-bug-fixes` to recent fix commits, reader tags to split stores, `wiring-hop-check` to an unwired hop, and `dead-button-check` to a dead setting, each as 1. The tally is 389 rows, 386 labeled, 302 bugs, 84 empty, 3 skipped. Coercion did not lift the hand-weight AUC above chance.

### [CTX:bug_hunt.spec_foundation]

**HOOK_ID:** `bug_hunt.spec_foundation`  
**Member type:** workflow  
**Promote to:** `docs/specs/bug-hunt/spec.md`

The adaptive dials are a behavior change. The session required the bug-hunt spec, plan, and tasks to be updated before that behavior is execution truth. This cartridge records the decisions so the spec can be mined. It does not replace the spec.

### [CTX:bug_hunt.rolling_cartridge]

**HOOK_ID:** `bug_hunt.rolling_cartridge`  
**Member type:** workflow  
**Promote to:** `docs/specs/bug-hunt/rolling-cartridge.md`

The eject template is `docs/ROSETTA-PLANNING-SESSION-CONTRACT.md`, copied by `src/hive_planner/rosetta_eject.py`. The section layout follows `docs/planning-rosetta-stone.md` and `docs/planning-rosetta-stone-generation-template.md`. This session's legend and transcript stay in this one file. New conversation segments are appended after the last transcript member.

### [CTX:legend.marker_clarification]

**HOOK_ID:** `bug_hunt.rolling_cartridge`  
**Member type:** constraint  
**Promote to:** `docs/specs/bug-hunt/rolling-cartridge.md`

Second-pass remine. The spec already stated the continue token, the stop rules, the review guards, the install edges, and the out-of-scope list, so those sentences were not copied in again. Three legend meanings were narrowed so they stop hiding those rules: `bug_hunt.rule_first` is the chat trigger only, `bug_hunt.outcome_votes` is weight votes only, and `bug_hunt.no_hard_stop` states the spec's stop rules.

### [CTX:bug_hunt.continue_token]

**HOOK_ID:** `bug_hunt.continue_token`  
**Member type:** requirement  
**Promote to:** `docs/specs/bug-hunt/spec.md`

R1 and R3. A pause written as 10.0 or 0.0 counts. A wait longer than a day raises the hook timeout. A missing pause is read from the installed script before it falls back to 10. Active may be 1 or the word true. A crash that leaves active true still stops at the ceiling or at two empty searches. Active false at the start of a pass means the token was used.

### [CTX:bug_hunt.review_restore]

**HOOK_ID:** `bug_hunt.review_restore`  
**Member type:** requirement  
**Promote to:** `docs/specs/bug-hunt/spec.md`

R1. A confirmed bug stays fix even with no harness. A secret, a product decision, or a missing harness is record-and-skip before any edit, and the 0.65 classifier must not override that. Self-review runs only when a patch exists. Tests are ranked from past diffs. A failed review is skipped only if that outcome was already skipped. Every other failure, including a failed commit, restores the edits and is review-failed. Invented bugs are forbidden.

### [CTX:bug_hunt.install_edges]

**HOOK_ID:** `bug_hunt.install_edges`  
**Member type:** requirement  
**Promote to:** `docs/specs/bug-hunt/spec.md`

R2 and R3. Print mode writes nothing. A broken hooks file fails before the script files are replaced. An omitted Home pause keeps the pause already written in the script, and uses 10 only when no script pause exists.

### [CTX:bug_hunt.phrase_exclusions]

**HOOK_ID:** `bug_hunt.phrase_exclusions`  
**Member type:** requirement  
**Promote to:** `docs/specs/bug-hunt/spec.md`

R4. A question, a review, a summary, an audit, an explanation, or a negation is not a start. End to end, and a start after another clause, are starts. The fallback file is scripts/bug-hunt.md. The agent does not answer by explaining how to invoke the command.

### [CTX:bug_hunt.out_of_scope]

**HOOK_ID:** `bug_hunt.out_of_scope`  
**Member type:** constraint  
**Promote to:** `docs/specs/bug-hunt/spec.md`

Out of scope: running the hunt inside Hive, auto-commit of product code, and remote upload.

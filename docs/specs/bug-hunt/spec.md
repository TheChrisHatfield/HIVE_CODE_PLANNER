# Spec: bug-hunt

**Hook:** `change.bugfix_mode`, `integration.wiring_audit`  
**Status:** active  
**Delta:** [bug-hunt.md](../../delta/20_micro/bug-hunt.md)

<!-- ROSETTA-NAV -->

## Agent navigation (Rosetta Stone)

Before implementing, load the hook map — do not jump straight into requirements.

1. [`docs/planning-rosetta-stone.md`](../../planning-rosetta-stone.md) — hook `planning.rosetta`
2. Follow **UNLOCKS**: `change.bugfix_mode`, `integration.wiring_audit`
3. This feature — hook `spec.flow`:
   - Delta micro: [`bug-hunt.md`](../../delta/20_micro/bug-hunt.md)
   - Plan: [`plan.md`](./plan.md)
   - Tasks: [`tasks.md`](./tasks.md)

## What

A core Hive Planner feature that installs the continuous bug-hunt agent script into a project and starts that loop from any Cursor chat when the user asks to hunt bugs.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A hunt request starts one pass (Priority: P1)

The user asks to hunt bugs in a Cursor chat. The always-on rule reads the installed script and starts that loop in the same turn. One inference pass runs, then the turn ends.

**Why this priority**: A request that only explains the command does not hunt. R4 is the start signal. R2 and R3 put the script and the stop hook on disk.

**Independent Test**: With the command, rule, packet, and stop hook installed, send a start phrase such as `bug hunt` or `hunt for bugs`. The agent reads `.cursor/commands/bug-hunt.md` and runs one pass. A question about where the file is, or `do not run the bug hunt`, does not start a pass.

**Acceptance Scenarios**:

1. **Given** the bug-hunt artifacts are installed, **When** the user says `run a bug hunt`, **Then** the agent starts the script in that turn and does not answer with install instructions.
2. **Given** the same install, **When** the user asks whether the command works or where the file is, **Then** that message is not a start signal.
3. **Given** a hunt in progress, **When** the user says `stop the bug hunt`, **Then** the loop does not restart.
4. **Given** Controls **Bug hunt → Enable → Run** on the active linked project, **When** Pause seconds is blank, **Then** the installed script waits 10 seconds between passes. `0` installs a script that does not wait.

---

### User Story 2 - One pass opens one location and records one outcome (Priority: P2)

Each pass ranks locations, opens the highest qualifying file this hunt has not opened, and classifies the scenario before any edit. Only **fix** is edited. The pass writes one rank row, writes `continue.json`, and ends the turn.

**Why this priority**: The ceiling is 50 committed fixes, not 50 passes. An empty search, a skip, and a failed review are different outcomes. R1 defines that order.

**Independent Test**: Run one pass against a repo that has at least one qualifying unopened file. The pass opens one file, appends one row to `.hive/bug-hunt/rank-rows.jsonl`, and does not push.

**Acceptance Scenarios**:

1. **Given** a confirmed bug, **When** the pass classifies it, **Then** the class is **fix**, including when the harness is missing.
2. **Given** a potential bug that needs a product decision, touches a secret, or has no harness, **When** the pass classifies it, **Then** the class is **record-and-skip**, no edit is committed, and the outcome is `skipped`.
3. **Given** a patch whose review fails and that is not a secret or a product decision, **When** the pass finishes, **Then** that iteration's uncommitted edits are restored and the outcome is `review-failed`.
4. **Given** two consecutive empty outcomes, **When** the second is written, **Then** the hook enters R11 recovery if a qualifying unopened production location remains; otherwise `continue.json` is active false and the hook does not start another pass.
5. **Given** a passing review and none of the skip exceptions, **When** the local commit succeeds, **Then** the outcome is `committed`. The pass does not push.

---

### User Story 3 - The ranker rebuilds, decays, and draws (Priority: P3)

Before the edit, the pass rebuilds the six score weights from this repo's rank rows, decays older voted rows, and draws one Thompson sample of those six slopes. R9 adds a trust draw and one place draw per candidate folder. It opens the highest total score among unopened files. Finding count, then line count, break remaining ties. Draws are discarded as learning inputs; an optional audit copy may remain in the pass state and selected row. The next pass rebuilds again.

**Why this priority**: R5 and R6 replace a permanent fixed sum and the instruction to fit a logistic regression after 30 completed rows. The seed stays the start of the rebuild.

**Independent Test**: With rank rows on disk, score the same six signals twice, once before a new voted row and once after the next rebuild. The second mean has moved. The drawn vector from the first pass is not the stored mean.

**Acceptance Scenarios**:

1. **Given** `.hive/bug-hunt/rank-rows.jsonl` has voted rows, **When** a pass starts, **Then** `bug_hunt.py` rebuilds the six weights from those rows. The slopes do not stay fixed at the seed.
2. **Given** a `committed` or `review-failed` row, **When** the mean is rebuilt, **Then** the weights move toward that file's signals. An `empty` row pulls them away. A `skipped` row casts no vote.
3. **Given** the rebuilt mean, **When** the pass scores unopened files, **Then** it uses one Thompson sample around that mean as the six-signal part of the score, opens the highest total score, and any stored draw is audit-only and cannot affect a later rebuild.
4. **Given** the hunt script, **When** a pass ranks locations, **Then** it does not switch to a logistic regression after 30 completed rows.

---

### User Story 4 - Attention explores with the same memory-plus-sample loop (Priority: P3)

Exploration is a sibling of the six weights, not a timer. Each pass rebuilds two extra posteriors from the same rank rows: detector trust, and place attention over folders. It draws once for the six-vector, once for trust, and once per candidate folder, adds those draws to the score, and discards the draws. The next pass rebuilds again. There is no every-Nth file, no epsilon-greedy coin flip, and no reserved quota of ignored files.

**Why this priority**: A fixed findings bonus and a three-commit folder block make the hunt narrow. Those hammers are replaced by sampled parts that drift with outcomes the same way the six slopes do.

**Independent Test**: After `empty` rows on finding files, rebuilt trust mean is below the 1.0 seed. After enough of those votes that the trust mean is at or below 0, a no-finding file outranks a finding file when the six-draw and place draws are equal. After several `empty` rows in one folder, that folder's mean stays at 0. A committed folder can rise above 0, so a later draw can score that other folder higher without a hardcoded rotation threshold.

**Acceptance Scenarios**:

1. **Given** voted rank rows, **When** a pass starts, **Then** `bug_hunt.py` rebuilds detector trust and place attention from those rows as well as the six weights.
2. **Given** a `committed` or `review-failed` row on a file with a detector finding, **When** trust is rebuilt, **Then** the mean stays at or moves toward 1.0. An `empty` row on a finding file pulls the mean below the 1.0 seed. A `skipped` row casts no vote on trust. A findings-zero row does not. A voted row that omits the `findings` key still votes on trust.
3. **Given** a voted row in a folder, **When** place attention is rebuilt, **Then** that folder's mass moves with the outcome the same way: pull toward on `committed` or `review-failed`, pull away on `empty`.
4. **Given** the rebuilt posteriors, **When** the pass scores unopened files, **Then** the R9 exploit score is one linear mix of three discarded draws (six-signal, trust × finding bit, folder attention), and R10 adds only its bounded uncertainty/coverage bonus after that score. It does not add a fixed findings-present bonus, does not force findings-first order, and does not rotate on a count of three commits.
5. **Given** recent voted outcomes that disagree with the previous pass's ranking, **When** the next draws are taken, **Then** the bells are wider than when recent outcomes matched. The width comes from that residual, not from a pass index.

### Edge Cases

- A blank pause is 10 seconds. `0` does not wait. The wait is not skippable. The normal two-empty threshold is an R11 recovery trigger when a qualifying unopened production location remains; it is a final stop only when recovery cannot start.
- Active false at the start of a pass means the previous continue token was used. It does not mean the hunt is over.
- Unopened files are not empty searches. Record-and-skip and `review-failed` do not count as empty searches.
- The script does not push and does not fill the ceiling with invented bugs.
- Each repo learns only from its own rank rows. Repos do not share a posterior.
- Folder identity uses the first part of the repo-relative posix path (backslashes become slashes, `./` prefixes stripped). Root files use `.`. `.cursor/hooks/x.py` is folder `.cursor`, not empty. Folder compare is case-insensitive on Windows the same way opened-file keys are.
- An explicit findings count of 0, or a non-finite findings value, is not a trust vote. A voted row that omits the `findings` key still votes on trust. A voted row that omits both `findings` and `score` is a ranking disagreement. A missing or non-finite `score` on a row that stores `findings` is not. A corrupt jsonl line is skipped and does not vote.
- An empty jsonl file keeps every posterior at its seed. Unused folders keep seed 0 and full imaginary-vote evidence even when other folders have many votes.
- If every remaining candidate shares one folder, that folder is drawn once and added to every score, so six-signal and trust still decide the order.
- If no remaining candidate has a finding, the trust draw is multiplied by 0 for every file. Trust still rebuilds for later passes.
- Imaginary votes shrink toward 0 as that posterior's vote count grows. Evidence is imaginary votes plus decayed real votes. With no voted rows, evidence is the full twenty. With many voted rows, decayed real votes cap near ten, so width stays finite. If `evidence` is not positive, width is 1 times `1+m`.
- The agent does not have to write `findings` or `score` on `continue.json`. The stop hook copies those fields from that file's `rank-pass.json` row when it appends `rank-rows.jsonl`.
- For an R11 empty outcome, the stop hook also copies a finite `empty_confidence` and the bounded recovery lens from the selected `rank-pass.json` row before rewriting the queue. Missing confidence defaults to `1.0`; malformed recovery metadata is omitted without dropping the outcome row.
- The complete rank-row schema is `file`, `signals`, `scenario`, `outcome`, `findings`, and `score`, with optional R10 `attribution` and optional R11 `empty_confidence` and `recovery_lens`; legacy rows may omit all optional fields and remain readable.
- Stored `findings` is a count. A bool, a list of hits, a non-integer string, or overflow that is not a finite integer is 0. Six-signal `signals` may be a dict of the six keys or a 6-list; both vote on the six posterior. Trust and place still vote when that vector is missing.
- If the opened file is missing from `rank-pass.json`, the row is still appended with `findings` 0 and `score` 0. That `score` is not a ranking disagreement.
- If every one of the last ten voted rows stores `findings` and has a missing or non-finite `score`, `m` is 0 and the surprise scale is 1. A voted row with neither `findings` nor `score` is a disagreement, so those old rows move the scale.
- An empty relative path is not opened. A blank `file` on `continue.json` does not open the queue head. A stop with no valid outcome still appends one `stopped` row, and that outcome casts no vote. When `file` is blank, that row's file is empty and the queue head stays unopened. A file with no slash is folder `.`.

## Requirements

### R1 — Script text

- `render_agent_prompt(iterations, pause_seconds=None)` describes one inference pass per iteration: rank a location, deep-dive, apply a fix, internal self-review, local commit, write the outcome row, write `.hive/bug-hunt/continue.json`, then end that turn.
- A blank pause is 10 seconds. The stop hook waits that many seconds, and the wait is not skippable. `0` makes the hook start the next pass without waiting. Any positive whole number is the wait in seconds, including a value written as `10.0` or `0.0`. The hook's time limit is raised when that wait is longer than a day, so the wait is not cut off. The hook consumes `continue.json` after the wait and submits the next inference pass, so ending the turn does not stop the hunt. Active false at the start of a pass means that token was used, not that the hunt is over. The agent must not ask whether to continue. When a stop condition is met, the continue file is written with active false and the hook does not start another pass. A committed, skipped, or review-failed outcome resets the empty-search count.
- The default iteration count is 50. That count is a ceiling on committed fixes, not a quota. Controls Fix ceiling starts at 50, and Enable writes that field into the script.
- The empty-search counter and the R11 recovery state are distinct: a committed, skipped, or review-failed outcome resets both; an empty outcome increments the applicable counter and does not reset recovery state.
- Before editing, the script ranks locations from rolling neural weights, not from a permanent fixed sum. The bootstrap seed is 0.7118, 3.3024, 1.0245, -0.1424, 0.0, and 0.0 (log1p of fix-commit churn, a thin or failing test counted once, an unwired hop, an unread flag, a reverted commit, two stores for one fact). Those six numbers are the seed-zero slopes from the Wednesday 4 November 2026, 3:25 AM optimality check. 0.884 is that check's fitted median AUC, not a second weight vector. A file-order AUC of 0.946 was inflated by blank rows. 0.884 is the real ceiling, and that check did not move toward 0.946. The old hand weights 3, 5, 5, 4, 4, and 4 are not the seed. They are not a permanent fixed set. The old rule that a logistic regression replaces those weights after 30 completed rows is superseded by R6. The six-signal score is one linear layer on those six signals. R9 then mixes detector trust and place attention into the same pass total. During every bug hunt run, continual backpropagation updates the rolling weights from voted outcomes, so the ranker changes as rows accumulate. Those rolling weights feed the prior used for Thompson sampling. Each pass draws one six-weight vector from a bell curve around the current mean, mixes the R9 draws (one trust draw and one place draw per candidate folder), and opens the highest total among unopened files. A per-file Beta was considered on November 2 and was not adopted. After the linear mix, finding count then line count break remaining ties. A mitigating system for a bad result stays active: the seed is an offset and is not averaged away. Twenty imaginary votes set the draw width only. One voted row moves a slope by about a third of its credit, and a non-negative seed is not taken below 0. Older rows decay. A skipped row casts no vote. Self-review still gates a commit. The pass draws around the rebuilt mean. A zero file signal adds no credit, does not change vote weights, and a stored draw does not move it. The draw does not replace the mean. A test file is not a hunt location. R9 mixes discarded trust and per-folder place draws into that pass's score. Unopened locations are not empty searches. The scenario classifier later in this section is unchanged.
- Before the edit, the script classifies the named scenario as fix, record-and-skip, or empty. A confirmed bug stays fix, including when the harness is missing. A potential bug that needs a product decision, touches a secret, or has no harness is record-and-skip before any edit. A classifier may use 0.65 and 0.35 on P(real bug) only after 30 rows in `.hive/bug-hunt/rank-rows.jsonl`, and must not override those two rules. Only fix proceeds to the edit. Self-review runs only when a patch exists. A failed review is not an empty search. It is `skipped` only when the outcome order already chose `skipped` (record-and-skip, product decision, or secret). Every other failed review restores that iteration's uncommitted edits and is `review-failed`.
- Each opened location appends one row (file, signals, scenario, outcome, findings, score, and optional R10 attribution) to `.hive/bug-hunt/rank-rows.jsonl` once, after the outcome is known. `findings` is the detector hit count used on that pass (0 if none). `score` is that pass's exploit-plus-exploration score for the opened file. Outcome is `committed`, `skipped`, `empty`, or `review-failed`. A failed review is `skipped` only when the outcome order already chose `skipped`. Every other failed review is `review-failed`. The location model treats `committed` and `review-failed` as pulls toward that file's signals. An `empty` row pulls them away. A `skipped` row casts no vote. The classifier treats `committed` and `review-failed` as a real bug. R9 rebuilds trust from `findings` on voted rows; a row that omits `findings` still votes on trust, and an explicit findings count of 0 does not. A row that omits both `findings` and `score` is a ranking disagreement. A missing `score` on a row that stores `findings` is not a ranking disagreement. The stop hook copies `findings`, `score`, and valid attribution from `rank-pass.json`; `continue.json` still only needs `file`, `scenario`, and `outcome` unless it carries a validated direct-inspection override. Legacy rows without attribution remain valid and are ignored by learning. The next hunt reads that file and may append a new row for a location this run already recorded. The queue opens the highest qualifying score only. Finding count, then line count, break remaining ties. A detector finding still qualifies a file even when the trust draw is negative.
- After the patch, the script ranks tests from past diffs on the same files and runs the top of that list. The ranker orders the harness. The self-review gate still decides the commit.
- R10 prompt and hook wiring carries optional `requested_file` and `requested_line` direct-inspection metadata, validates them before inspection, and labels the resulting attribution `override`. The line is review guidance only; it is never a separate location or vote. R10 attribution is optional for legacy state, is bounded to 4 KiB per persisted row, and malformed attribution fails closed as absent.
- The loop stops at the ceiling, after R11 recovery is exhausted, or when no unopened location still qualifies. Before R11, two consecutive empty searches stop only when recovery cannot start. An empty search is an opened location classified empty, or an opened location with neither a confirmed bug nor a potential bug. Record-and-skip and `review-failed` are not empty searches. An empty outcome restores that iteration's uncommitted edits and does not commit.
- A product decision or a secret is recorded as `skipped` and is not committed, including when the review fails or the patch cannot be covered. An uncoverable or failed patch that is not a secret or a product decision is `review-failed` and is not committed. A passing review commits only when none of those exceptions apply. If that local commit fails, the outcome is `review-failed` and that iteration's uncommitted edits are restored.
- The script forbids push and forbids filling the budget with invented bugs.

### R2 — Install

- `hive_planner bug-hunt` writes `.cursor/commands/bug-hunt.md`, `.cursor/rules/bug-hunt.mdc`, `.hive/bug-hunt/AGENT_PROMPT.md`, `scripts/bug-hunt.md`, and `.cursor/hooks/bug_hunt_continue.py` under `--root`. It adds that hook to `.cursor/hooks.json` on `stop` without removing other hook events.
- The rule is `alwaysApply` and treats a chat request to perform a bug hunt as the start signal for the script.
- `--iterations` accepts 1 through 200.
- `--pause-seconds` accepts 0 or any positive whole number the stop hook can wait (not larger than the platform sleep limit). The default is 10. `0` skips the wait.
- `--print` writes nothing and prints the script.

### R3 — Wiring

- The pre-R11 counter behavior described below applies only to installed artifacts that have not yet been upgraded. Once R11 is implemented and its generated artifacts are emitted together, the two-empty counter enters recovery whenever a qualifying unopened production location remains.

- The CLI command calls `install_bug_hunt`. A successful run leaves the command, the always-on rule, the packet, and the stop hook on disk. The command and packet contain the requested iteration count and the pause seconds for that run. The hook reads `.hive/bug-hunt/continue.json` from the working directory or a parent directory, waits `pause_seconds` when that file is active (`true`, `1`, or the word true; `0` does not wait; a missing pause is taken from the installed script before the 10-second default), clears active after the wait, and returns `followup_message` so the next turn is the next iteration. Each pass writes `ceiling`, `committed`, and `consecutive_empty` beside `active` and `pause_seconds`. The hook honors those counters even when `active` was left true by a crash: at the ceiling or at two consecutive empty outcomes it clears the token and does not start another pass. A broken `.cursor/hooks.json` fails a direct install before the script files are replaced. Init and handoff deploy replace that broken file when force is set, then install the stop hook onto the replacement.
- `init_project` and `deploy_agent_handoff_scaffold` install the same artifacts so new and upgraded Hive projects can start hunts from chat. Those installs use the default pause of 10 seconds.
- Home **Loop controls** opens the Controls tab. Controls **Bug hunt → Enable → Run** calls `run_project_bug_hunt_install` on the active linked project. Fix ceiling and Pause seconds are fields on that block. A blank Pause seconds field installs 10. `0` installs a script that does not wait. `hive_bug_hunt_enable` accepts `pause_seconds`. When that argument is omitted, the enable keeps the pause already written in the installed script, and uses 10 only when no script pause is found.

### R4 — Chat start signal

- `is_bug_hunt_request(text)` is true for explicit phrases and derivatives whose meaning is to run a hunt: "bug hunt", typos ("bug hun", "bung hunt"), hyphenation, `/bug-hunt`, "hunt for bugs", "start hunting bugs", "run a bug hunt", "run another loop to fix bugs", "loop to fix bugs".
- A question about the command itself (whether it works, where the file is, how to install it) is not a start signal. A review, summary, audit, or explanation request for the script is not a start signal unless that same message then starts a hunt ("read the bug hunt command and start a bug hunt"). A negation or stop request ("do not run the bug hunt", "stop the bug hunt", "skip the bug hunt", "never bug hunt", "do not loop to fix bugs") is not a start signal and must not restart the loop. "end to end bug hunt" and a start after another clause ("stop explaining and run a bug hunt") are start signals.
- The always-on rule tells the agent to read `.cursor/commands/bug-hunt.md` (fallback `scripts/bug-hunt.md`) and start the loop in the same turn — not to explain how to invoke it.

### R5 — Continual weight update

These rules are the update mechanics for the ranking in R1. The permanent fixed sum and the 30-row logistic gate are superseded, as R1 states. R5 itself stays.

R11 supersedes any earlier two-empty final-stop wording: two consecutive empty outcomes trigger bounded recovery when a qualifying unopened production location remains; they stop the hunt only when recovery cannot start.

- One weight vector is shared across files. It has six signals in this order: recent fix commits, a thin or failing test, an unwired hop, an unread setting, a reverted commit, and two stores for one fact. A file's own later row is not the only way other files move. Outcomes update the shared vector, and the next pass scores files that have not been opened yet.
- The seed is 0.7118, 3.3024, 1.0245, -0.1424, 0.0, and 0.0, the same six slopes named in R1. 0.884 names their fitted median AUC, not a replacement tuple. The first weight multiplies log1p of the fix-commit count. The other five multiply the raw signals. A thin or failing test is counted once: a production file that already has a wiring hop, unread flag, revert, or split store does not also take the thin-test bit from a missing test file. One committed thin row still moves that slope by about a third of its credit. Twenty imaginary votes set the draw width and halve for every forty voted rows. They are not in the residual divisor. A skipped row is not a voted row. Trust and place use their own vote counts, as R9 states. Each repo starts from that seed and updates only from its own file. Repos do not share a posterior.
- Decay of real rows follows row order, because a row has no timestamp. The newest voted row counts as 1. Each step older multiplies by 0.9. The seed stays an offset. It is not averaged with the file signals, so a seed of 3.3 is not diluted down toward a 0/1 bit. Real votes add a residual: `seed + Σ(sign × decay × credit) / (2 + Σ decay)`. The twenty imaginary votes set the draw width only. They are not in that divisor. One real vote therefore moves a slope by about a third of its credit. A slope whose seed is non-negative is not taken below 0. A negative seed is not taken lower than that seed. Credit is the file signal. A signal of 0 adds no credit. A voted row whose six features are all zero is not a six-slope vote: it does not move the mean and it does not change vote weights. A stored draw does not move that slope, and it does not pull a slope through the floor. Continual backpropagation is that rebuild. It is not a second step that replaces the mean with the drawn vector. The drawn weights score that pass. The next rebuild does not read them as credit.
- A `committed` or `review-failed` row pulls the weights toward the signals present on that file. An `empty` row pulls them away. A `skipped` row is logged and casts no vote.
- One new voted row moves its slope by about one third of that row's credit, because the residual divisor starts at 2, not at twenty. Row decay still caps the remembered real votes near ten, so the residual tracks recent outcomes rather than every row ever logged. There is no row count that freezes the update. About 400 rows from a stable process is when a six-weight recovery is trustworthy. That number is not a switch, not a hunt stop, and not a count the decayed mean treats as equal votes.
- Each pass draws one weight per signal from the rebuilt prior, scores every **qualifying** production file this hunt has not opened (any of the six signals or a detector finding), and opens the first file in that pass's queue. A test file is not a hunt location. After a patch, tests are ranked and run. The Python and C# detector paths both emit wiring, unread-setting, and split-store signals where their syntax supports them. A wiring hop on production code still qualifies. Detector findings are not a seventh rolling weight on the six-signal vector. A detector finding still qualifies a file. How much a finding moves the queue is R9 (sampled detector trust), not a fixed bonus and not a findings-first sort. Decay, seed votes, and the discarded six-draw stay on the six weights. The hunt's own stops still apply: the committed-fix ceiling, two empty searches, or no qualifying file.
- `bug_hunt.py` rebuilds these six weights from `.hive/bug-hunt/rank-rows.jsonl` at the start of each pass, using the decay above. The seed stays the start of that rebuild. The slopes do not stay fixed at the seed once rank rows exist.
- If a supplied learned seed is present but a malformed or extreme row makes the residual update non-finite, the rebuild preserves that supplied seed rather than reverting to the original bootstrap seed.

### R6 — Rolling weights

These rules are the rolling-weight half of the same design as R1 and R5. R5 states the update mechanics. R1 states how a pass uses them.

- The six weights are rolling weights. The score is one linear layer on the six signals, the same mathematics as a pared-down network with no hidden layer. Each voted outcome updates those weights by continual backpropagation. The update is not a one-time refit and not a swap to a new static vector.
- A sandbox on this repo's rank rows found the original hand weights stale. Their score ranked real bugs at AUC 0.387, and the top fifth of that score held about 15 percent of the bugs. The canonical start remains the R1 seed. A file-order AUC of 0.946 was inflated by blank rows. The 3:25 AM optimality check on 4 November 2026 measured a fitted median AUC of 0.884 and did not move toward 0.946. 0.884 is that ceiling. It is not a sixth set of slopes.
- About 400 rows is when a recovery of the six weights is trustworthy if those rows come from one stable process. Reaching 400 does not install a new fixed set. Logging to `.hive/bug-hunt/rank-rows.jsonl` continues, and the rolling update continues. A fitted vector may be compared with the hand numbers. That comparison does not by itself replace the rolling weights.
- Each repo's rolling dial is the adaptation layer on top of the shared seed. The seed remains the offset, as R5 states. It is not averaged away as voted rows accumulate. The dial is that repo's own running update from its own rows.
- A pass draws weights from a bell curve around the current mean. The queue file may store one audit copy of that six-vector draw so the selected row can be explained, but the draw is not learning state and queue rows do not each store a draw. A per-file Beta was considered on November 2 and was not adopted. The next pass rebuilds the mean from the seed offset plus the voted residuals. The shared prior absorbs a voted row's credit for every file scored on the next pass. A stored draw is not credit. A zero file signal stays zero. The draw does not replace the mean.
- That draw is one Thompson sample of the six slopes. It replaces the fixed slopes in `bug_hunt.py` and the hunt script's instruction to fit a logistic regression after 30 completed rows. The script scores with the drawn six weights plus the R9 attention draws. The 30-row logistic instruction is superseded, as R1 and R5 state.

### R9 — Attention (exploration)

Exploration is a memory-plus-sampler part in the same loop as R5 and R6. It is not a hardcoded schedule. There is no epsilon-greedy coin, no every-Nth open, no reserved slice of ignored files, and no fixed findings-present bonus.

The queue score for an unopened file is one linear mix of three Thompson draws, rebuilt from the same `.hive/bug-hunt/rank-rows.jsonl`. The draws are ephemeral for learning; an audit copy may be retained in `rank-pass.json` and the selected rank row, but no rebuild reads that copy as evidence:

1. Six-signal draw (R5/R6).
2. Detector trust draw times a 0/1 finding bit (1 when **this pass's detector scan** for that file has a findings count greater than 0). Findings stay off the six-vector. Trust is one shared posterior, not a per-file Beta (a per-file Beta was considered on November 2 and was not adopted). Rebuilds of that posterior use each **row's stored `findings`**, which may differ from a later scan of the same path.
3. Place-attention draw for that file's folder. The folder is the first path part, or `.` when the file sits at the repo root. That is the same grain the old three-commit rotation used.

Each of those posteriors uses the same residual as R5. Twenty imaginary votes halve every forty **votes of that posterior** and set that posterior's draw width. They are not in the divisor. Real rows decay by 0.9. `committed` and `review-failed` have sign +1. `empty` has sign −1. `skipped` casts no vote. A findings-zero row is not a trust vote. A row that omits the key is. A row in `src` is not a vote on `tests`.

Trust is one scalar. Seed mean is 1.0. A voted row votes on trust when its `findings` count is greater than 0, or when the key is absent. The feature is 1. The rebuild is `seed + Σ(sign × decay × 1) / (2 + Σ decay)`. A finding-file `empty` lowers trust from 1.0 and does not take it below 0. A finding-file `committed` or `review-failed` raises it. A row with `findings` 0 does not move trust. A row that omits `findings` does. Trust votes do not require a parseable six-signal vector. Place votes do not either.

Place attention is one scalar per folder, seed mean 0.0, rebuilt on its own votes. A voted row votes only on its folder (first path part, or `.`). The feature is 1. Empty votes do not take the mean below 0. A place term in the score is not below 0. Folders that have never been voted keep the seed and the full imaginary-vote evidence, so their draw stays wide until they collect rows.

Each pass draws `gauss(mean, width)` once per six slope, once for trust, and once per folder that appears in this pass's unopened candidates. Each posterior keeps its own evidence (imaginary votes plus decayed real votes of **that** posterior). Width is `(1 / sqrt(evidence)) × (1 + m)` using that posterior's evidence. `m` is shared: the fraction of the last ten voted rows (fewer if fewer exist) whose outcome sign disagreed with the sign of that **row's stored `score`** (positive score with `empty`, or non-positive score with `committed`/`review-failed`). Voted here means `committed`, `review-failed`, or `empty`. A missing or non-finite `score` on a row that stores `findings` stays in that ten and is not a disagreement. A voted row with neither `findings` nor `score` is a disagreement. `rank-pass.json` is overwritten each pass, so it is not the history for `m`. The scale is not a pass index. The same `1+m` multiplies every draw on that pass. The three mix terms are added in native units with no extra scale. Slope and trust draws may be negative. A place draw is not below 0. They are discarded as learning inputs. The next rebuild reads rows only. A negative trust draw does not drop a finding file from the qualified pool.

The old findings-first wall and the three-commit same-folder rotation are superseded. Finding count, then line count, break remaining ties after the linear mix. Qualifying is unchanged: any of the six signals or a detector finding.

The queue score is that mix plus a fixed bug-likelihood term. Likelihood is not a seventh learned slope and does not enter the rebuild. Lines, branch lines (`if`, `elif`, `else`, `for`, `while`, `except`, `finally`, `with`, `case`, `catch`, `switch`), and half of log1p of call sites share one surface that tanh squashes into the open range (−4, 4). A float that saturates to an endpoint is stepped to the next value inside that range. Detector findings stay outside that cap. One or more findings add both activity-cap spans, the surface cap, and the missing-test step once, then log1p of the count, so a smaller file with findings stays ahead of a larger clean file even when that clean file has the stronger activity. Add 1 when the file is production code whose thin-test signal is on after that once-only rule. The queue row stores likelihood. A later place rescore rebuilds it from the file when the key is missing or the stored value cannot contain the current finding step. That read stays inside the repo. A path part containing `..` or `:` is not read. The read uses the same byte cap as the candidate walk. An empty file does not keep a stale line count. A test file does not take that last step. When likelihood is applied, the activity mix (six slopes, trust, and place) is squashed with tanh into the open range (−4, 4) before the add. A saturated endpoint is stepped inside, same as the surface. Omitting likelihood, which the six-weight checks do, leaves the raw mix. A three-line file with a long fix history stays behind a much larger file that also qualifies.

Pass order: append this pass's outcome row from the current `rank-pass.json` entry (copy `findings`, `score`, and the audit attribution there), then rebuild, draw, score every qualifying unopened file, persist the top 50 as the new `rank-pass.json`, and discard the draws as learning inputs. Copying after the rewrite would drop the opened file from the queue and store 0. Place draws cover folders in the scored set, not only the truncated 50.

`bug_hunt.py` rebuilds trust and place attention with the six weights at the start of each pass. The hunt script describes this the same way it describes the six-draw: rebuild, sample, score, discard.

### R10 — Uncertainty-aware exploration and attribution

R9 provides sampled exploration, but a candidate can still be excluded before sampling when it has no qualifying signal or detector finding. R10 adds a bounded exploration layer for uncertainty and coverage without replacing the R5/R6 learned score or turning the hunt into a random walk.

- The exploit score remains the existing R9 `rank_queue_score` result: the six-signal, detector-trust, and place-attention mix plus the existing bug-likelihood term, with R9's existing squashing and endpoint handling. The exploration term is added to that final exploit score after R9 scoring and before sorting. It is added only after candidate qualification and does not change the six-signal mean, trust mean, place mean, or their vote counts.
- Let `E_s`, `E_t`, and `E_p` be the current evidence values for the six-signal, trust, and candidate-folder posteriors. Let `V_f` be the number of prior voted rows for the candidate file and `V_p` the number for its folder. Define `u(E) = min(1, sqrt(20 / max(E, 20)))`, `posterior_uncertainty = (u(E_s) + u(E_t) + u(E_p)) / 3`, `coverage_novelty = (1 / (1 + V_f) + 1 / (1 + V_p)) / 2`, and `exploration_bonus = 0.25 × posterior_uncertainty × coverage_novelty`. The `0.25` value is in native queue-score units and is the maximum exploration bonus for one candidate.
- Exploration is based on uncertainty and coverage, not on a fixed pass number. Repeated evidence reduces the bonus, and an unobserved folder starts with the largest folder novelty. It must not use an epsilon coin, an every-Nth rule, a fixed random quota, or a hard folder rotation.
- Exploration may reorder qualifying production files already in the candidate set. It does not make test files, unreadable files, files over the byte cap, or files with no signal and no detector finding into hunt locations. A user-named file is a direct-inspection override: after validating that its resolved path stays inside the repository and is a supported source file, the pass inspects it even if normal ranking would exclude it, and records its normal signals and outcome.
- Each scored candidate exposes this attribution record:
  `attribution = {attribution_version: 1, mode, six_signal: {recent_fix_commits, thin_test, wiring_hop, dead_setting, reverted, split_stores, total}, detector_trust, place, likelihood, exploration, raw_activity_total, raw_surface_total, exploit_score, final_score, top}`.
  The six per-signal values are the sampled slope multiplied by that signal (with the first signal using its existing `log1p` transform). `raw_activity_total` is the sum of the six-signal, detector-trust, and place components before R9's activity squashing. `raw_surface_total` is the R9 activity result plus the likelihood component. `exploit_score` is the result of `rank_queue_score`; `final_score` equals `exploit_score + exploration`; and `top` lists the named components in descending absolute contribution with a stable name tie-break. Attribution explains the score produced by the model; it is not a causal claim.
- The selected file's rank row persists the attribution needed to audit the decision, alongside `findings` and the pass `score`. Attribution is optional when reading legacy rows; a missing or malformed attribution is treated as absent and never as a vote. An audit copy of a draw may be persisted for reproducibility, but neither the draw nor attribution is a vote. Only the existing outcome and signal rules update learning. New attribution fields must be bounded to the current queue-row size budget and must not make old rank-row readers fail.
- Outcome review compares the selected file's attribution with the observed result and reports calibration errors. R10 does not silently rewrite signal meanings or assign component credit. Any future calibration update requires a separate spec rule and test.
- Attribution uses `attribution_version: 1`; rows without that field are legacy version 0 and remain readable but are ignored for attribution analytics. A malformed or oversized attribution is dropped without dropping the outcome row. The audit writes one bounded JSONL record per selected pass to `.hive/bug-hunt/calibration.jsonl` with file, attribution version, exploit score, exploration, final score, outcome, findings, and a mismatch flag. This audit file does not participate in ranking or learning.
- Exploration is per-repo. It must not borrow candidate coverage, uncertainty, attribution, or posterior evidence from another repository. Donor archives remain limited to the existing slope and trust rules in R9.
- Cold start uses the twenty imaginary votes as the evidence floor, giving every qualifying folder the same maximum initial posterior uncertainty; if only one qualifying candidate exists, it is selected without a bonus decision. If no candidate qualifies, the queue is empty and no exploration row is invented. Ties after the complete score use normalized path order. A seeded run is reproducible: the same repository snapshot, rank rows, and random seed produce the same candidate order and attribution, while a different seed may produce a different order without changing stored means.
- A direct-inspection override carries `requested_file` and an optional `requested_line` outside the learned ranking state. The path is resolved under the repository root, rejects traversal, symlinks that resolve outside the root, missing files, directories, and unsupported file types, and is inspected even when normal qualification would exclude it. A non-positive or out-of-range line is rejected with a structured error before the pass opens. The line is guidance for the review and does not become a separate rank location, signal, vote, or candidate. A direct override still records the file's detector result, normal signals, attribution as `override`, and outcome.

Acceptance requires a fixture containing at least 12 qualifying candidates across at least 3 folders, including separate Python and C# candidate fixtures when both detector paths are available, plus a `ground-truth.json` manifest mapping each candidate path to `bug: true|false`. Across 20 fixed seeds, the hybrid ranker must select an uncertain candidate ahead of a candidate whose exploit-only score is at most 0.25 higher in at least one seed, while a folder with repeated observations loses that exploration advantage. Attribution must reproduce `raw_activity_total`, `raw_surface_total`, and `final_score` within `1e-6`, and `final_score` must equal `exploit_score + exploration` within `1e-6`. Replaying a row with attribution removed or malformed must produce the same next mean. No unqualified file may enter the normal queue, no direct override may escape the repository root, invalid line requests must fail before inspection, and a zero-candidate repository must produce an empty queue without a synthetic row. Compared with exploit-only ranking over the same 20 seeds and manifest labels, hybrid top-10 bug recall (true bug paths selected in the top 10 divided by all true bug paths) may not fall by more than 5 percentage points, and median folder coverage must improve by at least one folder or remain equal without reducing recall. The fixture must verify the Python and C# paths separately when both are available.

### R11 — Empty-result recovery

An `empty` result is evidence about one inspected location, not proof that the repository has no remaining bugs. R11 adds a bounded recovery controller around the existing learned ranker. It may use the R5/R6/R9/R10 posterior state, but it is not a CTM clone or a second neural network; its purpose is to change search direction without creating an unbounded loop.

- When the normal empty threshold is reached and at least one qualifying unopened production location remains, the stop hook enters `recovery` instead of terminating. The existing two-empty threshold remains the trigger; it is no longer sufficient by itself to stop.
- Recovery state is persisted in `.hive/bug-hunt/recovery.json` with `phase`, `attempts`, `empty_streak`, `excluded_locations`, `excluded_folders`, `lenses_used`, `coverage_by_folder`, and `last_empty_confidence`. Missing or malformed recovery state fails closed to a new recovery state and never changes legacy rank rows.
- The recovery-state schema is:
  `{"phase":"idle"|"recovery","attempts":integer 0..3,"empty_streak":integer 0..3,"excluded_locations":[string, max 128],"excluded_folders":[string, max 64],"lenses_used":[allowed lens, max 6],"coverage_by_folder":{normalized folder:string -> integer 0..1, max 64},"last_empty_confidence":finite number 0..1}`.
  Unknown fields are ignored; unknown phase or lens values, non-relative paths, duplicate entries, oversized collections, and non-finite numbers make the state malformed.
- A recovery pass still opens exactly one qualifying location and writes exactly one normal rank row. It excludes the just-inspected empty location and temporarily down-ranks its folder while another qualifying folder remains. It must not manufacture a candidate or reopen the same location solely to satisfy the recovery budget.
- Each recovery pass chooses a review lens not used by the preceding empty passes, in this stable order: `ui-event`, `configuration`, `wiring`, `persistence`, `error-reporting`, `test-contract`. The lens is review guidance and attribution metadata; it is not a seventh learned signal and does not override a direct user request.
- Empty outcomes carry `empty_confidence` in `[0, 1]`. A high-confidence empty search completed the selected lens and its available checks; a low-confidence empty search was blocked by missing context, an unavailable harness, or an incomplete inspection. Empty-row negative learning is multiplied by this confidence. Legacy rows without the field retain confidence `1.0`.
- A committed, skipped, or review-failed outcome exits recovery, clears temporary exclusions, and resets the empty streak. A recovery empty increments `attempts`. The default recovery limit is three consecutive recovery-empty passes; reaching it stops the hunt with `active: false`.
- Recovery also stops immediately when no qualifying unopened production location remains, when the committed-fix ceiling is reached, or when recovery state cannot be written safely. It never pushes, invents bugs, or commits a recovery marker as product code.
- Recovery exploration is bounded and cannot override R10's maximum bonus. Its only additional preference is coverage of qualifying folders and unused lenses; repeated empty evidence reduces the chance of returning to the same branch. If all lenses have been used, selection cycles from the beginning only when a qualifying folder remains that has not been covered in the current recovery phase; otherwise recovery stops.
- `empty_confidence` is a finite number clamped to `[0, 1]`, defaults to `1.0` for legacy rows, and is written on every `empty` rank row. A missing, malformed, or non-finite value fails closed to `1.0` for compatibility. The confidence multiplier applies only to the negative location, trust, and place updates for that empty row; it does not change the stop counters.
- The recovery controller increments `empty_streak` and `attempts` only after the normal rank row is durably appended. A committed, skipped, or review-failed row clears `recovery.json`; a crash before the row is appended leaves the prior state unchanged. A new hunt with no active recovery starts with an empty exclusion set and does not inherit temporary exclusions from an earlier hunt.
- Metadata handoff is ordered: the pass writes its selected file, scenario, outcome, confidence, and lens into `rank-pass.json`; the stop hook appends the normal rank row from that entry; only after the append succeeds does it atomically update `recovery.json` and write the next `continue.json`. Queue rewriting happens after the rank-row append and never discards the selected metadata.
- `recovery.json` is the sole source of truth for recovery phase and attempts. `continue.json` retains its existing control fields (`active`, `pause_seconds`, `ceiling`, `committed`, and `consecutive_empty`) and may expose a bounded `recovery_phase` diagnostic, but the hook never resumes or stops recovery from that diagnostic alone.
- Temporary location exclusions last only for the current recovery phase, are keyed by normalized repository-relative path, and are removed when recovery resets or stops. Folder exclusions are preferences, not hard filters: a qualifying file may be selected from an excluded folder only after no unexcluded qualifying folder remains.
- The hook validates `recovery.json` atomically before writing `continue.json`. If the state cannot be parsed, validated, or replaced, it records a structured recovery-state error, writes `active: false`, and does not claim that another pass was scheduled.
- A saved recovery branch is audit state, not learning state. The next posterior rebuild reads only the normal outcome, signals, findings, score, and confidence-weighted empty vote. It never learns from the lens, exclusion, coverage, or exploration draw. Lens metadata is bounded to the six allowed names and is ignored if malformed.

R11 is a finite-state recovery controller around the existing posterior learner. The current Thompson sampler and a deterministic state machine are sufficient; a separate neural model is not required for correctness and would make empty-result attribution harder to audit.

## Memory and recall

This repo's prediction memory is `docs/specs/bug-hunt/TEMP-prediction-memory.md`. It is not applied to `AGENTS.md`. The writer and the recall script run for any composer tab in this repo, including a tab with no stored name and a subagent. They are not limited to the tab named `PREDICTION_BUG_HUNT`. A composer in another workspace is not written. The writer reinserts that any-tab scope line into the memory file. This section is the requirement.

### R7 — Recall

`.cursor/hooks.json` runs `.cursor/hooks/prediction_memory_recall.py` first on `sessionStart`, then the Hive session-start hook. `beforeSubmitPrompt` runs only the recall script. Both pass `--memory docs/specs/bug-hunt/TEMP-prediction-memory.md`.

`sessionStart`, and any submitted prompt that does not open with a recall phrase, return the memory file and do not read a chat transcript. A blank or missing file adds no context.

A recall phrase must start the line. The phrases are: hey, refresh your memory; hey refresh your memory; refresh your memory; hey do you recall; do you remember; can you recall; please recall; refresh memory; total recall; do you recall; full recall; and recall. A spoken quote starts a subject search only when it follows "the user said" or "the user asked" and that quote itself starts with a phrase. A later bare mention does not start a search. A bare phrase returns the file. A phrase with a subject searches that subject: 24 simulations, depth 2, 4 branches, then 16 Thompson draws. The draw uses each branch's own match, not the tree's backed-up reward. The chat transcript is read only when those passages do not cover the subject. Memory wins on a conflict.

The recall cap is 32,000 characters. Cursor may inline the first 10,000 and put the rest in a side file.

### Memory file lookup

When the hook does not pass `--memory`, an existing `PREDICTION_MEMORY` file is used. A `~` path is expanded. A missing value is ignored. Otherwise the script walks upward for `prediction-memory.md` and stops at a `.git` directory. Its own directory counts only when that directory sits inside the working directory's project. The live hooks pass `--memory`, so that walk is not the live path.

A blank or missing file, a file larger than 2,000,000 bytes, or a file that is not UTF-8 adds no context.

### R8 — Hang-up capture

`.cursor/hooks/prediction_bug_hunt_call_end.py` runs on `sessionEnd` and is the first `stop` hook. `sessionEnd` writes for any status. A `stop` writes when status is completed, aborted, error, cancelled, or canceled. A `stop` with no status does not write. A completed `stop` is what a hang-up delivers, and it is also what an ordinary finished agent turn delivers.

The write covers any composer tab in this repo, including a tab with no stored name and a subagent. It reads user turns from `glass.realtimeVoice.callTurns` in Cursor's `state.vscdb` for that composer. It does not read `agent-transcripts`. Assistant turns are dropped. The last 20 unique user lines are kept, each cut at 240 characters. They replace the block between `<!-- call-end-capture:start -->` and `<!-- call-end-capture:end -->`. They are not appended. Text outside that block is kept.

The capture temp file is created beside the memory file, then moved onto it, so the replace stays on the same drive. The lock file stays in the system temp directory.

## Out of scope

Running the hunt inside Hive planner, auto-commit of product code, and remote upload.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: One start phrase runs exactly 1 inference pass in that turn. The pass opens 1 location and appends 1 row to `.hive/bug-hunt/rank-rows.jsonl`.
- **SC-002**: The hunt stops at 50 committed fixes by default, after R11 recovery is exhausted, or when no unopened location still qualifies. Two consecutive empty outcomes enter recovery when a qualifying unopened production location remains. A `committed`, `skipped`, or `review-failed` outcome resets the empty-search count and recovery state.
- **SC-003**: A blank pause waits 10 seconds. A pause of 0 does not wait. `--iterations` outside 1 through 200 is refused.
- **SC-004**: Each pass rebuilds the 6 weights from that repo's rank rows, draws 1 Thompson sample of those weights, mixes it with the R9 attention draws, adds the bounded R10 exploration bonus, opens the highest unopened score, and discards every draw as a learning input. An optional audit copy does not affect the next rebuild. The next pass rebuilds again. The hunt script does not fit a logistic regression after 30 rows.
- **SC-005**: One new vote on a posterior moves that posterior by about one third of the vote's credit. The seed stays the offset. A `skipped` row moves every posterior by 0. A findings-zero row moves trust by 0. A vote in one folder moves other folders by 0. A non-negative seed is not taken below 0.
- **SC-006**: A passing review commits locally and does not push. A failed review that is not a secret or a product decision restores that iteration's uncommitted edits and records `review-failed`.
- **SC-007**: Detector trust and place attention rebuild from the same voted rows as the six weights. Empty rows on finding files lower later trust relative to the seed. Empty rows in one folder do not take that folder's attention below 0. A committed row in another folder can raise that folder above 0. Rank rows persist `findings` and that pass's mix `score`. No pass index or epsilon coin decides the next file.
- **SC-008**: R10 adds at most `0.25` native score units after the R9 exploit score. Its attribution components reproduce `raw_activity_total`, `raw_surface_total`, and `final_score` within `1e-6`, and malformed or absent attribution cannot change the next posterior mean. A direct override validates repository containment, supported source type, and optional line guidance before inspection.
- **SC-009**: After two consecutive empty outcomes with qualifying unopened locations remaining, recovery opens a different location. It prefers a different qualifying folder when one exists and uses a lens not used by the preceding empty passes; if only the same folder remains, a different file there is valid. Recovery stops after three consecutive recovery-empty passes, the ceiling, no qualifying location, or a validated state-write failure. A committed, skipped, or review-failed outcome resets recovery. Empty learning is scaled by persisted confidence, and legacy rows remain readable.

## Assumptions

- The hunt runs in Cursor chat on one repo. It does not run inside the Hive Planner process, and it does not push or upload.
- Each repo learns only from its own `.hive/bug-hunt/rank-rows.jsonl`. Repos do not share a posterior. A row has no timestamp, so decay follows row order.
- Ranking mixes six-signal, detector-trust, and place-attention draws, then adds the bounded R10 exploration bonus after the R9 exploit score. Draws are discarded as learning inputs, although an audit copy may be persisted. Jsonl persists `findings`, `score`, and optional bounded attribution. There is no findings-present bonus and no three-commit folder rotation.
- The seed 0.7118, 3.3024, 1.0245, -0.1424, 0.0, and 0.0 is the start of each rebuild. 0.884 is the fitted median AUC of the 3:25 AM check, and 0.946 is the inflated file-order figure, not a seed. The first weight multiplies log1p of the fix-commit count. The other five multiply the raw signals. Those slopes do not stay fixed once rank rows exist.
- A skipped row is logged and casts no vote. `committed` and `review-failed` pull toward that file's signals. `empty` pulls away. The same vote sign updates detector trust when the file had a finding, and updates place attention for that file's folder.
- Exploration includes R9 posterior sampling and the R10 bounded uncertainty/coverage bonus. It is not an epsilon, an every-Nth step, or a fixed findings bonus. Findings are not a seventh six-signal weight.
- Empty-result recovery is a bounded controller around the existing learner, not a CTM clone or a second neural network. Recovery state and lenses are audit metadata; only confidence-scaled normal outcomes update learning.
- The scenario classifier may use 0.65 and 0.35 on P(real bug) only after 30 completed rows, and it must not override a confirmed bug or a record-and-skip secret, product decision, or missing harness. That classifier is not the ranker. The ranker does not switch to a logistic regression after 30 rows.
- A blank pause is 10 seconds. The default ceiling is 50 committed fixes. `--iterations` accepts 1 through 200. `0` pause does not wait.
- The stop hook is `py -3.11 .cursor/hooks/bug_hunt_continue.py`. Active false at the start of a pass means the previous continue token was used.

## Continual learning beyond the residual (outline, not the live rebuild)

The live rebuild stays the seed offset plus a decayed residual. This section is the production shape on top of that, and the hook runs it.

Three memories, not one average:

- **Fast window.** The counter is per repo and survives hunts. A hunt's fix ceiling of 50 is not the window. A voted cycle is one appended row whose outcome is `committed`, `review-failed`, or `empty`. `skipped`, `stopped`, and any other outcome do not count. The hook stamps `window` with the open id on that row as it appends. The open id and the count live in `slope-windows.json` under `open`. The count is the number of voted rows in `rank-rows.jsonl` that carry that id. After a crash the hook recounts those rows. It does not trust a stale number in `open` over the log.
- **Window close.** When a recount reaches 200 and `closed` has no record for that id, append one record: the id, cycle count 200, the six slopes, and trust. The record stores the fast mean from before the shrink. It has no place map. Then write `.hive/bug-hunt/place-local.json` with the current place map, reset slopes to the seed and trust to 1.0, and reload place from that file. The reset does not clear `continue.json`, the opened set, the empty-search count, or the commit ceiling. The next open id starts at count 0. Rows stamped with a closed id are not votes.
- **Slow archive.** `slope-windows.json` is append-only for `closed` and is the long-term memory. A window that already has a closed record opens on the last-five blend, and residual votes add on top of that blend. The blend is the last five closed windows, weights 1, 1/2, 1/4, 1/8, 1/16, divided by the sum of the weights that exist. One window blends as itself. There is no pull back toward the original seed. The place file is the map for the window id it stores. A place file with no matching id is rebuilt, so an earlier folder at 0 does not freeze the next close.

**Donor precedence.** Donors apply only when this repo has no closed window. The list is `.hive/bug-hunt/donors.json`, a JSON object whose `donors` array is ordered. Each entry is a repo root or a direct path to `slope-windows.json`. Relative entries resolve from this repo root and may point outside it. The first entry that resolves to an archive with at least one valid closed window is the donor. Later entries are fallbacks, not a blend. A path that resolves to this repo's own archive is skipped. A record that is non-finite, below the floor, or whose cycle count is not 200 is skipped. The chosen donor then uses its own last-five blend, with no pull back to the original seed, on slopes and trust only. No donor list means no borrowing. The hook does not invent sibling repos.

**What is committed.** The hook is the only committer of the archive. When a window closes it makes one local commit whose only file is `slope-windows.json`. It does not push, and it does not stage the fix, `place-local.json`, or `donors.json`. The app's isolated fix commit does not stage the archive. If that archive commit fails, the file stays on disk and a later close retries. A donor reads a committed archive, not a dirty working tree. A repo with no git keeps the file and skips the commit. `place-local.json` and `donors.json` are gitignored. Install adds those two ignore lines and does not delete `slope-windows.json`. The app writes `donors.json` if it wants a donor. The app still opens `rank-pass.json` and does not read the archive to choose a file. The prompt says rows in the open window are votes, and rows stamped with a closed window id are not. The scenario classifier still counts every completed row in the log.

A `skipped` or `stopped` row is not stamped and is not counted. A stamped row whose outcome is not a vote is not counted. The first window, with no closed record, opens on the original seed. The hook writes `slope-windows.json` and `place-local.json`, and it commits the archive when a window reaches 200.

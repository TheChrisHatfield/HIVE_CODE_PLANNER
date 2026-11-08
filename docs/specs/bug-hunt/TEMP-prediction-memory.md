# Temporary prediction memory

Captured 2026-11-02 from this workspace's transcripts. Not applied to `AGENTS.md`.
Continual-memory shape: plain `- ` bullets, `## Learned User Preferences` for user working style, `## Durable Workspace Facts` for operational facts (`# operational`), and a separate behavioral section because product rules must not be written into `AGENTS.md`. Hive routes those to the active spec. A bullet stays at or under 240 characters. No evidence tags.

The plugin reads new or newer transcript files, writes candidates to `docs/proposals/cl-candidates.md` with `# operational` or `# behavioral`, then `agents-propose --apply` accepts short operational bullets into `## Durable Workspace Facts` (cap 12) and routes behavioral bullets to the spec. Untagged ambiguous bullets can be Thompson-sampled. `## Learned Workspace Facts` is legacy and merges into Durable Workspace Facts.

Transcript search: the design lives in chat `b997d166`. Call `call-d4a8f4a5` is stored in Cursor's `state.vscdb` under `glass.realtimeVoice.callTurns`. It is not in the agent transcript. Other Hive chats do not contain this ranker.

## Learned User Preferences

- Lookup and transcript search do not change files. Say so when the task is lookup only.
- Spec edits stay in the existing voice. Do not drop R5. Do not rewrite rules outside the requested ranking text.
- Do not modify original repos on D, E, F, or H when scanning. Copies go only to a new folder the user names.
- Diagrams for this design should be monochrome and printable, with short labels.
- Drive Downloads on D, E, F, and H is the beacon for moved repos. The Bluetooth repo is spelled `BLUETTOOTH_SURROUND`.
- Ad hoc, not permanent. Scope is any composer tab in this repo, not only `PREDICTION_BUG_HUNT`. A call in this repo, including an automatic drop, updates `docs/specs/bug-hunt/TEMP-prediction-memory.md`.

## Durable Workspace Facts

- Bug-hunt ranking is prompt text from `render_agent_prompt` in `src/hive_planner/bug_hunt.py`. Python stores `INITIAL_SLOPES` and does not fit them during a hunt. # operational
- Installed script still says weighted sum until 30 rows, then logistic regression. The sum starts at `INITIAL_SLOPES`. Tests still assert those strings. # operational
- `.hive/bug-hunt/rank-rows.jsonl` is append-only. Python never prunes, truncates, or rotates it. A row is written after the outcome. # operational
- This repo's rank file had 389 rows: 302 bugs, 84 empty, 3 skipped, 7 list-shaped signal rows that must be coerced. # operational
- Hand weights 3, 5, 5, 4, 4, 4 scored AUC 0.387. The top fifth of that score held about 15 percent of the bugs. # operational
- A later-row refit on log1p(fix commits) reached AUC 0.674. Full-file slopes wanted fix-commit churn negative and thin-test dominant. # operational
- Sandbox is `scripts/sandbox_rank_weights.py`. It does not import `bug_hunt`. Run `py -3.11 scripts/sandbox_rank_weights.py`. # operational
- Synthetic recovery of a known six-vector first stayed inside cosine 0.95 on 80 percent of trials at n=400. At n=100 only about 48 percent did. # operational
- On an inverted synthetic process, a 30-row linear refit beat the hand weights in 40 of 40 trials (median AUC about 0.80). # operational
- `continue.json` was inactive: 14 committed, 2 empty searches, ceiling 50. A new hunt's opened set starts empty. # operational
- Spec text is `docs/specs/bug-hunt/spec.md`. The printable loop is `docs/specs/bug-hunt/prediction-system-diagram.md`. # operational
- Session legend and transcript cartridge: `docs/specs/bug-hunt/rolling-cartridge.md`. # operational
- COLEMAN, the public Thompson-sampling test ranker, is a shallow clone at `H:\DRIVE_DOWNLOADS\BUGHUNT_RANKING_REFERENCES\coleman`. # operational
- Local archive copies are under `H:\DRIVE_DOWNLOADS\BUGHUNT_PREDICTION_LOCAL_MATCHES`. Robocopy exit 1 meant files copied. Failed count was 0. # operational
- Bluetooth surround is `E:\DRIVE_DOWNLOADS\BLUETTOOTH_SURROUND` (two T's). It runs dual Thompson bandits for speech and bandwidth. # operational
- Pineapple, Facebook predictive test selection, and Microsoft's test selector match the idea but have no public repository. # operational
- Hive continual memory writes operational bullets only under `## Durable Workspace Facts`, max 12, each at most 240 characters, tagged `# operational`. # operational
- Behavioral bullets are tagged `# behavioral` and routed to `docs/specs/<feature>/spec.md`, not into `AGENTS.md`. # operational
- Call-end hook is `.cursor/hooks/prediction_bug_hunt_call_end.py`, wired on sessionEnd and stop in this repo only. Not installed by bootstrap. # operational
- It writes on sessionEnd, and on stop when status is completed, aborted, error, or cancelled. A completed stop is the hang-up Cursor sends. # operational
- This design chat is composer `b997d166-609a-4a86-a9e5-5b2bf07e325d`, tab `PREDICTION_BUG_HUNT`, folder `d:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`. Any other tab in this repo uses the same hook. # operational
- Voice capture reads `glass.realtimeVoice.callTurns` in Cursor `state.vscdb` for that composer. It does not read `agent-transcripts`. # operational
- Tab routing reads the composer id and its stored name from Cursor state for this workspace. A new tab is recognized. Another workspace is ignored. # operational
- Header lookup uses the read-only `cursor_chat_delivery` helpers. The PREDICTION_BUG_HUNT-only name check has been removed. # operational
- Recall phrases must start the spoken line: hey refresh your memory, do you remember, do you recall, total recall, and recall, plus the other phrases in `START_RECALL_PHRASES`. # operational
- Voice labels said, asked, told, mentioned, replied, and stated are the same spoken-line kind, including "the user asked." Blank or punctuation-only quotes are skipped. # operational
- Monte Carlo recall is `.cursor/hooks/prediction_memory_recall.py`. A subject question uses a capped tree (24 sims, depth 2, 4 branches) and a Thompson draw. A bare trigger returns the file, fitted to the context limit. # operational
- Second review: ids with `..` or a slash are rejected. Truncated duplicate bullets collapse. The write is locked. # operational
- Final review: a transcript folder that resolves outside the project is ignored. A capture block missing its end marker still writes. The capture temp file sits beside the markdown. The lock stays in the system temp directory. # operational
- Recall and call-end tests are `tests/test_prediction_memory_recall.py` and `tests/test_prediction_call_end.py`. # operational

## Design memory (behavioral — do not merge into AGENTS.md)

- One shared six-weight vector ranks files. Signals, in order: fix-commit churn, thin or failing test, unwired hop, unread flag, reverted commit, two stores for one fact. # behavioral
- The score is one linear layer. No hidden layer. Continual backpropagation is the mean rebuild, not a second gradient step on the drawn vector. # behavioral
- Seed is 0.7118, 3.3024, 1.0245, -0.1424, 0, 0. First weight is log1p of fix commits. It starts with 20 imaginary votes. Those votes halve every 40 voted rows and are not re-added at full strength. # behavioral
- A skipped row casts no vote. The seed stays an offset. One new voted row moves a slope by about a third of its credit. A non-negative seed is not taken below 0. # behavioral
- `committed` and `review-failed` pull toward that file's signals. `empty` pulls away. This vote sign is not reconciled with "only committed is positive." # behavioral
- Real-row decay is 0.9 by row order, not by clock. Newest voted row counts as 1. Remembered real votes cap near 10, so the mean tracks recent outcomes. # behavioral
- Each pass draws one weight per signal around the rebuilt mean, scores unopened files, opens the highest, then discards the draw. Line churn breaks ties. # behavioral
- System 2 is the stored mean update. System 1 is the fast Thompson draw, used once and thrown away. The draw is not an input to the next rebuild. # behavioral
- About 400 rows from one stable process is when a six-weight recovery is trustworthy. It is not a swap, not a freeze, and not a hunt stop. # behavioral
- The old fixed sum and the 30-row logistic gate for ranking are superseded. The scenario classifier's own 30-row 0.65/0.35 gate is unchanged. # behavioral
- Each repo learns only from its own `.hive/bug-hunt/rank-rows.jsonl`. Repos do not share a posterior. The seed is the shared start. # behavioral
- A bell-curve draw and a Beta-on-shares draw were both named and never reconciled. The first signal is log1p of the fix-commit count. The other five stay raw. # behavioral
- Real rank rows are files the hunt already opened, so they are not one stable generative process. The 400-row trust line assumes that they are. # behavioral
- Hand weights rank worse than chance on this file. A permanent 20-vote anchor would have kept the mean within about one third of that stale seed. # behavioral
- Hunt stops still apply: committed-fix ceiling, two empty searches, or no qualifying unopened file. Unopened files are not empty searches. # behavioral
- COLEMAN is the closest public system: volatile combinatorial bandits, including Thompson sampling, for CI test order. It is test ranking, not file ranking. # behavioral
- Ericsson Pineapple ranks code-review requests with a Bayesian network. It was deployed. It is not Thompson sampling and has no public code. # behavioral
- No shipped tool found in the search ranks source files for a bug hunt with continual linear updates plus a discarded Thompson draw. # behavioral

## Detector training (603-row blend)

- Starting slopes are `INITIAL_SLOPES`: 0.7118, 3.3024, 1.0245, -0.1424, 0, 0. First multiplies log1p of the fix-commit count. A later fit starts there, not at 3, 5, 5, 4, 4, 4. # behavioral
- File-order 0.946 was inflated by 75 all-zero blanks. The linear ceiling on twenty stratified splits is about 0.88. Six-signal fitted median is 0.884. # behavioral
- Seven-signal linear median is 0.882. The small ReLU net is 0.884 on six signals and 0.887 on seven. Neither climbs back toward 0.946. # behavioral
- GAN thin-test plus wiring-hop files score 4.168 fitted on the frozen 0.946 slopes. Rounds that stayed on that pattern, including 4 and 6, hit 4.168 on all eight. # behavioral
- Diversified families, file-order on the restored 603 blend: 16 files fitted 0.907, and 8 files fitted 0.924. # behavioral
- Adding the highest thin-plus-wiring file one at a time drops fitted AUC at file one, from 0.946 to 0.934. Eight of those files end at 0.856. # behavioral
- Weak-file batch: the best single file scores 3.19 and the blend fitted AUC is 0.943. Eight weak files end at 0.923. None holds 0.946. # behavioral
- The 909-row mix (398 bugs, 311 hard negatives, 200 blanks) has fitted median 0.810 on the same twenty splits. # behavioral
- `flagged_line_fix` lights 94 of 603 rows: 75 bugs and 19 clean. Correlation with the file-level fix count is 0.50, and with the bug label is 0.08. # behavioral
- The system learns from new labeled rows over time. The baseline is about 0.88, not the file-order 0.946. New hunts start from the installed slopes. # behavioral

<!-- call-end-capture:start -->
## Call-end capture

Ad hoc log for any composer tab in this repo. Do not merge into `AGENTS.md`.

- Last capture composer `b8bb10b2-232a-4a78-ad3f-9570b95ba7f2` from `glass.realtimeVoice.callTurns/b8bb10b2-232a-4a78-ad3f-9570b95ba7f2/call-62be081b-e7c3-4a96-a4da-f90d718a4bb5`. Written when that call ends, including an automatic drop. #…
- So, okay so the, the fixed slope gives it a, basically gives it a ground truth to always maintain stability, and then the, the memory gives it a, is a flexible adaptivity, and the Thompson sampling gives it exploration versus exploitatio…
- Yeah but it is a, it is a feed, it, it's not, it's an, it's an emergent feedback system. 'Cause it, literally it is a feedback system. It's just not coded at, it's the, it's not coded as a feedback system, but if you look at the mechanis…
- So it's almost like system one and system, system two. One is like the, the, the, the, um, the weight slope is system two 'cause it's a slow learner, and you can consider system one combination between Thompson sampling or a derivation o…
- So, s, for the, so basically the, how does the memory system, the memory, how does the memory system work?
- Well you can, you have the information there. You can figure it out.
- Go into it and figure it out. You got it. You know what you're doing.
- So what is, so explain it, explain that in lay terms.
- And how does this relate to Thompson sampling?
- And how does the, the, the weight slopes work?
- But shouldn't they be, at certain intervals, shouldn't they be reinjected to, to, to rebalance out the system?
- Is this a unique system, or does, it's just mirroring something that already exists?
- So what are some of the emergent properties that can come out of this system?
- What, what does that mean in terms of, in lay terms?
- So what is this, okay for a system like this running in that type of loop? I'm trying to fi, wrap my brain around it. What does it mean in terms of hunting for bugs? Like, how can this system evolve in, in terms of what it, can it develo…
- Please speak in plain language.
- You don't have to use analogies. You can just speak concisely without using a whole lot of jargon.
- So what are some of the emergent, some of the emergent things that can happen over time?
- So, what does that mean?
- But doesn't the exploitation, like
- So how can we, how can we, how can we engineer it so that it, it has that, that ability to determine, okay here's an area, cause that's important in terms of looking for bugs.
<!-- call-end-capture:end -->

# Voice_Bot — two-pass code review handoff (2026-11-13)

**Purpose:** Continue **pass 2** (review + validate + close) in a **new Cursor chat** after pass 1 landed fixes in this repo.

**Repo:** `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`  
**Python:** `py -3.11`  
**Active feature:** Voice_Bot — load `docs/specs/Voice_Bot/spec.md`, `tasks.md`, `docs/planning-rosetta-stone.md` (`planning.rosetta`).

## What pass 1 did (this chat)

| Issue | Fix |
|-------|-----|
| Windows `Path.resolve()` truncates at NUL → `src/app.py\x00.txt` bound as `src/app.py` | Reject `\x00` in `_resolve_file`, ACP `fs/read`, and `_resolve_write_target` |
| R22 stale check used `dirty is live_dirty` | Value compare: `bool(dirty) == bool(live_dirty)` in `voice_task.submit` and `buffers_match` |
| ACP `fs/read` called `read_bytes()` then sliced | Stream read at most `cap_bytes` (R21) |
| Extension live feed dropped files like `..notes.md` | New `liveFeedRelative` in `core.js` (same fence as `isInsideWorkspace`) |
| `stopBridge()` left `sessionRoot` set | Clear `sessionRoot` on stop (not only on child exit) |
| Bridge drop during submit/spoken/call control → unhandled rejection | try/catch with user-facing error in `extension.js` |

### Files touched (pass 1)

- `src/hive_planner/voice_task.py` — path NUL guard, stale dirty compare, write path NUL guard  
- `src/hive_planner/voice_bot.py` — `buffers_match`, bounded `fs/read`, read NUL guard  
- `extensions/hive-voice-bot/src/core.js` — `liveFeedRelative` + export  
- `extensions/hive-voice-bot/src/extension.js` — live feed, stopBridge, try/catch on HTTP calls  
- `tests/test_voice_bot_code_review_2026_11_13.py` — **new**, 9 tests  
- `extensions/hive-voice-bot/test/code-review-2026-11-13.test.js` — **new**, 6 tests  

### Validation already run (pass 1)

```text
py -3.11 -m pytest tests/test_voice_bot_code_review_2026_11_13.py -q  → 9 passed
py -3.11 -m pytest tests -k "voice or acp" -q                        → 523 passed, 2 skipped
node --test extensions/hive-voice-bot/test/code-review-2026-11-13.test.js → 6 passed
extensions/hive-voice-bot npm test                                   → 62 passed (does NOT yet include code-review-2026-11-13.test.js)
py -3.11 -m hive_planner spec-drift-check --feature Voice_Bot        → specseed diverges (needs emit)
```

## Pass 2 checklist (new chat)

Do in order; one coherent close-out, not a full nn-cascade unless new bugs appear.

1. **Wire extension regression** — Add `test/code-review-2026-11-13.test.js` to `extensions/hive-voice-bot/package.json` `"test"` script; rerun `npm test` (expect 68 pass).
2. **Spec drift** — `py -3.11 -m hive_planner emit --feature Voice_Bot --force-delta` then `spec-drift-check --feature Voice_Bot` until `ok=true`, no spec_actions.
3. **Pass 2 code hunt** (confirm no regressions; fix only if found):
   - `voice_bridge.validate_tool_args` `relpath` for `wav_path`: confirm `..` / absolute paths cannot reach `submit_spoken` (bridge vs runner `_resolve_file`).
   - `followTask` in `extension.js`: interval cleared on all exit paths; no leak after bridge stop.
   - Re-read pass 1 diffs against R22, R23, R6 in `docs/specs/Voice_Bot/spec.md`.
4. **Impact packet** (if any further code changes): `docs/change-impact/impact-packets/2026-11-13-voice-bot-two-pass-review.md`.
5. **tasks.md** — Append validation log row for this two-pass review (fixes + test commands). Do not flip open checkboxes unless behavior spec requires it.
6. **Wiring audit** (required before “done”):
   - Chain: editor snapshot → bridge submit → runner stale/NUL path → ACP prompt.
   - Chain: approval poll → `liveFeedRelative` → `POST /v1/live` → write approve stale check.
   - Prove: pytest new file + full `voice or acp` + npm test.

## Do not redo (unless you change those files)

- Full historical Voice_Bot gap cascades in `tasks.md` validation log  
- Live G2/G6/R35 host runs  
- `edits_enabled` / R33 latch changes  

## Paste into new chat

Copy the block below as the **first user message** in the new session (or say: *continue Voice_Bot two-pass code review pass 2 using `docs/specs/Voice_Bot/two-pass-code-review-handoff.md`*).

```
CONTINUE Voice_Bot (two-pass code review — pass 2)

Last chat: 2026-11-13 (pass 1 complete)
Budget left: fresh chat
Verdict: read-only=READY (523 voice/acp pytest) full-agent=unchanged (R33 per-host)

Done pass 1:
- NUL path guard (Windows resolve truncation) on runner resolve + ACP fs/read + fs/write resolve
- R22 stale: bool(dirty) value compare in submit + buffers_match
- ACP fs/read capped stream read (R21)
- Extension: liveFeedRelative (..notes.md), stopBridge clears sessionRoot, try/catch on bridge HTTP calls
- Tests: tests/test_voice_bot_code_review_2026_11_13.py (9/9); extensions/.../code-review-2026-11-13.test.js (6/6 standalone)

Open next (pass 2 only):
1) Add code-review-2026-11-13.test.js to extension npm test script; npm test
2) emit --feature Voice_Bot --force-delta; spec-drift-check --feature Voice_Bot
3) Short second-pass hunt (bridge wav_path, followTask intervals); fix if needed
4) Impact packet + tasks.md validation log + wiring audit summary

Do not redo: pytest tests -k "voice or acp" unless pass 2 edits touch src/ or extensions/
Files to read first: docs/specs/Voice_Bot/two-pass-code-review-handoff.md, pass 1 files listed there
Blocked: none (specseed drift is procedural, not environmental)

First action: Read two-pass-code-review-handoff.md; wire npm test; run npm test + spec-drift emit + spec-drift-check.
```

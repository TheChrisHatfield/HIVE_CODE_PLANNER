# Voice_Bot — handoff after STT clip-4, pod terminate, T042 slice 5e (2026-11-14, session 11)

**Purpose:** Continue **Voice_Bot** after operator **terminated** pod `t13xqwp4ilb953`, **T056-live-clip-4** evidence, and **T042 slice 5e** (minimal typed-task greeting sync) in code + tests.

**Supersedes:** `docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session10.md` for **pod billing, open micro-tasks, and launcher slice 5e** only. Session 9/10 stack and STT clip details remain authoritative where not updated here.

**Repo:** `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`  
**Python (this host):** `py -3.11`  
**Active feature:** Voice_Bot

## Verdict

| Lane | Verdict |
|------|---------|
| read-only typed preview | READY |
| full-agent production | NOT READY |
| **G7 Moshi harness (T055)** | **pass** (recorded; old pod URL) |
| **G7-q8** | **pass (caveated)** (`evidence-register.md`; session 9 pod deltas in `deployment-gaps.md`) |
| **T056 live Moshi talk** | **open** (needs new GPU stack; no account pods) |
| **T056 STT clips (pinned Whisper)** | **partial** — rows `T056-live-clip` … **-4** in register; no WER on any clip |
| **T042 slice 5e (greeting / task sync)** | **code done; tasks.md not closed** — typed submit only; see validation below |

## Done session 11 (this chat)

1. **STT evidence:** `T056-live-clip-4` for `clip-20261114-194025-466141.wav` — near-silent (peak 688); transcript likely Whisper filler; partial row in `evidence-register.md`.
2. **Pod:** operator **terminated** `t13xqwp4ilb953`. Re-read: `get-pod` → 404; `list-pods` → **none**; disk no longer bills. Pod-only `*.orig`, `warm_ws.log`, log tails **not** recovered (see session 10 backup).
3. **T042 slice 5e (minimal, poll):** after `submit_typed` success with `task_id` + `context_snapshot_id`, controller polls `GET /v1/task` every 2 s; greeting shows `Working on it...` or `Waiting for your approval...` until terminal state, bridge error, hang-up (`on_end`), or 10 min cap. Panel reads `task_text()` on animation tick; listening wins over task label.
4. **Tests:** `tests/test_voice_panel_task_watch.py` — **15 passed** alone. `tests/test_voice_panel_controller.py` (56) and `tests/test_voice_panel.py` (33) pass **separately**. Combined run **104 passed** only when `test_moshi_call_runs_real_talk_over_loopback_echo_server` is deselected (`-k "not loopback_echo"`); with that test included, Windows **fatal exception 0x80000003** (pre-existing interaction; bisect inconclusive — panel sources untracked in git).

## RunPod (re-read every chat)

| Field | Value |
|-------|-------|
| Account pods | **none** (`list-pods` empty) |
| Former pod | **`t13xqwp4ilb953`** — **TERMINATED** (do not `get-pod` expect live) |
| New live Moshi | **new pod** per `cursor-g7-runpod-handoff.md` + local backups |

## Local backup (unchanged)

| Asset | Path |
|-------|------|
| Session 9 pod artifacts (partial) | `D:\DRIVE_DOWNLOADS\POD_BACKUPS\t13xqwp4ilb953-session9\` |
| q8 weights + tokenizer | `D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8\` |
| STT clips | `.hive/voice-bot/recordings/` — clips `194246`, `194802`, `195013`, `194025` + `.transcript.txt` |

## Do not redo

- Register rows **T056-live-clip** … **-4** or re-transcribe clips **194246**, **194802**, **195013**, **194025** unless user asks.
- G7-q8 row rewrite; G7 `moshi-probe --record` on dead pod URLs.
- Pod lifecycle on `t13xqwp4ilb953` (gone).
- Re-implement 5e core (watcher + `task_text` + panel `_sync_task_text`) unless user requests changes.

## Open micro-tasks (priority — pick one per chat)

### A. Close slice 5e in docs + validation

1. Add **T042 slice 5e status** bullet to `docs/specs/Voice_Bot/tasks.md` (wiring + test counts; **do not** check parent T042 — live mic still open).
2. Optional: extend greeting sync to **spoken submit** / Moshi utterance path when bridge returns `task_id` + `context_snapshot_id`.
3. Optional: bisect or isolate `test_moshi_call_runs_real_talk_over_loopback_echo_server` on combined Windows pytest runs.

### B. Live Moshi (operator billing)

New Runpod pod + stack from handoff/backups. Target: `moshi-talk` with **`utterances > 0`** on a real server (deferred by operator this session).

### C. T042 remainder (no pod)

Live mic / G3; launcher slices beyond 5e; Path A preview ship items in `tasks.md` § T042.

## Slice 5e chain (for wiring audit)

`app.py` `VoicePanel(..., task_text=voice_controller.task_text)` → `VoicePanelController.submit_typed` → `_start_task_watch` → `_get_from_bridge("/v1/task", {task_id, context_snapshot_id})` → `_task_label` → `VoicePanel._sync_task_text` → `_greeting.configure`. **Gap:** `/v1/submit/spoken` and Moshi utterance submit do not start the watcher yet.

## Files touched session 11

- `docs/specs/Voice_Bot/evidence-register.md` (`T056-live-clip-4`)
- `docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session10.md` (pod status → TERMINATED note)
- `src/hive_planner/launcher/voice_panel_controller.py` (5e watcher)
- `src/hive_planner/launcher/voice_panel.py` (`task_text`, `_sync_task_text`)
- `src/hive_planner/launcher/app.py` (`task_text=` wiring)
- `tests/test_voice_panel_task_watch.py` (new)
- `docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session11.md` (this file)

## Paste into new chat

```
Voice_Bot next micro-task (session 11 handoff — close 5e docs or live Moshi)

Handoff: docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session11.md
Repo: D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER | Python: py -3.11

Verdict: read-only=READY full-agent=NOT READY | G7 T055=pass | G7-q8=pass (caveated) | T056 live Moshi=open | STT T056-live-clip/-4=done | T042 slice 5e=code done, tasks.md open

Pod: none on account (t13xqwp4ilb953 terminated)
Backup: D:\DRIVE_DOWNLOADS\POD_BACKUPS\t13xqwp4ilb953-session9\ | q8: POD_BACKUPS\irfh4yaasw-q8\

Done session 11: T056-live-clip-4; pod terminate confirmed; slice 5e typed-task greeting + poll + 15 tests

Do not redo: STT clips 1–4 rows; pod t13xqwp4ilb953; 5e core unless asked

Open next (one micro-task): A) tasks.md 5e status + optional spoken-path sync or pytest crash note, or B) new pod + moshi-talk, or C) T042 live mic

Validation: py -3.11 -m pytest tests/test_voice_panel_task_watch.py -q; combined voice panel suites use -k "not loopback_echo" on Windows if needed

First action: read handoff § Open micro-tasks; if A, edit tasks.md slice 5e bullet only
```
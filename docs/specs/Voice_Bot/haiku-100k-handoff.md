# Voice_Bot — Haiku 100k handoff

**Trigger (this repo, Cursor agent):** `haiku handoff`  
Also: `haiku 100k`, `formulate haiku prompt`, `haiku continue`, `/haiku-100k`.

That trigger makes **another agent** (not Haiku) read `.cursor/commands/haiku-100k.md` and **write a paste-ready prompt** for Claude Haiku. It does not implement Voice_Bot. After Haiku replies, paste Haiku’s **Continue block** back here and say **haiku continue** so the same agent can write the **next** new-chat prompt.

Repo: `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`. Truth: `docs/specs/Voice_Bot/{spec.md,plan.md,tasks.md,evidence-register.md,deployment-gaps.md}`. Python: `py -3.11`.

## Operator quick ref

| You want | You do |
|---|---|
| Start **new** Haiku chat on Voice_Bot gap-fill | In **Cursor**: say **`haiku handoff`**. Copy only the `=== PASTE INTO HAIKU ===` block into a **new** Claude Haiku chat. |
| After Haiku finishes a turn | Copy Haiku’s **`CONTINUE Voice_Bot`** block at the end of its reply. |
| Get the **next** Haiku prompt | Back in **Cursor**: paste that Continue block and say **`haiku continue`**. Cursor updates this file § Prompt and prints a fresh `=== PASTE INTO HAIKU ===`. |

**If you skip the Continue block**, the next prompt cannot be generated safely — use **`tasks.md` validation log** and Phase 5 checkboxes as a manual fallback.

## Loop

```
[you]  "haiku handoff"
[Cursor]  === PASTE INTO HAIKU ===  (compact prompt)
[you]  new Claude Haiku chat, paste that only
[Haiku]  work + mandatory CONTINUE Voice_Bot block
[you]  "haiku continue" + paste that Continue block
[Cursor]  updates this file § Prompt, then === PASTE INTO HAIKU === for chat N+1
```

Budget: ~**100k tokens per Haiku chat** (formulated prompt + Haiku’s reads + replies). Grep/outline; no whole `spec.md`, `HIVE_PLANNING_DEV.md`, or `src/` trees.

## Rules (baked into every formulated prompt)

- One micro-task per turn. Spec before behavior. No `AGENTS.md` product rules. Commits only if asked.
- **Operator 2026-11-12:** R33 latch and **real `voice-bot live-write` are authorized on this host** (`D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`). `edits_enabled: true` already set; do not flip latch on other machines without explicit OK.
- Do not re-prove T001–T040, G0–G6 register rows, fake-ACP T047 tests, or full pytest/npm unless your edit can regress them.
- **Every Haiku turn must end with a filled Continue block.** Stop when budget is low; do not start the next backlog item in the same turn.

## § Prompt (source of truth for the next paste; Cursor rewrites Done/Next on continue)

Voice_Bot next micro-task (from chat ending 2026-11-14 (Cursor — T056 live clips, evidence rows, RunPod inventory)). Repo: D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER. Python: py -3.11.

Verdict carried over: read-only=READY full-agent=NOT READY

Done last chat: Three operator clips transcribed via pinned faster-whisper 1.2.1 + FasterWhisperAdapter; evidence-register rows T056-live-clip and T056-live-clip-2 added; clip-20261114-195013-527434 transcript saved (one word error speech-to-text→speech-to-sex); RunPod read: pod t13xqwp4ilb953 RUNNING $3.19/hr US-KS-2 ports 8002/8011/8998, no volume mounted, list-network-volumes empty (irfh4yaasw not visible on account); recommended stop pod when not doing live Moshi; user has not yet confirmed stop.

Do not redo: G7-q8 evidence row; deployment-gaps session 9 block; full stack bootstrap; moshi-probe --record on old pod; tests/test_voice_record_clip.py (5 pass); T033-S1 pin row; pinned transcriptions of clips 194246-619207, 194802-158013, 195013-527434; rows T056-live-clip and T056-live-clip-2; RunPod inventory unless pod state may have changed.

This chat, one micro-task only: Add evidence-register row T056-live-clip-3 for clip-20261114-195013-527434.wav (partial transcript, note word error and no WER); verify 7-column table row below T056-live-clip-2.

First action: Open docs/specs/Voice_Bot/evidence-register.md at T056-live-clip-2 and insert T056-live-clip-3 row matching format.

Context: read only the sections named in Open next from docs/specs/Voice_Bot/{spec.md,tasks.md,evidence-register.md,deployment-gaps.md}. Do not load full spec.md or src/ trees.

Do First action only; emit the Continue block again at end of turn. Never start the next micro-task in the same turn. If this chat nears ~100k context, stop after the current micro-task and end with a filled Continue block so Cursor can generate the next paste.

Every turn MUST end with a filled block exactly in this shape:

```

CONTINUE Voice_Bot
Last chat: <date>
Budget left: <low|unknown>
Verdict: read-only=<READY|NOT> full-agent=<READY|NOT>
G0–G6: <one-liners if changed>
Done this chat: <1–3 bullets>
Open next: <exactly one micro-task>
Do not redo: <commands that passed>
Files changed: <paths>
Blocked: <or none>
First action: <one line>

```

### Last Continue (Cursor 2026-11-13 — T042 slice 5a)

```
CONTINUE Voice_Bot
Last chat: 2026-11-13 (T042 slice 5a, launcher panel wiring)
Budget left: unknown
Verdict: read-only=READY full-agent=NOT READY (unchanged; G3 not claimed)
G0–G6: unchanged
Done this chat: voice_panel_controller.py added; on_back/on_menu/on_mic/on_end wired in app.py; mic refusal reverts and shows reason; end-call hits /v1/call/end (+ playback interrupt when audio on); tasks.md slice 5 bullet; 43 panel/controller tests + 403 launcher/voice-panel tests passing
Open next: 5b — side button typed-instruction fallback (voice_panel.py side canvas → controller → POST /v1/submit path)
Do not redo: pytest tests/test_voice_panel.py tests/test_voice_panel_controller.py -q (43 passed); pytest tests -q -k "launcher or voice_panel" (403 passed, 2 skipped)
Files changed: src/hive_planner/launcher/voice_panel_controller.py, src/hive_planner/launcher/voice_panel.py, src/hive_planner/launcher/app.py, tests/test_voice_panel.py, tests/test_voice_panel_controller.py, docs/specs/Voice_Bot/tasks.md
Blocked: none
First action: read voice_panel.py _build_footer side canvas and controller status; add on_side callback and a typed-instruction entry that calls the bridge submit route
```

### Last Continue (Cursor 2026-11-12 — polish tier prompts)

```
CONTINUE Voice_Bot
Last chat: 2026-11-12
Budget left: unknown
Verdict: polish-queue=active; start Tier 1 T1-doc
Done this chat: haiku-polish-handoff.md + next-haiku-prompt-tier1..5.md; next-haiku-prompt.md = tier1
Open next: T1-doc (paste tier1 into new Haiku chat)
Do not redo: writing tier prompts
Files changed: docs/specs/Voice_Bot/haiku-polish-handoff.md, next-haiku-prompt-tier*.md, next-haiku-prompt.md, .hive/voice-bot/continue-polish-tier1.txt
Blocked: none
First action: open next-haiku-prompt-tier1.md and paste into Haiku
```

### Last Continue (Cursor 2026-11-12 — U10 execute-write handoff seed)

```
CONTINUE Voice_Bot
Last chat: 2026-11-12
Budget left: unknown
Verdict: read-only=READY full-agent=NOT READY for production use (U10 open: execute-kind writes may bypass unguarded_write)
G0–G6: unchanged; R35 live-write had permissions=[]
Done this chat: deployment eval found execute tool_call not counted in write_events; handoff CLI wrote next-haiku-prompt.md
Open next: U10 — R22 execute write counting (voice_task.py + test_voice_bot_unguarded_write.py)
Do not redo: U6 tests (8 pass); full voice or acp suite unless U10 regresses shared paths
Files changed: docs/specs/Voice_Bot/next-haiku-prompt.md, docs/specs/Voice_Bot/haiku-100k-handoff.md, .hive/voice-bot/continue-u10-execute-write.txt
Blocked: none
First action: read voice_task.py WRITE_TOOL_KINDS and _ingest_tool_call; add execute to write detection; one fake-ACP test
```

### Last Continue (Cursor 2026-11-12 — sequence 17 ci-check + maps)

```
CONTINUE Voice_Bot
Last chat: 2026-11-12
Budget left: unknown
Verdict: read-only=READY full-agent=READY
G0–G6: unchanged (not re-proven this chat)
Done this chat: impact-sync-maps applied; ci-check 10/10 ok (2231 passed, 2 skipped); fixed truncated Voice_Bot cells in project-map.md; dry-run empty
Open next: T042 close-out — R13 running-task interruption test + tasks.md / deployment-gaps A sync
Do not redo: impact-sync-maps; ci-check full run (passed earlier 2026-11-12); R24 rss_reader default in tests/voice_turn_support.py
Files changed: docs/change-impact/project-map.md, docs/change-impact/test-map.md
Blocked: none
First action: read tasks.md T042 + test_voice_bot_interrupt.py; grep R13 audio_enabled patterns in test_voice_bot_speak.py; add minimal integrated test
```

### Last Continue (Cursor 2026-11-12 — after sequence 16 pytest isolation)

```
CONTINUE Voice_Bot
Last chat: 2026-11-12
Budget left: unknown
Verdict: read-only=READY full-agent=READY; ci-check pytest GREEN; whole ci-check blocked on impact-map-drift only
G0–G6: unchanged
Done this chat: pytest polluter = default RSS reader measuring pytest host (>100 MB); fixed tests/voice_turn_support.py default rss_reader; full pytest 2231 passed 2 skipped; ci-check pytest ok
Open next: impact-sync-maps + curate project-map/test-map until impact-map-drift passes; re-run ci-check for ok: true
Do not redo: py -3.11 -m pytest tests -q (2231 passed); ci-check except impact-map step; bisect on r24/sc010
Files changed: tests/voice_turn_support.py
Blocked: none
First action: py -3.11 -m hive_planner impact-sync-maps --dry-run; read diff vs docs/change-impact/*-map.md; apply sync and validate ci-check
```

### Last Continue (Cursor 2026-11-12 — CI isolation handoff seed)

```
CONTINUE Voice_Bot
Last chat: 2026-11-12
Budget left: unknown
Verdict: read-only=READY full-agent=READY; ship blocked on full ci-check pytest only (4 tests)
G0–G6: unchanged; Voice slice 368 passed isolated
Done this chat: deployment eval; documented ci-check fail; no code fix yet
Open next: bisect/repro pytest pollution for r24_runtime + sc010; minimal test or prod fix
Do not redo: voice-only pytest 368 passed; spec-drift-check ok; isolated 6/6 on the four tests
Files changed: docs/specs/Voice_Bot/haiku-100k-handoff.md (§ Prompt only)
Blocked: none
First action: run full pytest with last-failed or bisect; grep monkeypatch/time/config on voice_task and voice_bot across tests/
```

### Last Continue (from Composer 2026-11-12, after T042 slice 3)

```
CONTINUE Voice_Bot
Last chat: 2026-11-12
Budget left: unknown
Verdict: read-only=READY full-agent=READY; T042 slice 3 DONE (bridge spoken route); criterion 4 partial; audio_enabled NOT wired
G0–G6: G3 typed on host; spoken HTTP path exists; speak playback still typed-only; others unchanged
Done this chat: POST /v1/submit/spoken schema+handler; bridge test wav_path → transcript → task instruction
Open next: T042 slice 4 audio_enabled config read site + _say gate; speak.py tests
Do not redo: slice 3 bridge test; test_voice_stt_runtime 10; bridge+stt 79 passed 2 skipped
Files changed: src/hive_planner/voice_bridge.py; tests/test_voice_bot_bridge.py
Blocked: live mic; real faster-whisper over HTTP; extension spoken caller
First action: read spec audio_enabled; add field to VoiceBotConfig and wire _say adapter choice
```

### Last Continue (from Composer 2026-11-12, after T042 slice 2 — archived)

```
CONTINUE Voice_Bot
Last chat: 2026-11-12
Budget left: unknown
Verdict: read-only=READY full-agent=READY; T042 slice 2 runtime entry DONE; bridge/mic NOT wired
G0–G6: G3 typed on host; runtime entry exists but no HTTP caller; others unchanged
Done this chat: submit_spoken; resolve_pinned_model_dir; hybrid_speech_path model gate; test_voice_stt_runtime.py (10)
Open next: wire submit_spoken into local bridge; bridge test transcript → task
Do not redo: T033 WER; slice-2 pytest (23+17+21 passed); faster-whisper venv install
Files changed: voice_task.py, voice_stt.py, voice_bot.py, tests/test_voice_stt_runtime.py, tests/test_voice_stt.py
Blocked: live mic; choose audio transport (path vs bytes) for bridge body schema
First action: read voice_bridge.py POST routes; add spoken submit route → submit_spoken
```

### Last Continue (from Composer 2026-11-12, after T042 slice 1 — archived)

```
CONTINUE Voice_Bot
Last chat: 2026-11-12
Budget left: unknown
Verdict: read-only=READY full-agent=READY; gap B=T043 CLOSED; gap A=criteria 1–3 CLOSED (T033 pin); T042 slice 1 DONE; runtime capture NOT wired; criterion 4 partial
G0–G6: G0 pass; G1 fallback pass; G2 pass; G3 typed (stt_provider null on host); G4 pass (T043); G5 pass; G6 pass
Done this chat: stt_provider config read site; hybrid_speech_path(config); voice_stt.py FasterWhisperAdapter; wer.py; test_voice_stt.py; gates updated; register/tasks T042 partial
Open next: runtime capture calling adapter behind stt_provider; hybrid_speech_path must not lie (stt only when transcribe path exists)
Do not redo: T043 EDH 18/18; T033 fixtures/WER unless fixtures change; faster-whisper venv install; gate+speak 40 passed (2 skipped global)
Files changed: src/hive_planner/voice_stt.py, voice_bot.py, scripts/stt_pin/*, tests/test_voice_stt.py, test_voice_bot_gates.py, evidence-register.md, tasks.md
Blocked: audio speak + live interruption rows; .hive/stt-pin/.venv not gitignored
First action: read voice_task.py for voice turn submit; minimal capture entry → FasterWhisperAdapter.transcribe
```

## Haiku reply format

1. Verdict (read-only vs full)  
2. G0–G6 one-liners  
3. Commands + counts  
4. Files touched  
5. Wiring audit  
6. Footnote (one plain paragraph)  
7. **Continue block (required, last)**

## Continue block (Haiku fills every turn — copy this shape exactly)

```
CONTINUE Voice_Bot
Last chat: <date>
Budget left: <low|unknown>
Verdict: read-only=<READY|NOT> full-agent=<READY|…>
G0–G6: <one-liners if changed>
Done this chat: <1–3 bullets>
Open next: <next bug-hunt focus: file/surface, or "another full pass", or none>
Do not redo: <commands that passed>
Files changed: <paths>
Blocked: <or none>
First action: <one line>
```

## Wiring chain

typed instruction → `VoiceTaskRunner.submit` → `agent acp` → evidence → `spoken_update` / `written_result`; editor snapshot → bridge `editor_snapshot` → R22 stale check; T031 → `POST /v1/playback/interrupt` | `POST /v1/call/end` → runner → `state.json`.

## Do not paste into Haiku

This whole file except § Prompt; `docs/HIVE_PLANNING_DEV.md`; full `spec.md`; full `src/`; `node --test test/` (four named files only).

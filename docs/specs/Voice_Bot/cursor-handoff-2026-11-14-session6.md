# Voice_Bot — handoff after T056 close (2026-11-14, session 6)

**Purpose:** Continue **Voice_Bot** with **no live pod**. G7 (T055) and **T056** are **done**. Pod `yfhzy2r86j9akc` remains terminated; do not assume it is RUNNING.

**Supersedes:** `docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session5.md` (session 5 open items 1–2 are closed here).

**Repo:** `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`  
**Python (this host):** `py -3.11`  
**Active feature:** Voice_Bot

## Verdict

| Lane | Verdict |
|------|---------|
| read-only typed preview | READY |
| full-agent production | NOT READY |
| **G7 Moshi harness (T055)** | **pass** — recorded 2026-11-14 |
| **G7-q8 on live server** | **partial** — q8 needs `quantize.py` `.float()` patch (saved in `pod-artifacts/`; not in repo) |
| **T056 Moshi wiring + duplex** | **done** — code audit closed; live duplex proved session 5; CLI utterance counter fixed session 6 |

## Pod (closed)

| Field | Value |
|-------|-------|
| Last pod id | `yfhzy2r86j9akc` (`g7-moshi-single-h100`) |
| Status | **Gone** — `get-pod` returns 404 (terminated 2026-11-14) |
| Last proxy | `wss://yfhzy2r86j9akc-8998.proxy.runpod.net/api/chat` (dead) |
| Billing | **Off** for this id |

**New live work:** provision a pod only if the user authorizes spend; reuse launch recipes in `cursor-g7-runpod-handoff.md` and local assets below.

## Local artifacts (survive pod loss)

| Asset | Path |
|-------|------|
| q8 weights | `D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8\model.q8.safetensors` |
| q8 SHA256 | `0142f1c7df455c50e882cee8210ae3ccc28fecf1310762a6d7c3a693e89a0ddc` |
| quantize patch + logs | `docs/specs/Voice_Bot/pod-artifacts/` |
| G7 evidence | `docs/specs/Voice_Bot/evidence-register.md` |
| Tasks | `docs/specs/Voice_Bot/tasks.md` — T055 done, **T056 done** |

## Session 6 completed (this chat)

1. **Root cause confirmed:** session-5 live run showed `utterances 0` because `cli.py` `moshi-talk` called `talk()` without `on_utterance`, so `UtteranceSegmenter` was never constructed (not proof of silence; server STT was active on pod log).
2. **Fix:** `voice_moshi.count_utterance_only` — count-only sink for CLI (speech-to-task stays on panel path). `cli.py` passes `on_utterance=count_utterance_only` into `talk()`.
3. **Test:** `test_cli_moshi_talk_counts_user_utterances` runs real `hive_planner` `main(..., "voice-bot", "moshi-talk", ...)` against a loopback websocket with scripted mic; expects 2 utterances; fails if fix removed (`0 == 2`).
4. **T056 closed** in `tasks.md` with wiring audit summary (chain traced end to end).
5. **Validation:** `pytest tests/test_voice_moshi_conversation.py tests/test_voice_moshi.py tests/test_voice_panel_controller.py` → **98 passed**.

## Session 5 context (still true)

- Live `moshi-talk` 20 s over proxy: `sent_frames 249`, `audio_out_samples 474240`, `error ""` (utterance field was misleading until session 6 fix).
- `pod-artifacts/` holds `quantize.py` patch (`state.SCB = self.weight_scb.float()`), log tails, handshake timing.

## Open micro-tasks (priority order)

1. **G7-q8 repo:** document or script the quantize patch from `pod-artifacts/quantize.py` so the next pod boot is repeatable without manual pod edits (no pod required).
2. **Optional live re-prove:** new Runpod only on user authorization — transfer q8 from `POD_BACKUPS`, apply quantize patch, stack per `cursor-g7-runpod-handoff.md`; re-run `moshi-talk` and confirm `utterances > 0` on CLI; optional launcher panel live duplex.
3. **T042 Speech S1:** only open checkbox in `tasks.md`; deferred for preview ship (Path A); see `deployment-gaps.md`.
4. **Moshi Tool Lane ML-T5:** live G7 row for tool lane — blocked without operator-run Moshi server (`AGENTS.md` active lane).

## Do not redo

- G7 `moshi-probe --record` (T055 pass unless user asks to reprove).
- Assume pod `yfhzy2r86j9akc` is up.
- Wrong proxy host (`60831` suffix vs `-8998`).
- Re-open T056 unless a new gap is found in the Moshi chain.

## Wiring audit (current)

| Link | Status |
|------|--------|
| G7 probe → evidence register | pass (T055) |
| Live duplex audio host → proxy → Moshi | proved session 5 |
| Server STT / RAG (log evidence) | observed on pod log (session 5) |
| CLI `moshi-talk` → `on_utterance` → `utterances` | **pass** (session 6) |
| Panel mic → `talk(..., on_utterance=...)` | coded + unit tests; live panel not recorded |
| Single-connection server lock | documented; no concurrent probe during call |

## Files touched session 6

- `src/hive_planner/cli.py`
- `src/hive_planner/voice_moshi.py`
- `tests/test_voice_moshi_conversation.py`
- `docs/specs/Voice_Bot/tasks.md`
- `docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session6.md` (this file)

## Paste into new chat

Copy as the **first user message**:

```
CONTINUE Voice_Bot (post-T056 — G7-q8 / optional pod)

Last chat: 2026-11-14 session 6 (T056 closed; no pod)
Handoff: docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session6.md
Verdict: read-only=READY full-agent=NOT READY | G7=pass | T055=done | T056=done
Pod: yfhzy2r86j9akc GONE (404) — billing off

Done session 6:
- CLI moshi-talk wires on_utterance (count_utterance_only); utterances counter works
- test_cli_moshi_talk_counts_user_utterances (real main + loopback); 98 pytest pass
- T056 marked done + wiring audit in tasks.md

Still partial:
- G7-q8 quantize .float() patch only in pod-artifacts (not tracked runbook)
- Live CLI utterances>0 not re-recorded on a pod (unit proof only)
- Panel duplex live not recorded

Open next (pick per user):
1. G7-q8: doc/script quantize patch from pod-artifacts
2. New Runpod only if user authorizes — q8 from POD_BACKUPS, stack handoff, moshi-talk live
3. T042 Speech S1 (deferred) or ML-T5 Moshi tool lane when server exists

Do not redo: G7 --record; assume old pod URL; T056 unless new gap

Files touched session 6: cli.py, voice_moshi.py, test_voice_moshi_conversation.py, tasks.md, this handoff

First action: read handoff; if user wants q8 doc, read pod-artifacts/README and quantize.py; else ask which open item
```
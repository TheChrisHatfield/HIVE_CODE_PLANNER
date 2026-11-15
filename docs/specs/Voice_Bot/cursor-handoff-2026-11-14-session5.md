# Voice_Bot — handoff after Runpod shutdown (2026-11-14, session 5)

**Purpose:** Continue **Voice_Bot** with **no live pod**. G7 (T055) is done. **T056** is open: finish wiring audit and fix CLI utterance evidence. Pod `yfhzy2r86j9akc` was **terminated** by the user; do not assume `get-pod` returns RUNNING.

**Historical note (2026-11-14 session 6):** T056 and the CLI utterance fix are **done** — use `cursor-handoff-2026-11-14-session6.md` for continuation.

**Supersedes:** live-pod section of `docs/specs/Voice_Bot/cursor-g7-runpod-handoff.md` (session 4 end still useful for stack launch recipes).

**Repo:** `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`  
**Python (this host):** `py -3.11`  
**Active feature:** Voice_Bot

## Verdict

| Lane | Verdict |
|------|---------|
| read-only typed preview | READY |
| full-agent production | NOT READY |
| **G7 Moshi harness (T055)** | **pass** — recorded 2026-11-14 |
| **G7-q8 on live server** | **partial** — q8 needs `quantize.py` `.float()` patch (saved in repo artifacts) |
| **T056 wiring + live duplex** | **open** — live audio proved; client utterance counter + panel trace remain |

## Pod (closed)

| Field | Value |
|-------|-------|
| Last pod id | `yfhzy2r86j9akc` (`g7-moshi-single-h100`) |
| Status | **Gone** — `get-pod` returns 404 (user stopped/terminated 2026-11-14) |
| Last proxy | `wss://yfhzy2r86j9akc-8998.proxy.runpod.net/api/chat` (dead) |
| Billing | **Off** for this id |

**New live work:** provision a pod only if the user authorizes spend; reuse launch recipes in `cursor-g7-runpod-handoff.md` and local assets below.

## Local artifacts (survive pod loss)

| Asset | Path |
|-------|------|
| q8 weights | `D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8\model.q8.safetensors` |
| q8 SHA256 | `0142f1c7df455c50e882cee8210ae3ccc28fecf1310762a6d7c3a693e89a0ddc` (matches last pod read) |
| quantize patch + logs | `docs/specs/Voice_Bot/pod-artifacts/` (`quantize.py`, `README-pod-artifacts.txt`, log tails) |
| G7 evidence | `docs/specs/Voice_Bot/evidence-register.md` |
| Tasks | `docs/specs/Voice_Bot/tasks.md` — T055 done, T056 open |

## Session 5 completed (this chat)

1. Verified stack on pod before shutdown: :8011 encoder, :8002 vLLM, :8998 Moshi.
2. Live `moshi-talk` 20 s over proxy: `sent_frames 249`, `audio_out_samples 474240`, `error ""`.
3. Pulled pod-only `quantize.py` patch and log tails into `pod-artifacts/`.
4. Confirmed local q8 backup SHA256 matches pod.
5. **Finding:** `utterances 0` on CLI is **not** proof of silence — `cli.py` `moshi-talk` calls `talk()` **without** `on_utterance`, so `UtteranceSegmenter` is never created. Panel path **does** pass `on_utterance` (`voice_panel_controller.py`).
6. Pod `moshi_8998.tail.log` shows server STT recognized user speech during the live window (RAG reference to vLLM + encoder).

## Open micro-tasks (priority order)

1. **T056 CLI fix:** wire `on_utterance` in `moshi-talk` (noop or log callback) so `utterances` increments; add or extend test in `tests/test_voice_moshi_conversation.py`.
2. **T056 close:** wiring audit summary in `tasks.md` (chain traced); mark T056 done when audit + utterance evidence criteria met (no pod required for CLI fix; panel trace is code-level unless user wants launcher live test).
3. **G7-q8 repo:** port `pod-artifacts/quantize.py` change into tracked docs or patch script; optional test/doc only until next pod.
4. **Optional next pod:** only on user request — transfer q8 from `POD_BACKUPS`, apply quantize patch, run handoff launch recipes, warm ws before probe.

## Do not redo

- G7 `moshi-probe --record` (T055 pass unless user asks to reprove).
- Assume pod `yfhzy2r86j9akc` is up.
- Wrong proxy host (`60831` suffix vs `-8998`).

## Wiring audit (current)

| Link | Status |
|------|--------|
| G7 probe → evidence register | pass (T055) |
| Live duplex audio host → proxy → Moshi | proved session 5 |
| Server STT / RAG (log evidence) | observed on pod log |
| CLI `moshi-talk` utterance counter | **gap** — no `on_utterance` |
| Panel mic → `talk(..., on_utterance=...)` | coded + unit tests; live panel not recorded |
| Single-connection server lock | documented; no concurrent probe during call |

## Paste into new chat

Copy as the **first user message**:

```
CONTINUE Voice_Bot (post-Runpod — T056 close)

Last chat: 2026-11-14 session 5 (pod terminated; artifacts saved)
Handoff: docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session5.md
Verdict: read-only=READY full-agent=NOT READY | G7=pass | T055=done | T056=open
Pod: yfhzy2r86j9akc GONE (404) — billing off

Done session 5:
- Live moshi-talk duplex audio over proxy (249 frames in, ~20s model audio out)
- pod-artifacts: quantize.py patch + log tails; q8 on disk at POD_BACKUPS (SHA verified)
- Corrected: CLI utterances 0 because moshi-talk omits on_utterance (not silence)
- Server log shows STT + RAG during live run

Open next:
1. Fix CLI moshi-talk to pass on_utterance so utterances count (+ test)
2. Finish T056 wiring audit in tasks.md; mark done when criteria met
3. Optional: repo quantize/q8 doc from pod-artifacts
4. New Runpod only if user authorizes

Do not redo: G7 --record; assume old pod URL

Files touched session 5: tasks.md, docs/specs/Voice_Bot/pod-artifacts/*, this handoff

First action: read handoff; grep cli.py moshi-talk and voice_moshi talk/on_utterance; implement CLI utterance wiring + test
```
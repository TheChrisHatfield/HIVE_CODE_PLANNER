# Voice_Bot — handoff after STT evidence + pod stop (2026-11-14, session 10)

**Purpose:** Continue **Voice_Bot** after three pinned-STT live-clip evidence rows, **operator-stopped** pod `t13xqwp4ilb953`, and a **partial local backup** before terminate.

**Supersedes:** `docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session9.md` for **billing, pod status, and open micro-tasks** only. Session 9 stack/probe details remain authoritative in session 9 until the pod disk is terminated.

**Repo:** `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`  
**Python (this host):** `py -3.11`  
**Active feature:** Voice_Bot

## Verdict

| Lane | Verdict |
|------|---------|
| read-only typed preview | READY |
| full-agent production | NOT READY |
| **G7 Moshi harness (T055)** | **pass** (recorded; old pod) |
| **G7-q8** | **pass (caveated)** in `evidence-register.md` (session 9 probe on `t13xqwp4ilb953`, unrecorded; pod-only deltas in `deployment-gaps.md` Session 9) |
| **T056 live STT clips (pinned Whisper)** | **partial** — rows `T056-live-clip`, `-2`, `-3` in register; **T042 / live Moshi talk still open** |

## Done session 10 (this chat)

1. **Evidence register:** added `T056-live-clip-3` for `clip-20261114-195013-527434.wav` (partial, word error noted, no WER).
2. **Pod billing:** operator **stopped** pod `t13xqwp4ilb953` → status **EXITED** (no GPU hourly; **volume disk still bills** until terminate).
3. **Pre-terminate backup:** `D:\DRIVE_DOWNLOADS\POD_BACKUPS\t13xqwp4ilb953-session9\` — `warm_ws.py`, patched `arc_encoder.py` / `quantize.py` (reconstructed + repo copy), scripts, `MANIFEST.md`. Q8 weights **not** re-downloaded (use `POD_BACKUPS\irfh4yaasw-q8\`).
4. **Pod start for live pull:** MCP `pod-action start` returned **400 — not enough free GPUs on the host machine** (stopped pod pinned to host). **Not terminated** in this chat.

## Active pod (re-read every chat)

| Field | Value |
|-------|-------|
| Pod id | **`t13xqwp4ilb953`** |
| Name | `g7-q8-reprove-voice-bot` |
| Status | **TERMINATED** (confirmed 2026-11-14: get-pod 404 "pod not found"; list-pods on account returned none; disk no longer bills). Pod-only `*.orig`, `warm_ws.log`, and log tails were **not** pulled and are not recoverable from this pod. |
| Last known GPU rate | **$3.19/hr** H100 NVL when RUNNING (US-KS-2) |
| Disk | **200 GB** pod volume (bills while stopped) |
| Network volume | **none mounted** |
| Stack when stopped | Session 9 had :8011 / :8002 / :8998 up; assume **cold** after any start |
| Proxy (if RUNNING) | `wss://t13xqwp4ilb953-8998.proxy.runpod.net/api/chat` |

**Terminate:** only after operator confirms backup is enough **or** optional live pull completes (see below).

## Local backup (session 10)

| Asset | Path |
|-------|------|
| Session 9 pod artifacts (partial) | `D:\DRIVE_DOWNLOADS\POD_BACKUPS\t13xqwp4ilb953-session9\` |
| q8 weights + tokenizer | `D:\DRIVE_DOWNLOADS\POD_BACKUPS\irfh4yaasw-q8\` |
| STT clips + transcripts | `.hive/voice-bot/recordings/` (`clip-20261114-194246-619207`, `194802-158013`, `195013-527434` + `.transcript.txt`) |
| Fourth clip (no register row yet) | `clip-20261114-194025-466141.wav` |

Pending on pod disk only (need **RUNNING**): `*.orig` backups, `warm_ws.log`, log tails — see `MANIFEST.md` and `pull-from-pod.sh` in the backup folder.

## Do not redo

- G7 T055 `moshi-probe --record` on old pod URL unless user asks.
- G7-q8 evidence row rewrite or Session 9 `deployment-gaps` block unless user asks.
- Pinned transcriptions for clips **194246**, **194802**, **195013**.
- Register rows **T056-live-clip**, **-2**, **-3**.
- Full stack bootstrap on `t13xqwp4ilb953` if disk intact and operator only needs optional log pull then terminate.
- Failed placeholder `runpodctl pod start` pattern (this CLI uses `runpodctl start pod <id>`; prefer Runpod MCP when connected).

## Open micro-tasks (priority — pick one per chat)

### A. Pod lifecycle (operator billing)

1. `get-pod t13xqwp4ilb953`.
2. If terminating: retry `pod-action start` until success → run `pull-from-pod.sh` via `exec-pod` → download tarball → `pod-action stop` → **`pod-action terminate`** when user confirms.
3. If reconstructed backup is enough: user says **terminate** → `pod-action terminate` (disk gone; session 9 on-disk stack not recoverable).

### B. T056 live Moshi talk

Requires a **RUNNING** Moshi stack (this pod after start + warm, or a **new** pod per `cursor-g7-runpod-handoff.md`). Not available while `t13xqwp4ilb953` is EXITED.

`py -3.11 -m hive_planner voice-bot moshi-talk --url wss://t13xqwp4ilb953-8998.proxy.runpod.net/api/chat --duration N` — target **`utterances > 0`**.

### C. STT evidence (no pod)

Optional: register row for `clip-20261114-194025-466141.wav` if transcribed; or batch validate register rows T056-live-clip*.

## Session 9 stack reference (unchanged)

Full bootstrap, quantize patch, probe pass, warm_ws, vLLM `0.3` util: `cursor-handoff-2026-11-14-session9.md` + `deployment-gaps.md` Session 9 block.

## Files touched session 10

- `docs/specs/Voice_Bot/evidence-register.md` (`T056-live-clip-3`)
- `D:\DRIVE_DOWNLOADS\POD_BACKUPS\t13xqwp4ilb953-session9\` (created; not in git)
- `docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session10.md` (this file)

## Paste into new chat

```
Voice_Bot next micro-task (session 10 handoff — pod terminate or T056 live)

Handoff: docs/specs/Voice_Bot/cursor-handoff-2026-11-14-session10.md
Repo: D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER | Python: py -3.11

Verdict: read-only=READY full-agent=NOT READY | G7 T055=pass | G7-q8=pass (caveated) | T056 live Moshi=open | STT clips T056-live-clip/-2/-3=done

Pod: t13xqwp4ilb953 EXITED (operator stopped); disk still bills; start blocked earlier (host GPU full) — re-read get-pod
Backup: D:\DRIVE_DOWNLOADS\POD_BACKUPS\t13xqwp4ilb953-session9\ | q8: POD_BACKUPS\irfh4yaasw-q8\

Done session 10: T056-live-clip-3 register row; pod stop; partial pre-terminate backup; terminate not done

Do not redo: T056-live-clip 1–3 rows; pinned transcriptions 194246/194802/195013; G7-q8 register rewrite; G7 --record old pod

Open next (one micro-task): operator chooses A) retry start → optional pull-from-pod → terminate, or B) moshi-talk after stack up, or C) STT clip 194025 evidence

Blocked on A: host GPU capacity for start (may clear later)

First action: get-pod t13xqwp4ilb953; ask operator A vs B vs C if unclear
```
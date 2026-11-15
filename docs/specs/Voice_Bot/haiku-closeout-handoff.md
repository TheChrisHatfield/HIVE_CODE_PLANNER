# Voice_Bot — Haiku closeout (speech + full-agent production)

**Use when:** spoken mic (gap A) and fleet **production `agent` edits** are not ready until criterion 4, live evidence, operator review, and **per-host** `edits_enabled` are satisfied.

**Cursor trigger:** `haiku handoff` (start) or `haiku continue` (after each Haiku Continue block).

**Repo:** `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`. **Python:** `py -3.11`.

**Baseline (2026-11-12, Cursor deployment eval):** `pytest tests -k "voice or acp"` → **389 passed**, 2 skipped; `test_voice_bot_write_gate.py` + `test_voice_bot_unguarded_write.py` → **12 passed**; extension `npm test` → **58/58**; `spec-drift-check --feature Voice_Bot` ok; **U11b** brokered `fs/write_text_file` in `voice_task.py`.

**Lanes (do not over-claim):**

| Lane | Target |
|---|---|
| Read-only / ask / plan | READY (no Haiku work required unless regress) |
| Deploy pack | READY |
| Speech G3 (S1 mic) | NOT until T042 criterion 4 + live rows (C1–C4) |
| Full `agent` production fleet-wide | NOT until operator sign-off + per-host latch policy (F1–F4) |

**Rules:** One micro-task per Haiku chat. No `edits_enabled: true` on other hosts. No `AGENTS.md` product rules. Commits only if operator asks. Every Haiku turn ends with a `CONTINUE Voice_Bot` block.

---

## Sequence overview

Run **one column** at a time unless the operator says to interleave.

### F — Full-agent production (Tier F)

| ID | Paste file | Micro-task |
|---|---|---|
| **F1** | `next-haiku-prompt-closeout-f1.md` | Verdict sync: `spec.md` § Deployment readiness, `tasks.md` active task, `deployment-gaps.md` lane table — full-agent stays **NOT READY for production use** until operator signs checklist (no latch flip). |
| **F2** | `next-haiku-prompt-closeout-f2.md` | **Operator production checklist** (new short doc or deployment-gaps appendix): G6 pass, U11b green, U10 residual acknowledged, R35 optional re-run, per-host `edits_enabled` default false, RSS review. |
| **F3** | `next-haiku-prompt-closeout-f3.md` | **T3-u11:** Log `toolCall.kind` + redacted command on task evidence; extend `live-write-run.json` shape; test via fake ACP. |
| **F4** | `next-haiku-prompt-closeout-f4.md` | **Interpreter writes:** extend `_is_write_call` only if a fixture repro exists; else document residual in `deployment-gaps.md` + one TODO test skip with reason. Operator sign-off row template in `evidence-register.md` (doc). |

### C — Speech / gap A (Tier C)

| ID | Paste file | Micro-task |
|---|---|---|
| **C1** | `next-haiku-prompt-closeout-c1.md` | **T042 criterion 4:** `stt_provider` pin path — register § T033 pin row (complete criterion 4 text), `test_voice_bot_gates.py`, `hybrid_speech_path(config)` when `stt_provider` matches pin (fake adapter in tests; no fleet config flip). |
| **C2** | `next-haiku-prompt-closeout-c2.md` | **U7 pack/install:** `_voice_pack_install_md` + `INSTALL.md` — `[voice]` extra vs `ensure-runtime` vs offline wheels for faster-whisper pins. |
| **C3** | `next-haiku-prompt-closeout-c3.md` | **Extension spoken caller:** wire `hive.voiceBot.submitSpoken` (or equivalent) → `POST /v1/submit/spoken`; unit test in `bridge-client.test.js`; no live mic unless operator runs capture. |
| **C4** | `next-haiku-prompt-closeout-c4.md` | **Live evidence rows:** `evidence-register.md` — T034 `audio: true` + audio-on R13 row; operator runs host; Haiku only docs/tests if live blocked. |

**Suggested order for “fix both” goal:** **F1 → F2 → C1 → C2 → C3 → F3 → C4 → F4**, then Cursor re-run deployment evaluation.

---

## After closeout

Update `haiku-100k-handoff.md` § Prompt to **closeout done** or next feature. Run deployment evaluation in Cursor.

# Voice_Bot secondary bug review — Haiku run series (5 chats)

**Source:** Composer feature map 2026-11-13 (19 areas + 7 hotspots).  
**Repo:** `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER` · **Python:** `py -3.11`

Each row is one **new Claude Haiku chat**. Paste only the file in the **Prompt file** column (between `=== PASTE INTO HAIKU ===` fences). After a run finishes, start the next run in a **fresh** Haiku chat (do not append run 2 into the run 1 thread).

| Run | Scope (ids) | Items | Prompt file |
|-----|-------------|-------|-------------|
| **1** | H1–H5 | Writes, permissions, bridge, queue, secrets | [next-haiku-prompt-review-run1.md](./next-haiku-prompt-review-run1.md) |
| **2** | H6–H7, 1–3 | Recovery, latency, session, snapshots, tools | [next-haiku-prompt-review-run2.md](./next-haiku-prompt-review-run2.md) |
| **3** | 4–8 | State machine, interrupt/cancel, speech, events, stale | [next-haiku-prompt-review-run3.md](./next-haiku-prompt-review-run3.md) |
| **4** | 9–13 | Adapters, correlation, STT/audio flags, limits, G1 fallback | [next-haiku-prompt-review-run4.md](./next-haiku-prompt-review-run4.md) |
| **5** | 14–19 | Bridge editor, ACP loop, extension contract, R25, pack CLI, cartridge Q&A | [next-haiku-prompt-review-run5.md](./next-haiku-prompt-review-run5.md) |

**Within one run:** one checklist item per Haiku turn (fix + targeted pytest), then Continue; repeat until the batch is done or budget is low.

**After run 5:** optional return to T042 live-mic evidence (`scripts/voice_t042_live_mic.py`) or `haiku continue` in Cursor for polish.

**Rules (all runs):** Spec before behavior · no `AGENTS.md` product rules · no live G2/G6/R35 re-probe unless touched · commits only if asked.

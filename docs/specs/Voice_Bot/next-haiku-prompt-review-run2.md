=== PASTE INTO HAIKU ===

Voice_Bot bug review — **Run 2 of 5**. Repo: D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER. Python: py -3.11.

**Batch 2** (5 items). One item per turn, in order. After item **3** (area 3), Continue through H6→H7→1→2→3; when **3** is done, `Open next: Run 3` → new chat with `next-haiku-prompt-review-run3.md`.

Assume Run 1 (H1–H5) is done unless operator says otherwise. Re-run failed Run 1 items only if Continue says so.

Verdict: read-only=READY; full-agent=NOT READY. Spec = grep by R-number in `docs/specs/Voice_Bot/spec.md`.

## Batch 2 — recovery, budgets, lifecycle, context, tools

| Id | Spec | Target | Primary files / tests |
|----|------|--------|------------------------|
| H6 | R26, R29 | Restart → unknown; dedupe `(session_id, client_request_id)` | `voice_task.py`, `voice_bot.py`, `tests/test_voice_bot_edges.py` |
| H7 | R24, R21 | Limits from config; latency/RSS measurement not hard-coded | `voice_bot.py` config, `scripts/voice_r24_latency_probe.py`, r24 tests |
| 1 | R1, R25 | Session lifecycle: interrupt ≠ end ≠ cancel task; call end + pending approval | `voice_task.py`, interrupt/end routes, `tests/test_voice_bot_interrupt.py` |
| 2 | R2, R28 | Snapshots: truncation 64KB, binary/unsaved, multi-root binding | `voice_bot.py`, bridge `editor_snapshot`, `tests/test_voice_bot_safety.py`, bridge tests |
| 3 | R18 | Eight tools only; argument schema; reject shell tools | `voice_bridge.py`, tool registry, `tests/test_voice_bot.py` / safety |

First action: **H6** — read R26/R29 in spec; trace dedupe on submit and restart load from `.hive/voice-bot/state.json`.

Continue: `Review run: 2 of 5`; `Open next` = H7 | 1 | 2 | 3 | Run 3 (same block shape as Run 1).

=== END PASTE ===

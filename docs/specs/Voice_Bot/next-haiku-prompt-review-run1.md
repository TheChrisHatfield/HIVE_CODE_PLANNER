=== PASTE INTO HAIKU ===

Voice_Bot bug review — **Run 1 of 5** (Composer map 2026-11-13). Repo: D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER. Python: py -3.11.

This chat owns **batch 1 only** (items below). Complete items **in order**, **one per turn**: read → trace integrated path → fix → targeted pytest → wiring audit. When batch 1 is done, Continue says `Open next: Run 2` and operator starts a **new** Haiku chat with `next-haiku-prompt-review-run2.md`.

Verdict: read-only=READY; full-agent=NOT READY for production. G0–G6 closed in register—no live probes unless you edit those paths.

Do not redo: full pytest 2231; T033 pin; unrelated batches.

## Batch 1 — security and broker (5 items)

| Id | Spec | Target | Primary files / tests |
|----|------|--------|------------------------|
| H1 | R22 | Unguarded writes: execute/shell bypass (e.g. python -c open().write) | `voice_task.py`, `tests/test_voice_bot_unguarded_write.py` |
| H2 | R6, R27 | Permission broker: exact approve/deny, timeout, one pending, question vs approve | `voice_task.py`, `voice_bridge.py`, `tests/test_voice_bot_permissions.py` |
| H3 | R23 | Bridge: token 401, stale request_id 409, schema before dispatch | `voice_bridge.py`, `tests/test_voice_bot_bridge.py` |
| H4 | R5 | Queue: depth 5, held @ awaiting_approval, discard on session end | `voice_task.py`, `voice_bot.py`, queue tests in edges/permissions |
| H5 | R2 | Secret exclusion: deny-list + regex → `excluded: secret` | snapshot builders, `tests/test_voice_bot_safety.py` |

First action (turn 1): **H1** — grep spec deployment notes on execute writes; read `WRITE_COMMAND_RE`, `write_events`, `_ingest_tool_call` in `voice_task.py`; fix + test.

Per turn: grep spec by R-number only; no full `spec.md` load.

Continue block — `Open next` = next id in batch (H2…H5) or `Run 2 — paste next-haiku-prompt-review-run2.md` when H5 done:

```
CONTINUE Voice_Bot
Last chat: <date>
Budget left: <low|unknown>
Verdict: read-only=READY full-agent=NOT READY
Review run: 1 of 5
Done this chat: <id + fix summary>
Open next: <H2|H3|H4|H5|Run 2>
Do not redo: <pytest that passed>
Files changed: <paths>
Blocked: <or none>
First action: <one line>
```

=== END PASTE ===

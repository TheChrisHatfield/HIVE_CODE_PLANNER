=== PASTE INTO HAIKU ===

Voice_Bot bug review — **Run 3 of 5**. Repo: D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER. Python: py -3.11.

**Batch 3** (5 items): areas **4–8**. One item per turn, in order. When **8** is done → `Open next: Run 4` → `next-haiku-prompt-review-run4.md`.

Verdict: read-only=READY; full-agent=NOT READY. Minimal fixes + integrated tests only.

## Batch 3 — task machine, control, truth, events, stale writes

| Id | Spec | Target | Primary files / tests |
|----|------|--------|------------------------|
| 4 | R20 | Task FSM: transitions, `provider_lost` 300s, cancel_requested vs cancelled | `voice_task.py`, `tests/test_voice_bot.py`, edges |
| 5 | R7, R13 | Playback interrupt vs explicit cancel; cancel_on_interruption semantics | `voice_task.py`, `tests/test_voice_bot_interrupt.py` |
| 6 | R8, R14 | Test-state speech mapping; 300-char cap; progress throttle | `voice_task.py`, `tests/test_voice_bot_results.py` or speak tests |
| 7 | R17 | Normalized events on task record; UI/speech not raw ACP tokens | `voice_task.py`, event mapping, task tests |
| 8 | R22 | Stale buffer at submit **and** at write approval | `voice_task.py`, `tests/test_voice_bot_safety.py`, bridge stale tests |

**Done (Cursor 2026-11-13):** item **4** — `prior_state` on every `→ unknown`; `test_disconnect_while_cancel_requested_reconnects_to_cancel_requested`.

**Done (Cursor 2026-11-13):** item **5 audit** — no interrupt→cancel path; 15 interrupt tests pass; `cancel_on_interruption` scaffold (Pipecat tools not registered in hive src).

**Next:** item **5 close-out** (doc Option A in `deployment-gaps.md` row A), then **6**.

First action: read `deployment-gaps.md` row A + `spec.md` R13 (~436-444); add Notes bullet documenting R13 scaffold; sanity `pytest tests/test_voice_bot_interrupt.py -q` if doc-only.

Continue: `Review run: 3 of 5`; after item 5 close-out, `Open next` = item 6.

Do First action only; emit Continue block at end of turn.

=== END PASTE ===

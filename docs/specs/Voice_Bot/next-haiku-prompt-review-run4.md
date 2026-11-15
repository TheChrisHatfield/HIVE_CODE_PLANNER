=== PASTE INTO HAIKU ===

Voice_Bot bug review — **Run 4 of 5**. Repo: D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER. Python: py -3.11.

**Batch 4** (5 items): areas **9–13**. One item per turn. When **13** is done → `Open next: Run 5` → `next-haiku-prompt-review-run5.md`.

Verdict: read-only=READY; full-agent=NOT READY.

## Batch 4 — portability, resilience, speech flags, limits, strategy

| Id | Spec | Target | Primary files / tests |
|----|------|--------|------------------------|
| 9 | R11 | Adapter swap: second stub adapter; contracts unchanged | `voice_bot.py` adapters, `tests/test_voice_bot_gates.py` |
| 10 | R9 | Correlation: task/tool/session ids on retry, disconnect, timeout | `voice_task.py`, `voice_acp.py`, edges |
| 11 | R10, R32 | `hybrid_speech_path`, `stt_provider`, `audio_enabled` read sites | `voice_bot.py`, `voice_stt.py`, `tests/test_voice_stt*.py`, speak tests |
| 12 | R21 | Instruction/snapshot/diff limits from config; rejection vs truncated flag | `VoiceBotConfig`, handlers, `tests/test_voice_bot_safety.py` |
| 13 | R19 | `coding_unavailable` when agent missing; labeled ACP fallback | `voice_task.py`, `tests/test_voice_bot_gates.py` |

First action: **9** — find adapter injection points; confirm session/task/permission APIs stable across Typed vs Pipecat stub.

Continue: `Review run: 4 of 5`; `Open next` = 10 | 11 | 12 | 13 | Run 5.

=== END PASTE ===

=== PASTE INTO HAIKU ===

Voice_Bot **closeout F3 — toolCall evidence logging (T3-u11)**. Repo: `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`. Python: `py -3.11`.

**This chat — one micro-task: F3**  
Improve **auditability** for production agent review:

1. Grep `toolCall`, `raw_events`, `live-write-run.json` in `voice_task.py` / `voice_bot.py`.
2. On each ingested tool call, append normalized fields: `kind`, redacted command (no secrets; truncate), tool call id — on task record evidence.
3. Extend or document `.hive/voice-bot/live-write-run.json` shape in `evidence-register.md` R35 notes.
4. One integrated fake-ACP test asserting kind+redacted command present after `execute`.
5. `pytest` targeted + `tests -k "voice or acp"` if time.

**Do not:** log raw tokens/passwords; claim fleet production ready.

**First action:** Grep `_ingest_tool_call` in `voice_task.py`.

Open next: **F4**.

=== END PASTE ===

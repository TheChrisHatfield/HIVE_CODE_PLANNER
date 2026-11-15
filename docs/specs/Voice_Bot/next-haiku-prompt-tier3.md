=== PASTE INTO HAIKU ===

Voice_Bot **Tier 3 — full `agent` edit lane (beta)**. Repo: `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`. Python: `py -3.11`.

**Prerequisite:** Tiers 1–2 doc/pack hygiene in good shape (or proceed if only Tier 3 matters).

**This chat — one item: T3-u10-doc**  
Document the **residual** after U10 code:

1. Read `src/hive_planner/voice_task.py` `WRITE_COMMAND_RE` and `_is_write_call`.
2. Update `deployment-gaps.md` U10 paragraph: what is caught vs not (e.g. `python -c` open/write).
3. Add ≤3 sentences to `spec.md` § Deployment readiness residual notes OR deployment-gaps only (minimal spec touch).
4. No regex extension without a real ACP sample (doc-only this chat).

**Do not:** `live-write`; widen regex blindly; commit unless asked.

**Later:** T3-u11 logging → T3-u9 → T3-lane → T3-live (operator). See `haiku-polish-handoff.md`.

Do T3-u10-doc only. End with Continue block.

```
CONTINUE Voice_Bot
Last chat: <date>
Budget left: <low|unknown>
Verdict: polish-tier=3 item=T3-u10-doc
Done this chat: <bullets>
Open next: T3-u11 — toolCall.kind + redacted command on task evidence / live-write payload
Do not redo: U10 tests (9 pass)
Files changed: <paths>
Blocked: <or none>
First action: grep live-write / evidence / raw_events in voice_bot.py and voice_task.py
```

=== END PASTE ===

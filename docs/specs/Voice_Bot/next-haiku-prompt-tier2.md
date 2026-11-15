=== PASTE INTO HAIKU ===

Voice_Bot **Tier 2 — typed preview polish**. Repo: `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`. Python: `py -3.11`.

**Prerequisite:** Tier 1 T1-doc done (or deployment-gaps/spec already aligned).

**This chat — one item: T2-crosswalk**  
1. Read `docs/specs/Voice_Bot/acceptance-crosswalk.md` header (verified date + count).
2. Run once: `py -3.11 -m pytest tests -k "voice or acp" -q` and set header count/date from summary line.
3. If count unchanged, only refresh date if stale.

**Do not:** start T2-pack in same chat. No commit unless asked.

**Later:** T2-pack → T2-drift → T2-edh (optional note). See `haiku-polish-handoff.md`.

Do T2-crosswalk only. End with Continue block.

```
CONTINUE Voice_Bot
Last chat: <date>
Budget left: <low|unknown>
Verdict: polish-tier=2 item=T2-crosswalk
Done this chat: <bullets>
Open next: T2-pack — voice-bot pack + self_contained test assertions
Do not redo: crosswalk pytest run unless regressing
Files changed: <paths>
Blocked: <or none>
First action: py -3.11 -m hive_planner voice-bot pack; read tests/test_voice_bot_self_contained.py pack cases
```

=== END PASTE ===

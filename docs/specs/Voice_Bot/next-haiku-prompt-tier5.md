=== PASTE INTO HAIKU ===

Voice_Bot **Tier 5 — ops hardening**. Repo: `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`. Python: `py -3.11`.

**This chat — one item: T5-rss**  
1. Read `docs/specs/Voice_Bot/evidence-register.md` § T018 R24 (650 MB target, 770 outlier).  
2. Read `VoiceBotConfig` RSS fields in `src/hive_planner/voice_bot.py`.  
3. Either: (a) add register note “target tight, no change”, or (b) bump `agent_children_rss_target_mb` with test update — **operator policy in one sentence in deployment-gaps**.  
4. Run `py -3.11 -m pytest tests/test_voice_bot_resources.py -q` if config default changes.

**Do not:** full live R24 probe unless asked.

**Later:** T5-psutil → T5-flake → T5-maps. See `haiku-polish-handoff.md`.

Do T5-rss only. End with Continue block.

```
CONTINUE Voice_Bot
Last chat: <date>
Budget left: <low|unknown>
Verdict: polish-tier=5 item=T5-rss
Done this chat: <bullets>
Open next: T5-psutil — psutil dependency or documented optional for default_rss_mb
Do not redo: resources tests if no config change
Files changed: <paths>
Blocked: <or none>
First action: grep default_rss_mb psutil in voice_task.py and pyproject.toml
```

=== END PASTE ===

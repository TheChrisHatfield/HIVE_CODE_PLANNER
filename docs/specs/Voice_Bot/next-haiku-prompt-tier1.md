=== PASTE INTO HAIKU ===

Voice_Bot **Tier 1 — release integrity** (polish handoff). Repo: `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`. Python: `py -3.11`.

**This chat — one item only: T1-doc (U4b)**  
Sync deployment truth after U6/U10:

1. Read `docs/specs/Voice_Bot/deployment-gaps.md` (verdict table, gap F, status §, U6/U10 lines).
2. Read `docs/specs/Voice_Bot/spec.md` § Deployment readiness (first ~25 lines of that section).
3. Update: pytest baseline **386** passed (2 skipped); unguarded tests **9**; U10 `WRITE_COMMAND_RE` / `_is_write_call` one sentence; full-agent lane = operator-reviewed beta (not “production sealed”) unless you only fix factual errors.
4. Remove stale **327** / **8 pass** / **253** references in deployment-gaps.
5. Do **not** re-run full `voice or acp` unless you edited code (doc-only).
6. If you touch `spec.md`, run `py -3.11 -m hive_planner spec-drift-check --feature Voice_Bot` (emit only if drift fails).

**Do not:** commit; `edits_enabled`; live probes; `AGENTS.md`.

**Next tier items (later chats):** T1-u7 INSTALL STT story → T1-maps → T1-ci → T1-commit-prep. See `docs/specs/Voice_Bot/haiku-polish-handoff.md`.

Do T1-doc only. End with Continue block.

```
CONTINUE Voice_Bot
Last chat: <date>
Budget left: <low|unknown>
Verdict: polish-tier=1 item=T1-doc
G0–G6: unchanged unless you edited register
Done this chat: <bullets>
Open next: T1-u7 — STT install story in pack INSTALL.md generator
Do not redo: full pytest voice or acp unless code changed
Files changed: <paths>
Blocked: <or none>
First action: read src/hive_planner/voice_bot.py _voice_pack_install_md and deployment-gaps U7 paragraph
```

=== END PASTE ===

=== PASTE INTO HAIKU ===

Voice_Bot **closeout F2 — operator production checklist (docs)**. Repo: `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`. Python: `py -3.11`.

**Prerequisite:** F1 verdict sync done (or do minimal sync if missing).

**This chat — one micro-task only: F2**  
Add a short **operator checklist** (≤1 screen) for enabling full `agent` on a **single host**:

Create `docs/specs/Voice_Bot/operator-production-checklist.md` (or a named section in `deployment-gaps.md`) with checkboxes:

- G6 `pass` in `evidence-register.md` (live `live-permission --record`).
- `agent` logged in; CLI version pinned.
- U11b: `pytest tests/test_voice_bot_write_gate.py` green on that host.
- U10 residual read and accepted (`deployment-gaps.md` U10 caught/not caught).
- Optional: `voice-bot live-write --record` → R35 pass; file + nonce hash archived.
- Create `.hive/voice-bot/config.json` with `edits_enabled: true` **only after** above; document how to disable.
- RSS: note 650 MB target and review `r24.over_budget` rows.
- **Not fleet-wide:** other machines repeat checklist independently.

Link checklist from `spec.md` § Deployment readiness (one sentence + link). No behavior change.

**Do not:** auto-enable latch in pack/install scripts; commit unless operator asks.

**First action:** Read `evidence-register.md` R33 + R35 rows; outline checklist headers.

End with Continue block; Open next = F3 or C1 per operator priority (speech vs agent).

```
CONTINUE Voice_Bot
Last chat: <date>
Budget left: <low|unknown>
Verdict: full-agent=NOT READY until operator signs checklist on each host
Done this chat: <bullets>
Open next: C1 (speech criterion 4) OR F3 (toolCall logging)
Files changed: <paths>
Blocked: none
First action: <next item First action from haiku-closeout-handoff.md>
```

=== END PASTE ===

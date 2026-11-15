=== PASTE INTO HAIKU ===

Voice_Bot **Tier 4 — speech / G3**. Repo: `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`. Python: `py -3.11`.

**Operator choice (pick one path this chat):**

**Path A — T4-defer (recommended for preview polish):**  
1. Read `spec.md` § Speech I/O rollout and `tasks.md` T042.  
2. Add a short **Polish decision** paragraph to `deployment-gaps.md` gap A: S0 stays default; T042 remains partial; no G3 claim change.  
3. Optionally set tasks.md T042 note “deferred for preview ship” without checking the box done.

**Path B — T4-s1 (only if operator wants mic next):**  
1. Read evidence-register § T033-S1 and T042 criterion 4 list.  
2. One concrete step toward criterion 4 (gate test or register row) — no live mic unless operator says so.

**Do not:** claim spoken G3 pass; install faster-whisper on fleet without doc.

Do **Path A** unless the paste operator said Path B. End with Continue block.

```
CONTINUE Voice_Bot
Last chat: <date>
Budget left: <low|unknown>
Verdict: polish-tier=4 item=T4-defer|T4-s1
Done this chat: <bullets>
Open next: Tier 5 T5-rss OR T4-s1 if deferred
Do not redo: hybrid typed path tests
Files changed: <paths>
Blocked: <or none>
First action: read deployment-gaps gap A + spec Speech I/O rollout header
```

=== END PASTE ===

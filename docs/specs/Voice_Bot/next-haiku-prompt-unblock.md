=== PASTE INTO HAIKU ===

Voice_Bot **unblock closeout — F2 operator checklist + per-host latches (docs)**. Repo: `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`. Python: `py -3.11`.

**What stays blocked until closeout finishes**

| Blocker | Fix track | This chat |
|---|---|---|
| Spoken mic / G3 | Gap A → **C1–C4** after F2 | Not in this chat |
| Fleet-wide `agent` edits | Operator checklist + per-host `edits_enabled` | **F2 (this chat)** |
| Per-machine latches | Checklist + no pack auto-latch | **F2 (this chat)** |

**Verdict:** read-only=READY. speech=S0 `typed_instruction` (gap A open). full-agent=**NOT READY for production use** until a human signs the checklist **on each host**. Baseline: `pytest tests -k "voice or acp"` **389 passed**, 2 skipped; write gate **12/12**; U11b brokered writes green.

**Done (do not redo):** F1 per-host latch rule in `deployment-gaps.md`; `tasks.md` + `spec.md` say NOT READY fleet-wide; this host may have `edits_enabled: true` (operator only).

**This chat — one micro-task only: F2**  

1. Create `docs/specs/Voice_Bot/operator-production-checklist.md` (≤1 screen, markdown checkboxes) covering:
   - G6 `pass` in `evidence-register.md` (`voice-bot live-permission --record` on **this** host before enabling edits).
   - `agent` logged in; pin `agent --version` in the host notes.
   - `py -3.11 -m pytest tests/test_voice_bot_write_gate.py tests/test_voice_bot_unguarded_write.py -q` green on **this** host.
   - Operator read + initial on U10 residual (`deployment-gaps.md`: caught vs not caught, especially `python -c` / `node -e` writes).
   - Optional: `voice-bot live-write --record` → R35 pass; archive nonce hash (not raw nonce).
   - **Latch step:** create or edit `.hive/voice-bot/config.json` with `edits_enabled: true` **only after** all required boxes; document disable (`false` or remove key).
   - RSS: review `r24.over_budget` (`kind=rss`); 650 MB agent-children is tight (770 MB outlier recorded).
   - Explicit line: **no fleet-wide READY**; every other machine repeats this checklist independently.
   - **Sign-off block:** date, hostname, operator initials (blank until human fills).

2. Link the checklist from `spec.md` § Deployment readiness (one sentence + relative markdown link).

3. Add one sentence in `deployment-gaps.md` § Verdict by lane (full-agent row) pointing to the checklist file.

4. Tiny hygiene (same chat if quick): update `acceptance-crosswalk.md` L5 pytest count to **389 passed, 2 skipped** (2026-11-12 re-run). Trim the full-agent lane summary so it does not imply U11 is still an open blocker (U11b is shipped).

5. Run `py -3.11 -m hive_planner spec-drift-check --feature Voice_Bot`. If spec edited: `py -3.11 -m hive_planner emit --feature Voice_Bot --force-delta` once, then drift again.

**Do not:** set `edits_enabled: true` on other machines; claim spoken G3; implement STT/mic (that is **C1** next); change `voice_task.py`; commit unless operator asks.

**First action:** Read `evidence-register.md` R33, R35, G6; grep `edits_enabled` in `deployment-gaps.md`; draft checklist headers.

Do F2 only. End with a filled Continue block. Open next for gap A (speech): **C1**.

Every turn MUST end with:

```
CONTINUE Voice_Bot
Last chat: <date>
Budget left: <low|unknown>
Verdict: read-only=READY speech=S0 full-agent=NOT READY until checklist signed per host
G0–G6: unchanged unless you edited register
Done this chat: <1–3 bullets>
Open next: C1 — T042 criterion 4 STT pin gate (gap A spoken mic path)
Do not redo: 389 voice+acp; F1 latch paragraph; write gate 12
Files changed: <paths>
Blocked: live mic (C3/C4)
First action: grep hybrid_speech_path and test_voice_bot_gates in src and tests; read evidence-register § T033-S1
```

=== END PASTE ===

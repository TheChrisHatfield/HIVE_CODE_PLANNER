=== PASTE INTO HAIKU ===

Voice_Bot bug review — **Run 5 of 5** (final batch). Repo: D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER. Python: py -3.11.

**Batch 5** (6 items): areas **14–19**. One item per turn. When **19** is done → `Open next: review-complete` (optional T042 live-mic or Cursor `haiku continue` for summary).

Verdict: read-only=READY; full-agent=NOT READY.

**Done (do not redo):** Item **14** — bridge editor (`show_diff` traced; R18 schema on editor routes). Gap fix: `POST /v1/editor/navigate` added. `py -3.11 -m pytest tests/test_voice_bot_bridge.py -q` (65 passed); `py -3.11 -m pytest tests -q -k voice` (422 passed, 2 skipped).

**Blocked carry-over:** `POST /v1/editor/navigate` has no live EDH/voice caller yet (HTTP + tests only).

## Batch 5 — remaining

| Id | Spec | Target | Primary files / tests |
|----|------|--------|------------------------|
| 15 | R4, G2 | ACP reader loop, disconnect → unknown, stdout pump | `voice_acp.py`, acp integration tests |
| 16 | R2, G4 | Extension snapshot contract (Python side); EDH only if operator requests | bridge + extension protocol tests |
| 17 | R25 | Call end during pending approval: timeout still applies, no speech after end | `voice_task.py`, edges R25 tests |
| 18 | R30 | `voice-bot pack` / `ensure-runtime` / `status` wiring | `hive_planner` voice-bot CLI, `tests/test_voice_bot_self_contained.py` |
| 19 | US5, R16 | Feature Q&A from cartridge/spec without inventing requirements | grep voice_task + cartridge hooks; add test only if path exists |

First action: **15** — trace `voice_acp.py` reader loop; disconnect handling marks task **unknown**; stdout pump reaches runner updates.

Continue: `Review run: 5 of 5`; `Open next` = 16 | … | 19 | review-complete.

When review-complete: list any unfixed **Blocked** items across runs for operator.

Do **First action only** this turn; end with a filled **CONTINUE Voice_Bot** block (required shape in `docs/specs/Voice_Bot/haiku-100k-handoff.md`).

=== END PASTE ===

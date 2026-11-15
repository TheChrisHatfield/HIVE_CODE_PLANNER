# Voice_Bot — Haiku polish tiers (handoff)

**Use with:** `haiku handoff` / `haiku continue` and `py -3.11 scripts/haiku_handoff.py --continue-file <continue.txt>`.

**Rule:** One **tier item** per Haiku chat (not whole tier in one chat unless an item is doc-only and tiny). After each chat, paste the Continue block back to Cursor and say **haiku continue**, or run the script with the new Continue file.

**Headline target (operator picks one):** Preview = Tiers 1–2. Edit beta = + Tier 3. Full voice = + Tier 4. Ops-hardened = + Tier 5.

**Repo:** `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`. **Python:** `py -3.11`. **Do not:** flip `edits_enabled` on unfamiliar hosts; live `live-write` unless asked; promote product rules to `AGENTS.md`; commit unless asked.

**Baseline (2026-11-12):** `pytest tests -k "voice or acp"` → 386 passed, 2 skipped; extension `npm test` → 58/58; `spec-drift-check --feature Voice_Bot` ok; U6+U10 in `voice_task.py`; `tests/test_voice_bot_unguarded_write.py` (9 tests).

---

## Tier 1 — Release integrity (must-do)

**Continue seed:** `.hive/voice-bot/continue-polish-tier1.txt`  
**Paste file:** `docs/specs/Voice_Bot/next-haiku-prompt-tier1.md`

**Items (one per chat, in order):**  
1. **T1-doc** — U4b: `deployment-gaps.md` + `spec.md` § Deployment readiness (386 tests, 9 unguarded tests, U10 note, lane table sync; fix stale 327/8-pass lines).  
2. **T1-u7** — U7: STT in `INSTALL.md` via `_voice_pack_install_md` / pack generator (`[voice]` extra vs `ensure-runtime` / offline wheels).  
3. **T1-maps** — `impact-sync-maps` + curate only Voice-touched rows if `ci-check` fails on map drift.  
4. **T1-ci** — `py -3.11 -m hive_planner ci-check` (or document single failure class if out of scope).  
5. **T1-commit-prep** — List exact paths for a Voice-only commit (no launcher/bug-hunt); operator commits separately unless they asked.

---

## Tier 2 — Typed preview polish

**Continue seed:** `.hive/voice-bot/continue-polish-tier2.txt`  
**Paste file:** `docs/specs/Voice_Bot/next-haiku-prompt-tier2.md`

**Items:**  
1. **T2-crosswalk** — `acceptance-crosswalk.md` header date + re-measure pytest count if T1 changed tests.  
2. **T2-pack** — `voice-bot pack`; assert VSIX + `install-voice-bot.ps1` + INSTALL order (self_contained tests).  
3. **T2-drift** — After any spec edit: `emit --feature Voice_Bot --force-delta` + `spec-drift-check`.  
4. **T2-edh** (optional) — Note in `tasks.md` validation log only: EDH 16/18 re-run command; do not claim pass without operator run.

---

## Tier 3 — Full `agent` edit lane (beta)

**Continue seed:** `.hive/voice-bot/continue-polish-tier3.txt`  
**Paste file:** `docs/specs/Voice_Bot/next-haiku-prompt-tier3.md`

**Items:**  
1. **T3-u10-doc** — `deployment-gaps.md` U10 residual + spec one paragraph (regex heuristic; `python -c` open).  
2. **T3-u11** — Log `toolCall.kind` + redacted command on task evidence / `live-write-run.json` shape (code + test).  
3. **T3-u9** (optional) — Tighten `_has_unguarded_write` if command-only approval must not cover file write.  
4. **T3-lane** — Operator lane row in `evidence-register.md` or deployment-gaps: “full-agent beta approved” template (doc unless operator sets date).  
5. **T3-live** — Only if operator asks: `live-permission --record` note in validation log.

---

## Tier 4 — Speech / G3 (mic + audio)

**Continue seed:** `.hive/voice-bot/continue-polish-tier4.txt`  
**Paste file:** `docs/specs/Voice_Bot/next-haiku-prompt-tier4.md`

**Items:**  
1. **T4-defer** (default) — Spec status: lock S0 `typed_instruction`; close T042 checkbox only for “deferred” with evidence-register note — **or**  
2. **T4-s1** — T042 criterion 4: pin row, gate test, `stt_provider` claim (no live mic unless operator).  
3. **T4-audio** — Live evidence rows per spec § Speech I/O (STT pin, `audio: true`, R13 with audio).

---

## Tier 5 — Ops hardening

**Continue seed:** `.hive/voice-bot/continue-polish-tier5.txt`  
**Paste file:** `docs/specs/Voice_Bot/next-haiku-prompt-tier5.md`

**Items:**  
1. **T5-rss** — Document 650 MB agent-children target vs 770 outlier; optional config bump + register note.  
2. **T5-psutil** — Declare or document `psutil` for `default_rss_mb`.  
3. **T5-flake** — `test_live_feed_without_token_records_nothing` load flake: minimal fix or quarantine note in tasks.md.  
4. **T5-maps** — Final `impact-sync-maps` after Voice commit scope.

---

## After all tiers

Update `haiku-100k-handoff.md` § Prompt: polish queue **done** or next feature. Re-run deployment evaluation in Cursor.

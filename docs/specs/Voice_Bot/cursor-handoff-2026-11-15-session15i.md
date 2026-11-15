# Cursor handoff — Voice_Bot session 15i (2026-11-15)

Background: prior handoff `cursor-handoff-2026-11-15-session15h.md`. Session 15i: operator chose (3) full pytest, then (1) fix utterance/listen-gate conflict during live Moshi call (q8 single slot).

## Status

- **R37 q8 autostart:** still **PASS** (15e, commit `b707869`). 15g was operator confirmation only — **do not** rerun `autostart_gate_check.py` unless `scripts/moshi_q8_server.py` or `voice_moshi*` gate path changes.
- **Gap #1 (utterance vs listen gate):** **fixed** in code + spec (see below). **Not live-proven** on this host in 15i.
- **T056 live duplex:** still open (15f: audio out, no text / utterances 0 client-side where applicable).
- **Operator env:** Hive/launcher still do **not** set child env (unchanged from 15h).

## What changed (15i)

| Area | Change |
|------|--------|
| **Spec R37** | New bullet: live-call utterance skips `moshi_listen_gate` when bridge receives `moshi_live_call: true` (panel utterance path only). |
| **Panel** | `_on_moshi_utterance` → `_submit_recording(..., moshi_live_call=True)`; flag on `POST /v1/submit/spoken` and `/v1/reply/spoken`. WAV mic path unchanged (flag false). |
| **Bridge** | Optional `moshi_live_call` (bool) on `submit_spoken` and `reply_spoken` schemas; forwarded to runner. |
| **Runner** | `submit_spoken` / `reply_spoken`: `listen_code = None if moshi_live_call else moshi_listen_gate(...)`. STT and other gates unchanged. |

**Chain (fixed path):** Panel live call (`moshi_call_gate` + handover socket) → utterance WAV → bridge with `moshi_live_call: true` → runner transcribe + submit **without** second Moshi probe.

## Validation (15i)

| Check | Result |
|-------|--------|
| `pytest tests/test_voice_moshi.py` … `test_voice_moshi_server.py` (moshi + panel + bridge STT slice) | **192 passed** |
| `pytest tests -k "voice or acp" -q` (start of 15i, pre-fix) | **766 passed** (not re-run after fix — re-run before claiming full regression) |
| `autostart_gate_check.py` | **Not run** (no gate/launcher code change in 15i) |
| Live panel duplex + utterance → task on q8 | **Not run** |

**New tests:** `test_live_call_utterance_skips_listen_gate_only_when_flagged`; panel utterance test asserts `moshi_live_call is True`.

## Config / git (this host)

- `.hive/voice-bot/` remains **untracked** in git status unless you added it — q8 keys in `config.json` are **not** in version control until committed (15h assumed committed; **confirm** before next commit message).
- **Uncommitted Voice_Bot work from 15i** (6 files, ~68 lines): `spec.md`, `voice_bridge.py`, `voice_task.py`, `voice_panel_controller.py`, `test_voice_moshi.py`, `test_voice_panel_controller.py`.
- Repo has **many** unrelated modified/untracked files — commit Voice_Bot scope only; do not sweep bug-hunt, cartridge, Moshi_Tool_Lane, etc.

**Stub LLM:** still expected on **8009** (`moshi-q8-spike/llm_stub.py`); operator sets `LLM_BASE_URL` etc. (see 15h handoff block).

## Wiring audit

| Gap | Verdict |
|-----|---------|
| Utterance → `moshi_listen_gate` during live call | **Fixed in code**; validate with targeted tests (**done**); live step **deferred** |
| Operator env on child spawn | **Open** (optional item 5) |
| T056 live mic / transcript | **Open** |
| Full voice+acp regression after fix | **Re-run** `py -3.11 -m pytest tests -k "voice or acp" -q` before audit close |

**Closure (gap #1, partial):** traced panel → bridge → runner; gate skip is flag-gated; proven by unit tests; live q8 utterance-under-call not recorded.

## Do not redo

- Autostart gate reruns (unless q8 server / moshi gate code changes).
- Share-LM cache, streaming reset, `no_wait_stt_shutdown`, call-gate handover, 15 s connect timeout (R37 history).

## Suggested next (pick with operator)

1. **T056 live:** `voice-bot moshi-talk` or launcher mic with operator env + stub 8009; check `input_device`, speak 30–45 s; note transcript / `text_frames` / panel utterance → task.
2. **Re-run full suite:** `pytest -k "voice or acp"` after 15i patch; then close wiring audit in spec/tasks if live step done or explicitly waived.
3. **Commit:** Voice_Bot-only commit (spec R37 bullet + `moshi_live_call` wiring + tests); optionally `config.json` q8 keys + handoff md; impact packet under `docs/change-impact/impact-packets/` if policy requires.
4. **Child env:** wire PYTHONPATH / LLM_* into `MoshiServerProcess` spawn (spec + impact first).
5. **Impact packet** for 15i `src/` change if not already written.

**Rules:** Do not record G7 without real transcript/spoken reply. Do not sweep non–Voice_Bot files into a Voice_Bot commit.

---

## Paste into next chat

```
Voice_Bot session 15j. Read `docs/specs/Voice_Bot/cursor-handoff-2026-11-15-session15i.md` fully, then R37 in `docs/specs/Voice_Bot/spec.md` (including the live-call `moshi_live_call` bullet).

State: R37 q8 autostart PASS (15e, `b707869`) — do not rerun `autostart_gate_check.py` unless moshi_q8_server.py or voice_moshi* gate code changes. Session 15i fixed panel utterance vs listen-gate conflict: `moshi_live_call: true` skips `moshi_listen_gate` on `/v1/submit/spoken` and `/v1/reply/spoken` while a live call holds the slot (spec + bridge + runner + panel; tests 192 passed on moshi/panel slice; full voice+acp suite not re-run after fix). T056 live duplex still open. `.hive/voice-bot/config.json` q8 keys — confirm git tracked/untracked before commit.

Ask me what to do next: (1) T056 live mic + moshi-talk/panel, (2) re-run full pytest voice/acp and close wiring audit, (3) Voice_Bot-only commit (+ optional impact packet), (4) child env wiring, (5) something else. Do not record G7 without real transcript/spoken reply. Do not sweep non–Voice_Bot files into a Voice_Bot commit.
```
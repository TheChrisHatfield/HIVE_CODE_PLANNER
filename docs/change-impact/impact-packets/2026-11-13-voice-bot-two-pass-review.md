# Impact packet: Voice_Bot two-pass code review, pass 2 (2026-11-13)

**Feature:** Voice_Bot
**Hooks:** `change.impact`, `change.validation`, `integration.wiring_audit`
**Predecessor:** pass 1 fixes (see `docs/specs/Voice_Bot/two-pass-code-review-handoff.md`)

## Change in this pass

| File | Change |
|---|---|
| `extensions/hive-voice-bot/src/core.js` | New `createTimerRegistry(clear)` (add / release / stopAll / size), exported |
| `extensions/hive-voice-bot/src/extension.js` | `followTask` timers tracked in `taskFollowers`; released on terminal, timeout, and lookup failure; `stopAll()` in `stopBridge()` and `clearIfCurrent()` |
| `extensions/hive-voice-bot/package.json` | `npm test` now includes `test/code-review-2026-11-13.test.js` |
| `extensions/hive-voice-bot/test/code-review-2026-11-13.test.js` | +2 tests for the registry (stopAll, release) |
| `docs/specs/Voice_Bot/tasks.md` | Validation log entry for pass 2 |

No Python `src/` change in pass 2. No spec text change. No `edits_enabled` or R33 latch change.

## Defect fixed

`followTask` polled `GET /v1/task` every second. On a network error, `taskPollDecision` only stopped at the 15-minute deadline. After `stopBridge()`, the poll kept hitting a dead bridge and then reported a misleading "still running; stopped waiting" error. Timers are now tracked and cleared when the bridge stops or exits.

## Directly affected tests

- `extensions/hive-voice-bot/test/code-review-2026-11-13.test.js` (registry)
- `extensions/hive-voice-bot/test/core.test.js`, `bridge-client.test.js`, `review-fixes.test.js`, `review-cascade.test.js` (module loads and the poll decision)
- `tests/test_voice_bot_code_review_2026_11_13.py` (pass 1)

## Downstream impact

- Interface: none. `followTask` and `stopBridge` keep their signatures. `createTimerRegistry` is additive.
- Host: a bridge stop now ends in-flight task polls immediately. Previously they lingered up to 15 minutes.
- Not checked live: the real Extension Development Host. The registry is pure and tested. `extension.js` wiring is verified by `node --check` and by reading the call sites.

## Secondary and tertiary effects

- `wav_path` chain (bridge `relpath` → `submit_spoken` → `_resolve_file` → STT): traced, no change needed. Existing `tests/test_voice_stt_runtime.py::test_wav_path_outside_workspace_is_refused_before_transcribing` covers `../escape.wav`.
- Spec drift: `emit --feature Voice_Bot --force-delta` then `spec-drift-check --feature Voice_Bot` returned `ok=true`, no drift items, no spec actions.

## Validation

- `npm test` (extensions/hive-voice-bot): 70 pass, 0 fail
- `node --check` on `src/extension.js` and `src/core.js`: ok
- `py -3.11 -m pytest tests/test_voice_bot_code_review_2026_11_13.py -q`: 9 passed
- `py -3.11 -m pytest tests -k "voice or acp" -q`: 523 passed, 2 skipped
- `spec-drift-check --feature Voice_Bot`: ok=true

## Spec and memory flags

- Spec: no change required. R22, R23, and R6 behavior is unchanged.
- Memory: nothing promoted to `AGENTS.md`.

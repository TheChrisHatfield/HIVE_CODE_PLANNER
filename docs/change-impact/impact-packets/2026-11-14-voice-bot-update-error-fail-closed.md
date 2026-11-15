# Impact packet: Voice_Bot dropped ACP update fails closed (2026-11-14)

**Feature:** Voice_Bot
**Hooks:** `change.impact`, `change.validation`, `integration.wiring_audit`

## Defect

`VoiceTaskRunner._apply_notification` caught every exception from `_on_update` and returned silently.
If the handler failed while recording a write (for example, while counting a `write_events` entry), the write was
never counted. `_has_unguarded_write` then saw no write, and `_finish` reported `completed` (`end_turn`). That is a
false success under R8 and R22.

## Change

| File | Change |
|---|---|
| `src/hive_planner/voice_task.py` | `_apply_notification` calls `_note_update_error` on failure. That appends an `update.error` event to the active task. `_finish` on `end_turn` fails the task with `evidence_error` when `_has_update_error` is true. |
| `tests/test_voice_bot_update_errors.py` | New integrated test: real submit through the fake ACP child, with `_record_write_event` forced to raise. It failed before the fix (`completed`) and passes after. |

## Downstream impact

- Interface: none. No HTTP route, schema, or config change.
- New task reason `evidence_error` (failed). It is a terminal failure reason, so the bridge maps it to the existing 200/task-view path. The spoken text for a failed task is the generic failure path. The spec does not list this reason; it is a new value under R8/R22 and should be named in the spec if a reason table is later added.
- Behavior: a turn whose ACP update raised during recording now fails instead of completing. It is stricter on purpose. Cost: a benign malformed update can now fail a turn that used to pass.
- Disconnect, timeout, and cancel paths are unchanged. The check runs only on `end_turn`.

## Directly affected tests

- `tests/test_voice_bot_update_errors.py` (new, 1 test)
- `tests/test_voice_bot_unguarded_write.py` (73 total with the new file and `test_voice_bot_nn_cascade.py`, all passing)

## Validation

- Before fix: `tests/test_voice_bot_update_errors.py` failed (`completed` != `failed`).
- After fix: `py -3.11 -m pytest tests/test_voice_bot_update_errors.py tests/test_voice_bot_unguarded_write.py tests/test_voice_bot_nn_cascade.py -q` → 73 passed.
- After fix: `py -3.11 -m pytest tests -k "voice or acp" -q` → 545 passed, 2 skipped (baseline before the change: 544 passed, 2 skipped).

## Not checked

- Live ACP run: the path is exercised only by the fake child fixture. The live `agent acp` never drops an update in
  these tests, so this is not live evidence.
- Spec text and `spec-drift-check` were not re-run: `spec.md` was not changed.

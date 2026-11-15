# Impact packet: Moshi call worker fixes in the voice panel (2026-11-15)

**Feature:** Voice_Bot (parent), Moshi_Tool_Lane
**Hooks:** `change.impact`, `change.validation`, `integration.wiring_audit`
**Spec:** R36, R37 (T056 call loop, T042 panel wiring)

## Defect

Three faults in `VoicePanelController`'s Moshi call path:

1. Stop pressed while the listen gate was still waiting (cold server start) let the worker open audio devices after the user had stopped.
2. A call that ended on its own (socket drop, device fault) left `mic_active` true, so the panel kept showing "listening" with no notice.
3. `_on_moshi_text` ran one HTTP `GET /v1/approval` per Moshi text frame on the receive thread, stalling audio decoding behind each round trip.

## Change

| File | Change |
|---|---|
| `src/hive_planner/launcher/voice_panel_controller.py` | Stop check after the gate and before `talk()`. Worker `finally` clears `mic_active` and adds a notice for an unrequested error (not for a gate refusal, not for a user stop). `PENDING_POLL_TTL_S = 0.5` memo via `_cached_pending_approval`; memo cleared only on terminal reply statuses. |
| `tests/test_voice_panel_controller.py` | New: `test_stop_during_listen_gate_never_opens_the_call`, `test_dropped_call_clears_listening_and_reports_the_error`, `test_pending_approval_poll_is_memoised_across_text_frames`. Loopback test waits for `fake_io.opened` before stop. |

## Downstream impact

- Interface: none. No HTTP route, config key, or spec text changed.
- Behavior: a stop during the gate never opens devices. A dropped call shows a notice and the mic turns off. Approval replies can lag by up to 0.5 s on the Moshi text path (the memo).
- Typed Whisper approval path and the R37 gate are unchanged.

## Directly affected tests

- `tests/test_voice_panel_controller.py` (59 passed, targeted run 2026-11-15)
- `tests/test_voice_panel_task_watch.py`, `tests/test_voice_mic_recorder.py`, `tests/test_voice_panel.py`, `tests/test_voice_moshi_conversation.py`, `tests/test_voice_moshi.py`

## Validation

- `py -3.11 -m pytest tests/test_voice_panel_controller.py -q` → 59 passed.
- `py -3.11 -m pytest tests -k "voice or acp or launcher" -q` → 1137 passed, 2 warnings (about 6 min, post-fix run).

## Not checked

- Live microphone, live speaker, live Moshi server (G7 / T055 / ML-T5 still open).
- The 0.5 s memo under a real Moshi stream.

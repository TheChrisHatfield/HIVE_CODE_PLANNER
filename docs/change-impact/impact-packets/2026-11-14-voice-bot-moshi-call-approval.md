# Impact packet: Moshi call-mode spoken approval (2026-11-14)

**Feature:** Voice_Bot (parent), Moshi_Tool_Lane
**Hooks:** `change.impact`, `change.validation`, `integration.wiring_audit`, `agent.permissions`
**Spec:** R6, R36, R37

## Defect

Spoken approval only worked on the typed Whisper path (`voice_layer=typed` and `stt_provider=faster-whisper`). The shipped default is Moshi duplex: the mic never writes a WAV, and Moshi `0x02` text stayed transcript-only, so a yes/no during a live call could not resolve a pending R6 request.

## Change

| File | Change |
|---|---|
| `docs/specs/Voice_Bot/spec.md` | R36: Moshi `0x02` text may reply to a pending approval via `POST /v1/reply`. R37 listen gate does not run on that path. |
| `src/hive_planner/voice_moshi.py` | `MoshiConversation` takes `on_text`. A true return consumes the frame as an approval reply. Else a pending tool-lane approval uses `reply`. `talk` / `run_conversation` forward `on_text`. |
| `src/hive_planner/launcher/voice_panel_controller.py` | Live Moshi call passes `_on_moshi_text`. Pending GET `/v1/approval` then POST `/v1/reply`. No WAV, no `stt_provider`. |
| Tests | Conversation, panel, tool-lane exec, runner (default Moshi, `stt_provider` null). |

## Downstream impact

- Interface: no new HTTP route. Moshi call-mode uses existing `POST /v1/reply`.
- Behavior: default Moshi call can approve by voice. Moshi text still cannot create a task and is not evidence (WER gate unchanged).
- Typed Whisper `/v1/reply/spoken` is unchanged.
- Moshi_Tool_Lane: a pending lane approval now receives the next `0x02` line through `MoshiToolBroker.reply`.

## Directly affected tests

- `tests/test_voice_moshi_conversation.py`
- `tests/test_voice_panel_controller.py`
- `tests/test_voice_moshi_lane_exec.py`
- `tests/test_voice_reply_spoken.py`

## Validation

- `py -3.11 -m pytest tests/test_voice_reply_spoken.py tests/test_voice_moshi_conversation.py tests/test_voice_panel_controller.py tests/test_voice_moshi_lane_exec.py -q` → 92 passed
- `py -3.11 -m pytest tests -k "voice or acp or moshi" -q` → 708 passed, 2 skipped
- `emit --feature Voice_Bot --force-delta` then `spec-drift-check --feature Voice_Bot` → ok (tasks.md had one invalid Windows-1252 byte in an older T056 note; replaced)

## Not checked

- Live microphone, live faster-whisper model, live `moshi.server` (G7 / T055 / ML-T5 still open).

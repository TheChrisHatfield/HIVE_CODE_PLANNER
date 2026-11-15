# Impact packet — Voice_Bot 10-layer code-review cascade (2026-11-11)

**Primary:** `src/hive_planner/voice_task.py` (`reply_approval`, `_live_buffer_at_reply`), `src/hive_planner/voice_bridge.py` (`POST /v1/reply` `editor_snapshot`), `extensions/hive-voice-bot/src/core.js`, `extensions/hive-voice-bot/src/extension.js`

**Tests:** `tests/test_voice_bot_nn_cascade.py`, `tests/test_voice_bot_bridge.py`, `tests/test_voice_bot_safety.py`, `extensions/hive-voice-bot/test/review-fixes.test.js`, `extensions/hive-voice-bot/test/bridge-client.test.js`

**Spec:** R6 (do not claim timeout after a local approve/deny), R22 (write approval compares live editor version/dirty captured at reply time).

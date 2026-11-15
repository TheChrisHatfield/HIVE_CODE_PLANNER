# Impact packet — Voice_Bot unguarded writes and spoken snapshot

**Primary:** `src/hive_planner/voice_task.py` (empty toolCallId kind merge, drain after disconnect, unguarded_write on every finish outcome, spoken `editor_snapshot`), `src/hive_planner/voice_bridge.py` (spoken schema), `extensions/hive-voice-bot/src/core.js` / `src/extension.js`

**Secondary:** `tests/fixtures/acp_turn_server.py` (`WRITE_EMPTY_ID_UNGUARDED`, `WRITE_THEN_CRASH`)

**Tests:** `tests/test_voice_bot_unguarded_write.py`, `tests/test_voice_stt_runtime.py`, `tests/test_voice_bot_bridge.py`, `extensions/hive-voice-bot/test/bridge-client.test.js`

**Spec:** Voice_Bot R22 unguarded write, R2 editor snapshot on submit (typed and spoken)

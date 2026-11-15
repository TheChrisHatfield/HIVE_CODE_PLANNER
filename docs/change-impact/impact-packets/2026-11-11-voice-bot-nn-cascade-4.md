# Impact packet — Voice_Bot 10-loop code-review cascade (2026-11-11, pass 4)

**Primary:** `src/hive_planner/voice_task.py` (write-approval file identity, cancel/reply after close, approval view `file_path`), `extensions/hive-voice-bot/src/core.js` (`pickLiveDocumentRelative`), `extensions/hive-voice-bot/src/extension.js` (capture bound file at reply)

**Tests:** `tests/test_voice_bot_nn_cascade.py`, `tests/test_voice_bot_bridge.py`, `extensions/hive-voice-bot/test/review-fixes.test.js`

**Spec:** R22 (live buffer is the bound snapshot file), R9 (cancel after close must not report success without a save).

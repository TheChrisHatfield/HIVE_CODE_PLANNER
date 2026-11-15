# Impact packet — Voice_Bot 10-layer code-review cascade

**Primary:** `src/hive_planner/voice_bot.py`, `src/hive_planner/voice_task.py`, `src/hive_planner/voice_bridge.py`, `extensions/hive-voice-bot/src/core.js`, `extensions/hive-voice-bot/src/extension.js`

**Tests:** `tests/test_voice_bot_nn_cascade.py`, `tests/test_voice_bot_safety.py`, `tests/test_voice_bot_queue.py`, `tests/test_voice_bot_cascade_review.py`, `extensions/hive-voice-bot/test/review-fixes.test.js`

**Spec:** R2/R28 (no disk refill of excluded snapshots), R9 (no submit/save after close), R5/R6/R21 (spoken notice on queue_full, agent_mode_disabled, instruction_too_long), R18 (retry editor navigate until it opens).

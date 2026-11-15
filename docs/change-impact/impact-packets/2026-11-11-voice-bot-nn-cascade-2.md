# Impact packet — Voice_Bot 10-loop code-review cascade (2026-11-11, pass 2)

**Primary:** `extensions/hive-voice-bot/src/core.js` (`approvalReplySettlesHost`), `extensions/hive-voice-bot/src/extension.js` (approval poll + submit refused UX), `src/hive_planner/voice_task.py` (stale submit spoken), `src/hive_planner/voice_bridge.py` (`run_turn_via_bridge` spoken on refuse)

**Tests:** `extensions/hive-voice-bot/test/review-fixes.test.js`, `tests/test_voice_bot_cascade_review.py`, `tests/test_voice_bot_bridge.py`

**Spec:** R6 (approval modal must retry after dismiss or reprompt), R22 (stale buffer spoken at submit and approval).

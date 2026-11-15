# Impact packet — Voice_Bot 10-loop code-review cascade (2026-11-11, pass 3)

**Primary:** `src/hive_planner/voice_task.py` (`_require_active_session` spoken), `extensions/hive-voice-bot/src/core.js` (`approvalReplySpokenNotice`, `approvalReplySettlesHost` stale), `extensions/hive-voice-bot/src/extension.js` (approval reply UX)

**Tests:** `tests/test_voice_bot_bridge.py`, `tests/test_voice_bot_nn_cascade.py`, `extensions/hive-voice-bot/test/review-fixes.test.js`

**Spec:** R6 (host surfaces bridge spoken on non-failure replies), R9/R25 (`session_not_active` voice notice on bridge submit).

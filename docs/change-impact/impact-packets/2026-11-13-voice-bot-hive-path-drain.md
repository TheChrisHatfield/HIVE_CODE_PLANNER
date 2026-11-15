# Impact packet — Voice_Bot hive-path fence and oversize POST drain

**Primary:** `src/hive_planner/voice_task.py` (`_resolve_file` refuses `.hive/`), `src/hive_planner/voice_bot.py` (snapshot refill skips `.hive/`), `src/hive_planner/voice_bridge.py` (drain oversize POST bodies), `extensions/hive-voice-bot/src/core.js` / `src/extension.js` (task poll retries a network error until the deadline)

**Secondary:** none

**Tests:** `tests/test_voice_bot_security.py`, `tests/test_voice_bot_bridge.py`, `extensions/hive-voice-bot/test/review-fixes.test.js`

**Spec:** Voice_Bot R23 path checks, R21 body cap, R8/R14 task poll

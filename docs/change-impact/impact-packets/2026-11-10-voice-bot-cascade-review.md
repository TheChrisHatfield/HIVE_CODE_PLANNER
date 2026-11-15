# Impact packet — Voice_Bot 4-loop code review fixes

**Primary:** `src/hive_planner/voice_task.py`, `src/hive_planner/voice_bot.py`, `src/hive_planner/voice_bridge.py`

**Tests:** `tests/test_voice_bot_cascade_review.py`, `tests/test_voice_bot_safety.py`, `tests/test_voice_bot_review_fixes.py`, `tests/test_voice_bot_security.py`, `tests/test_voice_bot_loop_review.py`

**Spec:** R7/R20 (finish after terminal cancel), R9 (close stops timer writes), R22 (stale check at submit), R23 (workspace bind uses realpath + normcase).

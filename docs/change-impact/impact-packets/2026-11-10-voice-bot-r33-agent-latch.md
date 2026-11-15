# Impact packet — Voice_Bot R33 agent latch wiring

**Primary:** `src/hive_planner/voice_task.py`, `src/hive_planner/voice_bot.py`, `src/hive_planner/voice_bridge.py`, `extensions/hive-voice-bot/src/core.js`, `extensions/hive-voice-bot/src/extension.js`

**Tests:** `tests/test_voice_bot_gates.py`, `tests/test_voice_bot_edges.py`, `tests/test_voice_bot_bridge.py`, `extensions/hive-voice-bot/test/core.test.js`

**Spec:** R33 — `agent` mode is allowed only when G6 register is `pass` and config `edits_enabled` is true. R23 — host navigate stays inside the bound workspace.

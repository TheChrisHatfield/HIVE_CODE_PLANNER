# Impact packet — Voice_Bot 10-loop code-review cascade (2026-11-11, L5)

**Primary:** `src/hive_planner/voice_task.py` (`_handle_server_request`, `_ensure_session` initialize), `extensions/hive-voice-bot/src/core.js` (`resolveHivePlannerSrc`), `extensions/hive-voice-bot/src/extension.js` (Start Bridge PYTHONPATH)

**Tests:** `tests/test_voice_bot_nn_cascade.py`, `extensions/hive-voice-bot/test/review-fixes.test.js`

**Spec:** T004/T006 live ACP turn (G2 `fs/read` client method), R23 path bound for that read, T027 writes stay JSON-RPC errors, T017/R30 Start Bridge must find `hive_planner`.

**Secondary:** `src/hive_planner/voice_bot.py` unchanged (`_read_workspace_text` reused). No spec text change.

**Downstream:** Ask-mode ACP sessions advertise read-only `fs`. Start Bridge prepends `<workspace>/src` to PYTHONPATH when `src/hive_planner` exists and the setting is empty.

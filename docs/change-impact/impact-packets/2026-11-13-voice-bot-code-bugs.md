# Impact packet — Voice_Bot code bugs (read leak, ACP reader, write gate, reconnect, STT)

**Primary:** `src/hive_planner/voice_bot.py` (`_read_workspace_text` refuses `.hive/`), `src/hive_planner/voice_acp.py` (null JSON-RPC code, poison-line reader, close wait), `src/hive_planner/voice_task.py` (write regex, empty toolCallId, pump params, reconnect slot, fs write errors), `src/hive_planner/voice_bridge.py` (POST path query), `src/hive_planner/voice_stt.py` (wrap transcribe errors)

**Secondary:** bridge 409 `task_slot_occupied`

**Tests:** `tests/test_voice_bot_nn_cascade.py`, `tests/test_voice_acp.py`, `tests/test_voice_bot_unguarded_write.py`, `tests/test_voice_bot_bridge.py`, `tests/test_voice_bot_delegation.py`, `tests/test_voice_stt.py`, `tests/test_voice_bot_review_fixes.py`

**Spec:** Voice_Bot R23 path checks, R20 disconnect, U10/U6 write counting, R26 reconnect, T042 STT

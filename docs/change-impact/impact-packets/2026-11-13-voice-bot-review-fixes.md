# Impact packet — Voice_Bot review fixes (ACP close, execute-update writes, empty STT, panel teardown)

**Primary:** `src/hive_planner/voice_acp.py` (close fails pending RPCs; one disconnect sentinel)

**Secondary:** `src/hive_planner/voice_task.py` (tool_call_update kind/command; empty STT), `src/hive_planner/launcher/voice_panel.py` (mic toggle after destroy)

**Tests:** `tests/test_voice_acp.py`, `tests/test_voice_bot_unguarded_write.py`, `tests/test_voice_stt_runtime.py`, `tests/test_voice_panel.py`

**Spec:** Voice_Bot R20 disconnect, U10/U6 write counting, T042 spoken submit, launcher visual shell.

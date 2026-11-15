# Impact packet — Voice_Bot 10-loop code-review cascade (2026-11-11, pass 6, L5)

**Primary:** `src/hive_planner/voice_task.py` (`_ensure_session`, `_launch`)

**Tests:** `tests/test_voice_bot_nn_cascade.py` (`test_close_during_acp_handshake_kills_unassigned_child`)

**Spec:** R9 shutdown must not duplicate work. Stop Bridge (`runner.close`) during ACP initialize left `agent acp` running because `_client` was still None.

**Secondary:** `close()` unchanged for an assigned client. `_abandon_provider` still only kills `_client`. No spec text change.

**Downstream:** A handshake child is terminated when `_closed` is set before assign. `_launch` does not start `_run_prompt` after close. The next Start Bridge can take the runner lock.

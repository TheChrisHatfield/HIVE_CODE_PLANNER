# Impact packet — Voice_Bot follow-up keeps excluded snapshots

**Primary:** `src/hive_planner/voice_task.py` (`queue_follow_up`)

**Tests:** `tests/test_voice_bot_queue.py`

**Spec:** R2/R28 — a follow-up must carry the active snapshot's `excluded` flag and empty payload so dispatch does not refill secrets from disk.

**Secondary:** `_dispatch_next` → `_new_task` → `create_context_snapshot` → `_prompt_text` (ACP prompt). No bridge schema change.

**Tertiary:** extension poll path unchanged; follow-ups still use `queue_follow_up` on the runner.

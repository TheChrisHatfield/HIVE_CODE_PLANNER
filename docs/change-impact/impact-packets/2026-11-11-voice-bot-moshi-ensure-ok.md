# Impact packet — Voice_Bot Moshi ensure-runtime false success

**Primary:** `src/hive_planner/voice_bot.py` (`ensure_voice_runtime`)

**Secondary:** `src/hive_planner/cli.py` (exits 0/1 from `result.ok`; unchanged)

**Tests:** `tests/test_voice_bot_self_contained.py`

**Spec:** R30 — a failed Moshi install is recorded; `voice-bot ensure-runtime --install` must not report `ok` when pip exits 0 but `moshi` / `pipecat` still cannot be imported.

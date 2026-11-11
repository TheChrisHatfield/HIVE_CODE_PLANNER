# Impact packet — Voice_Bot R30 self-contained deploy

**Primary:** `src/hive_planner/voice_bot.py`, `docs/specs/Voice_Bot/spec.md`

**Secondary:** `docs/specs/Voice_Bot/tasks.md`, `docs/specs/Voice_Bot/plan.md`, `docs/delta/20_micro/Voice_Bot.md`, `src/hive_planner/cli.py`, `pyproject.toml` (`voice` extra; core `dependencies` stay empty)

**Tests:** `tests/test_voice_bot_self_contained.py`, `tests/test_voice_bot.py`

**Spec:** R30, SC-014, AC 22. Hive `voice` extra declares Moshi and Pipecat; `voice-bot pack` writes a portable deploy folder; `voice-bot ensure-runtime --install` pip-installs them; Cursor CLI uses the official installer.

=== PASTE INTO HAIKU ===

Voice_Bot **closeout C2 — U7 STT install story in deploy pack**. Repo: `D:\DRIVE_DOWNLOADS\HIVE_CODE_PLANNER`. Python: `py -3.11`.

**Prerequisite:** C1 criterion-4 gate done (or proceed if only install docs matter).

**This chat — one micro-task: C2**  
Fix **dead-config / operator confusion**: `pip install -e ".[voice]"` includes faster-whisper pins but `voice-bot ensure-runtime` and offline `wheels/` do not.

1. Read `src/hive_planner/voice_bot.py` — `VOICE_STACK_PYPI`, `_voice_pack_install_md`, `build_voice_deploy_pack`, `ensure-runtime`.
2. Read `pyproject.toml` `[project.optional-dependencies] voice`.
3. Update generated `INSTALL.md` text so step order explains: Moshi/Pipecat via ensure-runtime; **STT optional** via full `[voice]` extra or explicit pip line for faster-whisper pins; offline pack limitation.
4. Add/adjust test in `tests/test_voice_bot_self_contained.py` asserting INSTALL mentions STT (string assert, minimal).
5. `pytest tests/test_voice_bot_self_contained.py -q`; `voice-bot pack` dry layout if cheap.

**Do not:** claim spoken G3; download large models in CI; change ensure-runtime to install whisper without operator decision (doc-first; optional code flag only if spec allows).

**First action:** Grep `_voice_pack_install_md` and `VOICE_STACK_PYPI` in `voice_bot.py`.

Continue block; Open next: **C3** extension spoken caller.

=== END PASTE ===

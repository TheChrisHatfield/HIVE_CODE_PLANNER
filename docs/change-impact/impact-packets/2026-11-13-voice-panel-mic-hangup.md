# Impact packet — Voice panel mic glyph and hang-up

**Primary:** `src/hive_planner/launcher/voice_panel.py` (capsule mic + U cradle, listening ring, red hang-up)

**Secondary:** none in `src/` beyond the panel. Launcher `app.py` packing unchanged; mic/end-call stay presentation-only.

**Tests:** `tests/test_voice_panel.py` (`test_mic_glyph_is_narrow_capsule_with_u_cradle`, `test_hangup_is_red_with_white_x`)

**Spec:** Voice_Bot launcher visual shell.

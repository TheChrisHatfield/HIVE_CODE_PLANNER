# Impact packet — Voice panel launcher import and destroy

**Primary:** `src/hive_planner/launcher/app.py` (`PANEL_WIDTH`, `VoicePanel` import)

**Secondary:** `src/hive_planner/launcher/voice_panel.py` (header bind, destroy filter, animation guard)

**Tests:** `tests/test_voice_panel.py`

**Spec:** Voice_Bot visual shell in the desktop launcher. Mic/end-call remain presentation-only; this packet restores constructability, single-timer animation, teardown-safe handlers, and destroy cancel.

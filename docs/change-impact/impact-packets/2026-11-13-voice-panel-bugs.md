# Impact packet — Voice panel teardown, reentry, and size

**Primary:** `src/hive_planner/launcher/voice_panel.py` (end-call reentry, toggle/refresh desync, destroy identity, content height, hang-up vs mic, TclError from `on_end`)

**Secondary:** none in `src/` beyond the panel. Launcher `app.py` still packs the panel `fill=y`; intrinsic height only matters when that stretch is absent.

**Tests:** `tests/test_voice_panel.py`

**Spec:** Voice_Bot launcher visual shell. Mic/end-call remain presentation-only.

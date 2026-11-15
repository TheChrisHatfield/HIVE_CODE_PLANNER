# Impact packet — Voice panel tall layout, wheel sink, hang-up packing

**Primary:** `src/hive_planner/launcher/voice_panel.py` (body spacers for fill=y, mouse-wheel sink, hang-up packed before expanding mic, hang-up fill uses border)

**Secondary:** launcher `app.py` still packs the panel `fill=y`; no callback wiring change (mic/end stay presentation-only)

**Tests:** `tests/test_voice_panel.py`

**Spec:** Voice_Bot launcher visual shell.

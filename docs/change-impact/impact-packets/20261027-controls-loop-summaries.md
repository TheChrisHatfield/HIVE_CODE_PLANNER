# Impact packet — Controls loop summaries

**Date:** 2026-10-27  
**Spec:** `docs/specs/hive-desktop-v1/spec.md` R3

## Change

The Controls heading lists one plain-language line for Bug hunt, CodeSpec, and Agnostic loop, above the note about blocks and the active repo. Hover text on each Controls button, command, and setting is one plain sentence about what it does. The Command tip updates when the selected command changes.

## Primary

- `src/hive_planner/launcher/app.py` (`LOOP_SUMMARIES`, `_controls_active_caption`)

## Secondary

- `docs/specs/hive-desktop-v1/spec.md`, `docs/delta/20_micro/hive-desktop-v1.md`

## Tests

- `tests/test_launcher.py` — `test_controls_caption_summarizes_each_loop`

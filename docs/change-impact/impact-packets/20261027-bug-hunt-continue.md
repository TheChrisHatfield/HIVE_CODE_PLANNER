# Impact packet: bug-hunt continue hook

**Date:** 2026-10-27
**Feature:** bug-hunt

## Change

Ending a hunt turn writes `.hive/bug-hunt/continue.json`. The stop hook `.cursor/hooks/bug_hunt_continue.py` consumes it, waits `pause_seconds` (`0` does not wait), and returns `followup_message` so the next turn is the next iteration. Stop conditions write `active: false`. Step 4 no longer says to pause or to keep the hunt open. Enable with the default Fix ceiling writes a 50-fix cap.

## Wiring

Script instruction → `continue.json` → `stop` hook → `apply_continue` → wait → `followup_message`. Enable → `install_bug_hunt` → hook file + `hooks.json` entry. Other hook events stay.

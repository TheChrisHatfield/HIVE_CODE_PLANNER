# Impact packet — Home action groups

**Date:** 2026-10-27  
**Spec:** `docs/specs/hive-desktop-v1/spec.md` Home

## Change

Home command buttons sit in titled groups. **Arrange groups** (Home or Settings) lets the user rename headings and move groups or buttons. Layout is stored in launcher `config.json`.

## Primary

- `src/hive_planner/launcher/home_groups.py`
- `src/hive_planner/launcher/app.py`
- `src/hive_planner/launcher/config.py`

## Secondary

- `docs/specs/hive-desktop-v1/spec.md`, `docs/delta/20_micro/hive-desktop-v1.md`
- `scripts/README.md`

## Tests

- `tests/test_home_groups.py`
- `tests/test_launcher.py` (Loop controls / CodeSpec labels still present)

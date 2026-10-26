# Implementation loop checker

Python owns this pass. Run `py -3.11 -m hive_planner implementation-loop check` (or Home **Loop check**). Do not re-run the gates by hand unless `check` is missing.

`check` runs `build` and `test:quick` from `.hive/implementation-loop/commands.json`, then the wiring audit when the project enforces it, and appends the checker `result.md` entry. You do not edit product code. You do not commit.

Do not edit `AGENTS.md`. Do not commit.

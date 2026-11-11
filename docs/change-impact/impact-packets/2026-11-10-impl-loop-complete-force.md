# Impact packet — implementation-loop complete start needs force-feature

**Primary:** `src/hive_planner/implementation_loop.py` (`coordinator_start`)

**Tests:** `tests/test_implementation_loop_coordinator.py`

**Spec:** A different running feature blocks `start` unless `--force-feature`. The complete-feature shortcut used to run first and rewrite `state.json` without that flag.

**Secondary:** CLI `implementation-loop start` and Controls Start share this function. Overlap gate stays earlier and unchanged.

**Tertiary:** same-feature complete reports still skip force-feature.

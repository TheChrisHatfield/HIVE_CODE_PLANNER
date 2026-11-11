# Impact packet — hive_notify dashed --body/--title/--seconds

**Primary:** `src/hive_planner/vendor_templates/continual-learning/hooks/hive_notify.py`

**Tests:** `tests/test_notify.py`

**Spec / behavior:** Values for `--title`, `--body`, `--seconds`, and `--repo` may start with a dash. argparse treated those tokens as flags, so the popup never showed (same class as the existing dashed `--repo` heading fix).

**Secondary:** `src/hive_planner/notify.py` still spawns this script with a token list; a dashed body now survives in the child. The installed plugin copy is a separate location.

**Tertiary:** stop-hook notice text does not start with a dash; CLI and `notify()` can.

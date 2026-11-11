"""Controls Execute with no linked project must not keep a prior sent label."""

from __future__ import annotations

from hive_planner.launcher.app import HivePlannerApp


def test_controls_execute_without_link_reports_failed_not_sent() -> None:
    shown: list[str] = []
    inst = {"execute_outcome": object()}

    class Stub:
        def _require_active_link(self):
            return None

        def _show_execute_outcome(self, block, outcome):
            shown.append(outcome)
            assert block is inst

    HivePlannerApp._on_controls_execute(Stub(), inst)
    assert shown == ["failed"]

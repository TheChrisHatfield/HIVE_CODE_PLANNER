from __future__ import annotations

from hive_planner.launcher.app import HivePlannerApp
from hive_planner.runtime_paths import APP_DISPLAY_NAME


def test_dialog_applies_hive_icon(monkeypatch) -> None:
    seen: list[object] = []

    class _Top:
        def __init__(self, master) -> None:
            self.master = master

    monkeypatch.setattr("hive_planner.launcher.app.tk.Toplevel", _Top)
    monkeypatch.setattr("hive_planner.launcher.app.apply_app_icon", lambda window: seen.append(window))
    monkeypatch.setattr("hive_planner.launcher.app.remember_popup", lambda _window: None)
    app = HivePlannerApp.__new__(HivePlannerApp)
    app.root = object()
    dialog = app._dialog()
    assert isinstance(dialog, _Top)
    assert seen == [dialog]


def test_app_display_name_is_hive_capitalized() -> None:
    assert APP_DISPLAY_NAME == "HIVE Planner"

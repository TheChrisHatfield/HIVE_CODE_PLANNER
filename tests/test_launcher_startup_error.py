from __future__ import annotations

import pytest

from hive_planner.launcher.__main__ import _show_startup_error


def test_startup_error_is_printed_when_the_dialog_cannot_open(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import tkinter

    def _no_display() -> None:
        raise RuntimeError("no display")

    monkeypatch.setattr(tkinter, "Tk", _no_display)

    with pytest.raises(SystemExit) as caught:
        _show_startup_error("Could not install hive-planner.", "pip failed")

    assert caught.value.code == 1
    err = capsys.readouterr().err
    assert "Could not install hive-planner." in err
    assert "pip failed" in err

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.launcher import __main__ as main_mod
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


def test_ensure_installed_accepts_pip_success_without_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = tmp_path / "hive"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='hive-planner'\n", encoding="utf-8")
    monkeypatch.setattr(main_mod, "_repo_root", lambda: repo)
    monkeypatch.setattr(main_mod, "_package_installed", lambda: False)
    monkeypatch.setattr(
        main_mod.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})(),
    )
    monkeypatch.setattr(
        main_mod,
        "_show_startup_error",
        lambda msg, detail="": (_ for _ in ()).throw(AssertionError("should not error")),
    )
    main_mod.ensure_installed()


def test_ensure_installed_shows_error_when_pip_cannot_start(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = tmp_path / "hive"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='hive-planner'\n", encoding="utf-8")
    monkeypatch.setattr(main_mod, "_repo_root", lambda: repo)
    monkeypatch.setattr(main_mod, "_package_installed", lambda: False)
    monkeypatch.setattr(
        main_mod.subprocess,
        "run",
        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("python.exe")),
    )
    shown: list[tuple[str, str]] = []

    def _capture(msg: str, detail: str = "") -> None:
        shown.append((msg, detail))
        raise SystemExit(1)

    monkeypatch.setattr(main_mod, "_show_startup_error", _capture)
    with pytest.raises(SystemExit):
        main_mod.ensure_installed()
    assert shown == [("Could not install hive-planner.", "python.exe")]

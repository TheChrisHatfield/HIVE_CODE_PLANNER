"""Open in Explorer returns an error when the launcher cannot start."""

from __future__ import annotations

from pathlib import Path

import pytest

from hive_planner.launcher.service import open_path_in_explorer


def test_open_path_in_explorer_reports_launch_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(*_args, **_kwargs):
        raise OSError("explorer is unavailable")

    monkeypatch.setattr("hive_planner.launcher.service.subprocess.Popen", _fail)
    result = open_path_in_explorer(tmp_path)
    assert result["ok"] is False
    assert "unavailable" in result["error"]


def test_open_path_in_explorer_starts_the_existing_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def _ok(argv, **kwargs):
        seen["argv"] = argv
        seen["shell"] = kwargs.get("shell")
        return object()

    monkeypatch.setattr("hive_planner.launcher.service.subprocess.Popen", _ok)
    result = open_path_in_explorer(tmp_path)
    assert result["ok"] is True
    assert result["path"] == str(tmp_path.resolve())
    assert seen["shell"] is False
    assert seen["argv"][-1] == str(tmp_path.resolve())

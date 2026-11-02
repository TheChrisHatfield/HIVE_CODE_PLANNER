from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hive_planner.launcher.service import _cursor_from_logs


def test_cursor_log_scan_skips_a_log_behind_a_junction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    appdata = tmp_path / "appdata"
    logs = appdata / "Cursor" / "logs"
    logs.mkdir(parents=True)
    local_root = tmp_path / "local" / "cursor" / "app"
    local_root.mkdir(parents=True)
    (local_root / "Cursor.exe").write_bytes(b"local")
    outside_root = tmp_path / "outside" / "cursor" / "other"
    outside_root.mkdir(parents=True)
    (outside_root / "Cursor.exe").write_bytes(b"out")
    (logs / "session.log").write_text(
        f"{local_root}\\resources\\app\n",
        encoding="utf-8",
    )
    outside = tmp_path / "outside-logs"
    outside.mkdir()
    secret = outside / "secret.log"
    secret.write_text(f"{outside_root}\\resources\\app\n", encoding="utf-8")
    link = logs / "jump"
    created = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
        capture_output=True,
        text=True,
    )
    if created.returncode != 0:
        pytest.skip("directory junction is not permitted")
    secret.touch()

    monkeypatch.setenv("APPDATA", str(appdata))

    assert _cursor_from_logs() == str(local_root / "Cursor.exe")

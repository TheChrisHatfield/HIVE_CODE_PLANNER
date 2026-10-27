"""Desktop notice stays out of the chat transcript."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from hive_planner.notify import MEMORY_CHECK_BODY, NOTICE_TITLE, notify, notifier_script


def test_notify_dry_run_records_without_a_window(tmp_path: Path, monkeypatch) -> None:
    log = tmp_path / "notice.json"
    monkeypatch.setenv("HIVE_NOTIFY_DRY_RUN", "1")
    monkeypatch.setenv("HIVE_NOTIFY_LOG", str(log))
    assert notify("Hive Planner", "Hello from any IDE.")
    payload = json.loads(log.read_text(encoding="utf-8"))
    assert payload == {"ok": True, "title": "Hive Planner", "body": "Hello from any IDE."}


def test_notify_returns_false_when_the_process_exits(tmp_path: Path) -> None:
    bad = tmp_path / "hive_notify.py"
    bad.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    assert notify("Hive Planner", "Hello", script=bad) is False


def test_immediate_clean_exit_is_not_a_shown_notice(tmp_path: Path) -> None:
    bad = tmp_path / "hive_notify.py"
    bad.write_text("raise SystemExit(0)\n", encoding="utf-8")
    assert notify("Hive Planner", "Hello", script=bad) is False


def test_module_main_names_a_missing_script(tmp_path: Path, monkeypatch, capsys) -> None:
    from hive_planner.notify import main

    monkeypatch.setattr("hive_planner.notify.notifier_script", lambda: tmp_path / "missing.py")
    assert main(["--body", "x"]) == 1
    assert "missing" in capsys.readouterr().err


def test_module_main_names_an_early_exit(tmp_path: Path, monkeypatch, capsys) -> None:
    from hive_planner.notify import main

    bad = tmp_path / "hive_notify.py"
    bad.write_text("raise SystemExit(0)\n", encoding="utf-8")
    monkeypatch.setattr("hive_planner.notify.notifier_script", lambda: bad)
    assert main(["--body", "x"]) == 1
    err = capsys.readouterr().err
    assert "stayed open" in err
    assert "missing" not in err


def test_notify_cli_dry_run(tmp_path: Path) -> None:
    log = tmp_path / "notice.json"
    env = os.environ.copy()
    env["HIVE_NOTIFY_DRY_RUN"] = "1"
    env["HIVE_NOTIFY_LOG"] = str(log)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "hive_planner",
            "notify",
            "--title",
            NOTICE_TITLE,
            "--body",
            MEMORY_CHECK_BODY,
        ],
        text=True,
        capture_output=True,
        cwd=str(tmp_path),
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is True
    assert "You did not type this" in json.loads(log.read_text(encoding="utf-8"))["body"]
    assert notifier_script().is_file()

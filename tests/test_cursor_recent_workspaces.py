import json
import sqlite3
from pathlib import Path

from hive_planner.launcher.service import discover_cursor_workspaces


def _write_state_db(db: Path, entries: dict) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE ItemTable (key TEXT UNIQUE ON CONFLICT REPLACE, value BLOB)")
    conn.execute(
        "INSERT INTO ItemTable (key, value) VALUES (?, ?)",
        ("history.recentlyOpenedPathsList", json.dumps(entries).encode("utf-8")),
    )
    conn.commit()
    conn.close()


def test_discover_cursor_workspaces_reads_while_state_db_is_locked(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path / "my-repo"
    repo.mkdir()
    db = tmp_path / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    _write_state_db(db, {"entries": [{"folderUri": repo.as_uri()}]})
    monkeypatch.setenv("APPDATA", str(tmp_path))

    locked = sqlite3.connect(db)
    locked.execute("BEGIN EXCLUSIVE")
    try:
        workspaces = discover_cursor_workspaces()
    finally:
        locked.close()

    assert [item.path for item in workspaces] == [str(repo.resolve())]

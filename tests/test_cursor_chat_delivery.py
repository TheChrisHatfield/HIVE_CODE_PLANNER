"""Cursor chat delivery: headers, scope, and request/result outcomes."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hive_planner.launcher.chat_target import execute_controls, outcome_text
from hive_planner.launcher.cursor_chat_delivery import CursorChatTarget
from hive_planner.launcher.cursor_submitter import apply_request


def _db(path: Path, rows: list[tuple], disks: list[tuple] | None = None) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE composerHeaders (
            composerId TEXT,
            workspaceId TEXT,
            createdAt INTEGER,
            lastUpdatedAt INTEGER,
            isArchived INTEGER,
            isSubagent INTEGER,
            value TEXT
        )
        """
    )
    conn.execute("CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
    conn.executemany(
        "INSERT INTO composerHeaders VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    for key, value in disks or []:
        conn.execute("INSERT INTO cursorDiskKV VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def _storage(root: Path, workspace_id: str, folder: Path) -> Path:
    slot = root / workspace_id
    slot.mkdir(parents=True)
    uri = folder.resolve().as_uri()
    (slot / "workspace.json").write_text(json.dumps({"folder": uri}), encoding="utf-8")
    return root


def _install(repo: Path, phrase: str = "bug hunt") -> None:
    name = {
        "bug hunt": "bug-hunt.md",
        "code spec": "implementation-loop.md",
        "agnostic loop": "agnostic-loop.md",
    }[phrase]
    path = repo / ".cursor" / "commands" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("loop\n", encoding="utf-8")


def _header(composer_id: str, workspace: str, stamp: int, name: str, *, archived: int = 0, subagent: int = 0, draft: bool = False) -> tuple:
    return (
        composer_id,
        workspace,
        1,
        stamp,
        archived,
        subagent,
        json.dumps({"name": name, "isDraft": draft}),
    )


def _target(db: Path, storage: Path, **kwargs) -> CursorChatTarget:
    kwargs.setdefault("timeout", 0.4)
    return CursorChatTarget(db_path=db, storage_root=storage, **kwargs)


def _mark_generating(db: Path, composer_id: str) -> None:
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT OR REPLACE INTO cursorDiskKV VALUES (?, ?)",
        (f"composerData:{composer_id}", json.dumps({"status": "generating"})),
    )
    conn.commit()
    conn.close()


def test_duplicate_titles_use_later_update(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _install(repo)
    db = tmp_path / "state.vscdb"
    storage = _storage(tmp_path / "ws", "ws-a", repo)
    _db(
        db,
        [
            _header("old", "ws-a", 10, "Hive face"),
            _header("new", "ws-a", 20, "Hive face"),
            _header("other-window", "ws-b", 99, "Hive face"),
        ],
    )
    seen: dict[str, str] = {}

    def on_request(path: Path) -> None:
        request = json.loads(path.read_text(encoding="utf-8"))
        seen["id"] = request["composerId"]
        seen["phrase"] = request["phrase"]
        _mark_generating(db, request["composerId"])
        apply_request(repo, lambda composer_id, phrase: None)

    outcome = _target(db, storage, on_request=on_request).deliver("  hive face  ", repo, "bug hunt")
    assert outcome == "sent"
    assert seen == {"id": "new", "phrase": "bug hunt"}


def test_unknown_title_and_blank_are_not_found(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _install(repo)
    db = tmp_path / "state.vscdb"
    storage = _storage(tmp_path / "ws", "ws-a", repo)
    _db(db, [_header("one", "ws-a", 5, "Hive face")])
    target = _target(db, storage)
    assert target.deliver("missing", repo, "bug hunt") == "not_found"
    assert target.deliver("   ", repo, "bug hunt") == "not_found"
    assert not (repo / ".hive" / "controls-execute" / "request.json").exists()


def test_draft_and_missing_command_are_refused(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    db = tmp_path / "state.vscdb"
    storage = _storage(tmp_path / "ws", "ws-a", repo)
    _db(
        db,
        [
            _header("draft", "ws-a", 30, "Hive face", draft=True),
            _header("older", "ws-a", 10, "Hive face"),
        ],
    )
    assert _target(db, storage).deliver("Hive face", repo, "bug hunt") == "refused"
    bare = tmp_path / "bare"
    bare.mkdir()
    storage2 = _storage(tmp_path / "ws2", "ws-b", bare)
    _db(tmp_path / "other.vscdb", [_header("live", "ws-b", 5, "Other")])
    assert _target(tmp_path / "other.vscdb", storage2).deliver("Other", bare, "code spec") == "refused"


def test_tie_is_failed_and_does_not_submit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _install(repo)
    db = tmp_path / "state.vscdb"
    storage = _storage(tmp_path / "ws", "ws-a", repo)
    _db(db, [_header("a", "ws-a", 8, "Same"), _header("b", "ws-a", 8, "Same")])
    assert _target(db, storage).deliver("Same", repo, "bug hunt") == "failed"
    assert not (repo / ".hive" / "controls-execute" / "request.json").exists()


def test_already_generating_skips_submit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _install(repo)
    db = tmp_path / "state.vscdb"
    storage = _storage(tmp_path / "ws", "ws-a", repo)
    _db(
        db,
        [_header("busy", "ws-a", 4, "Hive face")],
        [( "composerData:busy", json.dumps({"status": "generating"}) )],
    )
    assert _target(db, storage).deliver("Hive face", repo, "bug hunt") == "already_generating"
    assert not (repo / ".hive" / "controls-execute" / "request.json").exists()

    idle_db = tmp_path / "idle.vscdb"
    _db(idle_db, [_header("idle", "ws-a", 4, "Hive face")])
    state = repo / ".hive" / "bug-hunt"
    state.mkdir(parents=True)
    (state / "continue.json").write_text(json.dumps({"active": True}), encoding="utf-8")
    assert _target(idle_db, storage).deliver("Hive face", repo, "bug hunt") == "already_generating"
    assert not (repo / ".hive" / "controls-execute" / "request.json").exists()


def test_archived_and_other_workspace_do_not_win(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _install(repo)
    db = tmp_path / "state.vscdb"
    storage = _storage(tmp_path / "ws", "ws-a", repo)
    _db(
        db,
        [
            _header("arch", "ws-a", 50, "Hive face", archived=1),
            _header("sub", "ws-a", 40, "Hive face", subagent=1),
            _header("elsewhere", "ws-z", 90, "Hive face"),
        ],
    )
    assert _target(db, storage).deliver("Hive face", repo, "bug hunt") == "not_found"


def test_sent_without_generating_status_is_failed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _install(repo, "agnostic loop")
    db = tmp_path / "state.vscdb"
    storage = _storage(tmp_path / "ws", "ws-a", repo)
    _db(db, [_header("id", "ws-a", 3, "Chat")])

    def on_request(path: Path) -> None:
        apply_request(repo, lambda composer_id, phrase: None)

    assert _target(db, storage, on_request=on_request).deliver("Chat", repo, "agnostic loop") == "failed"


def test_no_result_is_failed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _install(repo, "code spec")
    db = tmp_path / "state.vscdb"
    storage = _storage(tmp_path / "ws", "ws-a", repo)
    _db(db, [_header("id", "ws-a", 3, "Chat")])
    assert _target(db, storage, timeout=0.05).deliver("Chat", repo, "code spec") == "failed"


def test_phrase_map_ignores_command_and_fake_adapter() -> None:
    class Fake:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def deliver(self, name: str, repo: Path, phrase: str) -> str:
            self.calls.append((name, phrase))
            return "not_found"

    fake = Fake()
    repo = Path("repo")
    assert execute_controls("Bug hunt", "Tab", repo, fake) == "not_found"
    assert execute_controls("CodeSpec", "Tab", repo, fake) == "not_found"
    assert execute_controls("Agnostic loop", "Tab", repo, fake) == "not_found"
    assert fake.calls == [
        ("Tab", "bug hunt"),
        ("Tab", "code spec"),
        ("Tab", "agnostic loop"),
    ]
    assert outcome_text("not_found") == "not found"
    assert outcome_text("sent") != outcome_text("failed")
    assert outcome_text("already_generating") == "already generating"


def test_execute_handler_does_not_read_the_database_or_run_a_gate() -> None:
    source = Path(__file__).resolve().parents[1] / "src" / "hive_planner" / "launcher" / "app.py"
    text = source.read_text(encoding="utf-8")
    body = text.split("def _on_controls_execute", 1)[1].split("\n    def ", 1)[0]
    assert "state.vscdb" not in body
    assert "submitChatMaybeAbortCurrent" not in body
    assert "run_project_" not in body
    assert "execute_controls" in body
    assert '"Execute"' in text
    assert "impl_allow_overlap" in text
    assert "Allow overlap" in text

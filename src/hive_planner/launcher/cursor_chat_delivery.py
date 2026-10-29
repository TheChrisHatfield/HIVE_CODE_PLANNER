"""Resolve a Cursor composer header and ask the in-workbench submitter to send a phrase.

This module reads ``composerHeaders`` read-only. It writes
``.hive/controls-execute/request.json`` and waits for ``result.json``. It does
not call ``submitChatMaybeAbortCurrent`` and it does not open the desktop bridge.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from hive_planner.launcher.cursor_submitter import REQUEST_REL, RESULT_REL
from hive_planner.launcher.service import resolve_linked_project_root

PHRASE_COMMANDS = {
    "bug hunt": ".cursor/commands/bug-hunt.md",
    "code spec": ".cursor/commands/implementation-loop.md",
    "agnostic loop": ".cursor/commands/agnostic-loop.md",
}

_WAIT_SECONDS = 10.0
_POLL_SECONDS = 0.1


def _same_path(left: Path, right: Path) -> bool:
    a = os.path.normcase(str(left))
    b = os.path.normcase(str(right))
    return a == b


def _uri_to_path(uri: str) -> Path | None:
    text = (uri or "").strip()
    if not text:
        return None
    if text.startswith("file:"):
        parsed = urlparse(text)
        raw = unquote(parsed.path or "")
        if os.name == "nt" and raw.startswith("/") and len(raw) > 2 and raw[2] == ":":
            raw = raw[1:]
        if not raw:
            return None
        return Path(raw)
    return Path(text)


def _workspace_folder(workspace_json: Path) -> Path | None:
    try:
        data = json.loads(workspace_json.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    folder_uri = data.get("folder")
    if isinstance(folder_uri, str) and folder_uri.strip():
        folder = _uri_to_path(folder_uri)
        if folder is None:
            return None
        if folder.suffix.lower() == ".code-workspace":
            return resolve_linked_project_root(folder)
        return folder
    workspace_uri = data.get("workspace")
    if isinstance(workspace_uri, str) and workspace_uri.strip():
        workspace = _uri_to_path(workspace_uri)
        if workspace is None:
            return None
        return resolve_linked_project_root(workspace)
    return None


def workspace_id_for_repo(repo: Path, storage_root: Path) -> str | None:
    """Return the workspaceStorage id whose folder is the active repo."""
    if not storage_root.is_dir():
        return None
    target = repo.resolve()
    for child in storage_root.iterdir():
        if not child.is_dir():
            continue
        meta = child / "workspace.json"
        if not meta.is_file():
            continue
        folder = _workspace_folder(meta)
        if folder is None:
            continue
        try:
            resolved = folder.resolve()
        except OSError:
            resolved = folder
        if _same_path(resolved, target):
            return child.name
    return None


def _cursor_user_dir() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "Cursor" / "User"


def _open_ro(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)


def _truthy(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes"}
    return bool(value)


def _header_name(value: object) -> tuple[str, bool]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return "", False
    if not isinstance(value, dict):
        return "", False
    name = value.get("name")
    title = name.strip() if isinstance(name, str) else ""
    return title, _truthy(value.get("isDraft"))


def _titles_match(typed: str, title: str) -> bool:
    left = typed.strip()
    right = title.strip()
    if not left or not right:
        return False
    return left.casefold() == right.casefold()


def _loop_in_progress(repo: Path, phrase: str) -> bool:
    if phrase == "bug hunt":
        path = repo / ".hive" / "bug-hunt" / "continue.json"
        key = "active"
        want = True
    elif phrase == "code spec":
        path = repo / ".hive" / "implementation-loop" / "state.json"
        key = "status"
        want = "running"
    elif phrase == "agnostic loop":
        path = repo / ".hive" / "agnostic-loop" / "state.json"
        key = "status"
        want = "running"
    else:
        return False
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    return data.get(key) == want


def _command_missing(repo: Path, phrase: str) -> bool:
    rel = PHRASE_COMMANDS.get(phrase)
    if rel is None:
        return True
    return not (repo / rel).is_file()


def _composer_status(db_path: Path, composer_id: str) -> str:
    conn = _open_ro(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM cursorDiskKV WHERE key = ?",
            (f"composerData:{composer_id}",),
        ).fetchone()
    except sqlite3.Error:
        return ""
    finally:
        conn.close()
    if row is None or row[0] is None:
        return ""
    raw = row[0]
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    status = data.get("status")
    return status.strip() if isinstance(status, str) else ""


def _stamp(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _select_header(rows: list[tuple[str, object, bool]]) -> tuple[str, str]:
    """Return (composer_id, outcome-or-empty). Empty outcome means a single winner."""
    if not rows:
        return "", "not_found"
    latest = max(_stamp(item[1]) for item in rows)
    winners = [item for item in rows if _stamp(item[1]) == latest]
    if len(winners) != 1:
        return "", "failed"
    composer_id, _updated, draft = winners[0]
    if draft:
        return composer_id, "refused"
    return composer_id, ""


class CursorChatTarget:
    """Cursor adapter. Tests pass a database, storage root, and request hook."""

    def __init__(
        self,
        *,
        db_path: Path | None = None,
        storage_root: Path | None = None,
        on_request=None,
        timeout: float = _WAIT_SECONDS,
    ) -> None:
        user = _cursor_user_dir()
        if db_path is None and user is not None:
            db_path = user / "globalStorage" / "state.vscdb"
        if storage_root is None and user is not None:
            storage_root = user / "workspaceStorage"
        self.db_path = db_path
        self.storage_root = storage_root
        self.on_request = on_request
        self.timeout = timeout

    def deliver(self, name: str, repo: Path, phrase: str) -> str:
        try:
            return self._deliver(name, repo, phrase)
        except (OSError, sqlite3.Error, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            return "failed"

    def _deliver(self, name: str, repo: Path, phrase: str) -> str:
        if phrase not in PHRASE_COMMANDS:
            return "failed"
        if self.db_path is None or self.storage_root is None or not self.db_path.is_file():
            return "failed"
        workspace_id = workspace_id_for_repo(repo, self.storage_root)
        if not workspace_id:
            return "not_found"
        conn = _open_ro(self.db_path)
        try:
            queried = conn.execute(
                """
                SELECT composerId, lastUpdatedAt, isArchived, isSubagent, value
                FROM composerHeaders
                WHERE workspaceId = ?
                """,
                (workspace_id,),
            ).fetchall()
        finally:
            conn.close()
        matches: list[tuple[str, object, bool]] = []
        for composer_id, stamp, archived, subagent, value in queried:
            if _truthy(archived) or _truthy(subagent):
                continue
            title, draft = _header_name(value)
            if not _titles_match(name, title):
                continue
            matches.append((str(composer_id), stamp, draft))
        composer_id, early = _select_header(matches)
        if early:
            return early
        if _command_missing(repo, phrase) or _loop_in_progress(repo, phrase):
            if _command_missing(repo, phrase):
                return "refused"
            return "already_generating"
        if _composer_status(self.db_path, composer_id) == "generating":
            return "already_generating"
        nonce = uuid.uuid4().hex
        request = {"nonce": nonce, "composerId": composer_id, "phrase": phrase}
        request_path = repo / REQUEST_REL
        result_path = repo / RESULT_REL
        request_path.parent.mkdir(parents=True, exist_ok=True)
        if result_path.is_file():
            result_path.unlink()
        request_path.write_text(json.dumps(request), encoding="utf-8")
        if self.on_request is not None:
            self.on_request(request_path)
        outcome = self._wait_result(result_path, nonce)
        if outcome != "sent":
            return "failed"
        if _composer_status(self.db_path, composer_id) != "generating":
            return "failed"
        return "sent"

    def _wait_result(self, result_path: Path, nonce: str) -> str:
        deadline = time.monotonic() + self.timeout
        while True:
            if result_path.is_file():
                try:
                    payload = json.loads(result_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    payload = None
                if isinstance(payload, dict) and payload.get("nonce") == nonce:
                    outcome = payload.get("outcome")
                    if outcome in {"sent", "failed"}:
                        return str(outcome)
                    return "failed"
            if time.monotonic() >= deadline:
                return "failed"
            time.sleep(min(_POLL_SECONDS, max(0.0, deadline - time.monotonic())))

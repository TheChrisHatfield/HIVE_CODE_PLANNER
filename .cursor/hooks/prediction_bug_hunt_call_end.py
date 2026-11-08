"""Ad hoc call-end capture for composer tabs in this repo.

Not installed by bootstrap. Cursor runs this on sessionEnd (the composer
closed) and on stop. A stop with status completed is the hang-up Cursor
sends, and it writes. A stop with status aborted or error writes too.

beforeSubmitPrompt recall matches a scripted phrase and reads the memory file.
It does not look up a composer, a tab name, or a workspace id. Call-end writes
still use the composer id on the hook payload, looked up in composerHeaders
for a workspace slot of this repo. The capture reads that composer's latest
voice call in Cursor's state database (`glass.realtimeVoice`), the store the
view-transcript button opens. It does not read the agent jsonl. Stdout is
always JSON. A missing id, another workspace, a subagent, or no stored voice
call does not write the memory file.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

MEMORY_REL = Path("docs/specs/bug-hunt/TEMP-prediction-memory.md")
MAX_BULLET_CHARS = 240
CAPTURE_START = "<!-- call-end-capture:start -->"
CAPTURE_END = "<!-- call-end-capture:end -->"
_ID_KEYS = ("conversation_id", "composerId", "composer_id", "session_id")
_COMPOSER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_DROP_STATUSES = {"aborted", "error", "cancelled", "canceled"}
_CONTEXT_LIMIT = 10000
_QUERY = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.DOTALL)
_SCOPE_BODY = (
    "Ad hoc, not permanent. Scope is any composer tab in this repo, not only "
    "`PREDICTION_BUG_HUNT`. A call in this repo, including an automatic drop, "
    "updates `docs/specs/bug-hunt/TEMP-prediction-memory.md`."
)

SKELETON = """# Temporary prediction memory

Ad hoc file for any composer tab in this repo. Not applied to `AGENTS.md`.
Continual-memory shape: plain `- ` bullets, `## Learned User Preferences` for working style, `## Durable Workspace Facts` for operational facts (`# operational`), and a behavioral section that must not be written into `AGENTS.md`. A bullet stays at or under 240 characters.

## Learned User Preferences

## Durable Workspace Facts

## Design memory (behavioral — do not merge into AGENTS.md)

"""


def call_end_reason(payload: object) -> str:
    """Empty when this invocation should write. Otherwise the skip reason.

    sessionEnd is the composer closing (user_close, window_close, or a drop).
    stop with status completed is the hang-up Cursor actually sends. A stop
    with status aborted, error, or cancelled is a dropped turn and also writes.
    """
    if not isinstance(payload, dict):
        return "not_call_end"
    event = str(payload.get("hook_event_name") or "").strip().casefold()
    status = str(payload.get("status") or "").strip().casefold()
    if event == "sessionend":
        return ""
    if event == "stop" and status == "completed":
        return ""
    if event == "stop" or status:
        if status in _DROP_STATUSES:
            return ""
        return "turn_completed"
    return "not_call_end"


def composer_id_from_payload(payload: object) -> str:
    """Composer id Cursor puts on sessionEnd and stop.

    conversation_id is that id. session_id is only a fallback, and only when
    it is a single path segment so it cannot escape the transcript directory.
    """
    if not isinstance(payload, dict):
        return ""
    for key in _ID_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and _COMPOSER_ID.fullmatch(value.strip()):
            return value.strip()
    return ""


def project_slug(repo: Path) -> str:
    """Cursor project-folder slug: non-alphanumerics become single hyphens."""
    text = str(Path(repo))
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")


def _within(path: Path, root: Path) -> bool:
    """True when path resolves inside root. A junction or symlink outside does not."""
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def transcript_dir_for(repo: Path, composer_id: str, projects_root: Path) -> Path | None:
    """Transcript folder for this repo slug and composer id.

    A slug hit that has no transcript directory is a miss. Another project's
    folder is not a substitute. A directory that resolves outside that
    project's agent-transcripts folder is not a substitute either.
    """
    if not composer_id or not projects_root.is_dir():
        return None
    slug = project_slug(repo).casefold()
    for child in projects_root.iterdir():
        if not child.is_dir() or child.name.casefold() != slug:
            continue
        transcripts = child / "agent-transcripts"
        candidate = transcripts / composer_id
        if not candidate.is_dir() or not _within(candidate, transcripts):
            return None
        return candidate
    return None


def _bullet(body: str) -> str:
    text = " ".join(body.split())
    prefix = "- "
    room = MAX_BULLET_CHARS - len(prefix)
    if len(text) > room:
        text = text[: room - 1].rstrip() + "…"
    return prefix + text


def scope_bullet() -> str:
    return _bullet(_SCOPE_BODY)


def repo_workspace_ids(repo: Path, storage_root: Path) -> list[str]:
    """Workspace slots whose folder is this repo, same lookup as chat delivery."""
    hooks_dir = Path(__file__).resolve().parent
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    from _bootstrap import bootstrap_hive_planner

    bootstrap_hive_planner()
    from hive_planner.launcher.cursor_chat_delivery import workspace_ids_for_repo

    return workspace_ids_for_repo(repo, storage_root)


def header_title(
    db_path: Path,
    composer_id: str,
    workspace_ids: list[str] | tuple[str, ...],
) -> tuple[str, str]:
    """Return (stored title, status) for this composer in this repo.

    The title is the ``name`` field in the header, read the same way as
    ``cursor_chat_delivery._header_name``. Status is `ok` for any non-subagent
    header in one of ``workspace_ids``, including a tab opened after install.
    `missing` is an unknown id or a subagent. `other_workspace` is a composer
    that belongs to a different folder. Database failures return `db_error`.
    """
    if not composer_id:
        return "", "missing"
    allowed = {item.strip().casefold() for item in workspace_ids if item and item.strip()}
    if not allowed:
        return "", "workspace_missing"
    if not db_path.is_file():
        return "", "db_missing"
    hooks_dir = Path(__file__).resolve().parent
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    from _bootstrap import bootstrap_hive_planner

    bootstrap_hive_planner()
    from hive_planner.launcher.cursor_chat_delivery import (
        _decode_saved_text,
        _header_name,
        _open_ro,
        _truthy,
    )

    try:
        conn = _open_ro(db_path)
        try:
            try:
                conn.execute("PRAGMA busy_timeout=3000")
            except Exception:
                pass
            columns = {
                str(row[1]).casefold()
                for row in conn.execute("PRAGMA table_info(composerHeaders)").fetchall()
                if row and row[1]
            }
            stamp = "lastUpdatedAt" if "lastupdatedat" in columns else "NULL"
            rows = conn.execute(
                f"""
                SELECT value, isSubagent, workspaceId, {stamp}
                FROM composerHeaders
                WHERE composerId = ?
                ORDER BY 4 DESC
                """,
                (composer_id,),
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return "", "db_error"
    saw_other = False
    for value, subagent, workspace_id, _stamp in rows:
        if _truthy(subagent):
            continue
        slot = workspace_id.strip() if isinstance(workspace_id, str) else ""
        if not slot:
            continue
        if slot.casefold() not in allowed:
            saw_other = True
            continue
        raw = value
        if isinstance(raw, bytes):
            try:
                raw = _decode_saved_text(raw)
            except UnicodeError:
                continue
        title, _draft = _header_name(raw)
        if not title:
            continue
        return title, "ok"
    if saw_other:
        return "", "other_workspace"
    return "", "missing"


def requests_from_transcript(transcript_dir: Path) -> list[str]:
    """User requests from the composer jsonl, in file order."""
    path = transcript_dir / f"{transcript_dir.name}.jsonl"
    if not path.is_file():
        return []
    found: list[str] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict) or row.get("role") != "user":
                continue
            message = row.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            texts: list[str] = []
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, str):
                        texts.append(part)
                    elif isinstance(part, dict) and isinstance(part.get("text"), str):
                        texts.append(part["text"])
            for text in texts:
                for match in _QUERY.finditer(text):
                    cleaned = " ".join(match.group(1).split())
                    cleaned = cleaned.replace(CAPTURE_START, "").replace(CAPTURE_END, "")
                    cleaned = " ".join(cleaned.split())
                    if cleaned:
                        found.append(cleaned)
    return found


def voice_user_requests(
    db_path: Path,
    composer_id: str,
    *,
    timeout: float = 3.0,
) -> tuple[str, str, list[str]]:
    """User turns from this composer's latest voice call in state.vscdb.

    Returns ``(skip_reason, call_id, requests)``. ``skip_reason`` is empty when
    the read succeeded. ``missing_transcript`` means no stored call. ``busy``
    means the database was locked. ``db_error`` is any other read failure.
    A locked database is not reported as a missing call.

    The call row is ``glass.realtimeVoice.calls/<composer>/<call>``. Turns are
    ``glass.realtimeVoice.callTurns/<composer>/<call>/<chunk>``. Latest
    ``startedAtMs`` wins. Only ``speaker`` user is a request.
    """
    if not composer_id or not db_path.is_file():
        return "missing_transcript", "", []
    call_prefix = f"glass.realtimeVoice.calls/{composer_id}/"
    try:
        conn = sqlite3.connect(
            f"{db_path.resolve().as_uri()}?mode=ro",
            uri=True,
            timeout=timeout,
        )
    except sqlite3.Error as exc:
        return _voice_read_reason(exc), "", []
    try:
        try:
            conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
        except sqlite3.Error as exc:
            return _voice_read_reason(exc), "", []
        try:
            call_rows = conn.execute(
                "SELECT key, value FROM ItemTable WHERE key LIKE ? ESCAPE '\\'",
                (_like_prefix(call_prefix),),
            ).fetchall()
        except sqlite3.Error as exc:
            return _voice_read_reason(exc), "", []
        chosen = ""
        chosen_started = -1.0
        for key, value in call_rows:
            if not isinstance(key, str) or not key.startswith(call_prefix):
                continue
            call_id = key[len(call_prefix) :]
            if not call_id or "/" in call_id:
                continue
            started = _started_at(value)
            if started >= chosen_started:
                chosen_started = started
                chosen = call_id
        if not chosen:
            return "missing_transcript", "", []
        turn_prefix = f"glass.realtimeVoice.callTurns/{composer_id}/{chosen}/"
        try:
            turn_rows = conn.execute(
                "SELECT key, value FROM ItemTable WHERE key LIKE ? ESCAPE '\\'",
                (_like_prefix(turn_prefix),),
            ).fetchall()
        except sqlite3.Error as exc:
            return _voice_read_reason(exc), chosen, []
    finally:
        conn.close()
    ordered = sorted(
        (
            (key, value)
            for key, value in turn_rows
            if isinstance(key, str) and key.startswith(turn_prefix) and "/" not in key[len(turn_prefix) :]
        ),
        key=lambda item: _chunk_index(item[0]),
    )
    requests: list[str] = []
    for _key, value in ordered:
        requests.extend(_user_turn_texts(value))
    return "", chosen, requests


def _like_prefix(prefix: str) -> str:
    """Left-anchored LIKE pattern. ``_`` is a real character in composer ids."""
    escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return escaped + "%"


def _voice_read_reason(exc: sqlite3.Error) -> str:
    """Map a failed voice-store read to a skip reason. A missing table is no call."""
    text = str(exc).casefold()
    if "no such table" in text:
        return "missing_transcript"
    if "locked" in text or "busy" in text:
        return "busy"
    return "db_error"


def _started_at(value: object) -> float:
    text = _stored_text(value)
    if not text:
        return -1.0
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return -1.0
    if not isinstance(payload, dict):
        return -1.0
    started = payload.get("startedAtMs")
    if isinstance(started, (int, float)):
        return float(started)
    return -1.0


def _chunk_index(key: str) -> int:
    tail = key.rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else 10**9


def _stored_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value if isinstance(value, str) else ""


def _user_turn_texts(value: object) -> list[str]:
    text = _stored_text(value)
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return []
    found: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        if str(item.get("speaker") or "").strip().casefold() != "user":
            continue
        spoken = item.get("text")
        if not isinstance(spoken, str):
            continue
        cleaned = " ".join(spoken.split())
        cleaned = cleaned.replace(CAPTURE_START, "").replace(CAPTURE_END, "")
        cleaned = " ".join(cleaned.split())
        if cleaned:
            found.append(cleaned)
    return found


def render_capture(composer_id: str, source: str | Path, requests: list[str]) -> str:
    last: dict[str, str] = {}
    order: list[str] = []
    for item in requests:
        bullet = _bullet(item)
        key = bullet.casefold()
        if key in last:
            order.remove(key)
        last[key] = bullet
        order.append(key)
    unique = [last[key] for key in order]
    label = source.as_posix() if isinstance(source, Path) else source
    lines = [
        CAPTURE_START,
        "## Call-end capture",
        "",
        "Ad hoc log for any composer tab in this repo. Do not merge into `AGENTS.md`.",
        "",
        _bullet(
            f"Last capture composer `{composer_id}` from `{label}`. "
            "Written when that call ends, including an automatic drop. # operational"
        ),
    ]
    for item in unique[-20:]:
        lines.append(item)
    lines.append(CAPTURE_END)
    return "\n".join(lines)


def ensure_scope(text: str) -> str:
    bullet = scope_bullet()
    if bullet in text:
        return text
    lines = text.splitlines()
    out: list[str] = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and line.strip() == "## Learned User Preferences":
            out.append(bullet)
            inserted = True
    if not inserted:
        out.extend(["", "## Learned User Preferences", "", bullet])
    rendered = "\n".join(out)
    if text.endswith("\n"):
        rendered += "\n"
    return rendered


def merge_memory(existing: str, capture: str) -> str:
    if CAPTURE_START in existing:
        pre, rest = existing.split(CAPTURE_START, 1)
        if CAPTURE_END in rest:
            _old, post = rest.split(CAPTURE_END, 1)
            merged = pre.rstrip() + "\n\n" + capture + "\n" + post.lstrip("\n")
        else:
            merged = pre.rstrip() + "\n\n" + capture + "\n"
    else:
        base = existing if existing.strip() else SKELETON
        if not base.endswith("\n"):
            base += "\n"
        merged = base.rstrip() + "\n\n" + capture + "\n"
    return ensure_scope(merged)


def _lock_path(memory_path: Path) -> Path:
    """Lock lives in the temp directory so a crash cannot leave it in the repo."""
    key = hashlib.sha256(str(memory_path).encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f"prediction-call-end-{key}.lock"


def _acquire_lock(lock_path: Path):
    """Exclusive lock file. None if another writer still holds a fresh lock."""
    deadline = time.time() + 5
    while True:
        try:
            return os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
            except OSError:
                age = 0
            if age > 30:
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                continue
            if time.time() >= deadline:
                return None
            time.sleep(0.05)


def _release_lock(fd: int, lock_path: Path) -> None:
    os.close(fd)
    try:
        lock_path.unlink()
    except OSError:
        pass


def _replace_capture(memory_path: Path, capture: str) -> None:
    """Replace the capture block. Caller holds the memory-file lock.

    The temp file sits next to the memory file. os.replace cannot move a file
    onto another drive, and the system temp directory is often on C: while this
    repo is on D:.
    """
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = memory_path.with_name(memory_path.name + ".tmp")
    try:
        existing = memory_path.read_text(encoding="utf-8") if memory_path.is_file() else ""
        updated = merge_memory(existing, capture)
        if updated == existing:
            return
        tmp_path.write_text(updated, encoding="utf-8", newline="\n")
        os.replace(tmp_path, memory_path)
    finally:
        if tmp_path.is_file():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _write_merged(memory_path: Path, capture: str) -> None:
    """Re-read and replace under a lock so two call-end hooks cannot tear the file."""
    lock_path = _lock_path(memory_path)
    fd = _acquire_lock(lock_path)
    if fd is None:
        raise TimeoutError("memory file lock held")
    try:
        _replace_capture(memory_path, capture)
    finally:
        _release_lock(fd, lock_path)


def prompt_text(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    value = payload.get("prompt")
    return value if isinstance(value, str) else ""


def _start_recall():
    """The recall script owns the phrase list. The write path does not call this."""
    name = "prediction_memory_recall"
    loaded = sys.modules.get(name)
    if loaded is not None and hasattr(loaded, "opens_with_recall"):
        return loaded
    path = Path(__file__).resolve().with_name("prediction_memory_recall.py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def is_recall_prompt(prompt: str, extra: object = None) -> bool:
    """True when the user's own text opens with a recall phrase.

    The assembled prompt may be a voice rewrite. Matching stays at the start of
    the raw line. This does not write the file and does not look up a tab.
    """
    try:
        module = _start_recall()
        return any(module.opens_with_recall(text) for text in module.recall_sources(prompt, extra))
    except (ImportError, OSError, SyntaxError):
        return False


def fit_context(text: str, limit: int = _CONTEXT_LIMIT) -> str:
    """Stay under Cursor's additional_context cap. Curated sections come before the call log."""
    if len(text) <= limit:
        return text
    note = "\n\n[Call log truncated to the hook context limit.]\n"
    budget = limit - len(note)
    if budget < 1:
        return text[:limit]
    marker = CAPTURE_START
    if marker in text:
        head, tail = text.split(marker, 1)
        if len(head) >= budget:
            return head[:budget] + note
        room = budget - len(head) - len(marker)
        if room < 0:
            return head[:budget] + note
        return head + marker + tail[:room] + note
    return text[:budget] + note


def recall(
    payload: object,
    *,
    memory_path: Path,
) -> dict[str, object]:
    """Read the prediction memory into context. Does not write the file.

    The only gate is a scripted phrase at the start of the spoken line.
    A bare phrase returns the file. A phrase with a subject grows the tree.
    Composer id, stored tab name, and workspace id are not consulted.
    """
    if not is_recall_prompt(prompt_text(payload), payload):
        return {"continue": True}
    if not memory_path.is_file():
        return {"continue": True}
    transcript = ""
    if isinstance(payload, dict):
        value = payload.get("transcript_path")
        if isinstance(value, str):
            transcript = value
    context = _start_recall().present_recall(
        prompt_text(payload),
        memory_path.read_text(encoding="utf-8"),
        transcript,
        limit=_CONTEXT_LIMIT,
        extra=payload,
    )
    if not context:
        return {"continue": True}
    return {"continue": True, "additional_context": context}


def run(
    payload: object,
    *,
    repo: Path,
    db_path: Path,
    projects_root: Path,
    memory_path: Path,
    workspace_ids: list[str] | tuple[str, ...] | None = None,
    storage_root: Path | None = None,
) -> dict[str, str]:
    """Confirm the tab, then write the voice-call capture. Never writes on a skip."""
    reason = call_end_reason(payload)
    if reason:
        return {"status": "skipped", "reason": reason}
    composer_id = composer_id_from_payload(payload)
    if not composer_id:
        return {"status": "skipped", "reason": "missing_composer_id"}
    if workspace_ids is None:
        workspace_ids = repo_workspace_ids(repo, storage_root) if storage_root is not None else []
    title, status = header_title(db_path, composer_id, workspace_ids)
    if status != "ok":
        return {"status": "skipped", "reason": status}
    # Read the voice call inside the file lock. sessionEnd and a completed
    # stop can overlap, and a snapshot taken before the lock can be written
    # last and replace a newer capture.
    lock_path = _lock_path(memory_path)
    fd = _acquire_lock(lock_path)
    if fd is None:
        return {"status": "skipped", "reason": "busy"}
    try:
        voice_reason, call_id, requests = voice_user_requests(db_path, composer_id)
        if voice_reason:
            return {"status": "skipped", "reason": voice_reason}
        if not requests:
            return {"status": "skipped", "reason": "empty_transcript"}
        source = f"glass.realtimeVoice.callTurns/{composer_id}/{call_id}"
        _replace_capture(memory_path, render_capture(composer_id, source, requests))
    except (OSError, UnicodeError):
        return {"status": "skipped", "reason": "unreadable"}
    finally:
        _release_lock(fd, lock_path)
    return {"status": "wrote", "reason": "ok", "composer_id": composer_id, "tab": title}


def main() -> int:
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            payload = {}
        repo = Path(__file__).resolve().parents[2]
        event = ""
        if isinstance(payload, dict):
            event = str(payload.get("hook_event_name") or "").strip().casefold()
        if event == "beforesubmitprompt":
            recalled = recall(
                payload,
                memory_path=repo / MEMORY_REL,
            )
            print(json.dumps(recalled), flush=True)
            return 0
        hooks_dir = Path(__file__).resolve().parent
        if str(hooks_dir) not in sys.path:
            sys.path.insert(0, str(hooks_dir))
        from _bootstrap import bootstrap_hive_planner

        bootstrap_hive_planner()
        from hive_planner.launcher.cursor_chat_delivery import _cursor_user_dir

        user = _cursor_user_dir()
        db_path = (user / "globalStorage" / "state.vscdb") if user is not None else Path("")
        storage_root = (user / "workspaceStorage") if user is not None else None
        projects_root = Path.home() / ".cursor" / "projects"
        slots = repo_workspace_ids(repo, storage_root) if storage_root is not None else []
        result = run(
            payload,
            repo=repo,
            db_path=db_path,
            projects_root=projects_root,
            memory_path=repo / MEMORY_REL,
            workspace_ids=slots,
        )
        if result.get("status") == "skipped":
            print(f"[prediction_bug_hunt_call_end] skipped: {result.get('reason')}", file=sys.stderr)
        print(json.dumps({}), flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001 — Cursor hooks must fail open with JSON
        print(f"[prediction_bug_hunt_call_end] failed: {exc}", file=sys.stderr)
        print(json.dumps({}), flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

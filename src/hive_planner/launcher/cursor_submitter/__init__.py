"""In-workbench half of Controls Execute.

Hive's process must not call ``submitChatMaybeAbortCurrent``. A host that
already has that workbench function passes it in. Force is omitted.

Cursor's workspace-open ``pluginPaths`` host loads hooks and skills. It cannot
call the workbench function. This package does not open the desktop bridge,
does not read a bearer token, and does not paste or walk an accessibility tree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

REQUEST_REL = Path(".hive") / "controls-execute" / "request.json"
RESULT_REL = Path(".hive") / "controls-execute" / "result.json"

Submit = Callable[[str, str], None]


def _write_result(repo: Path, nonce: str, outcome: str) -> dict[str, str]:
    payload = {"nonce": nonce, "outcome": outcome}
    result_path = repo / RESULT_REL
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def apply_request(repo: Path, submit: Submit) -> dict[str, str]:
    """Read request.json, call submit(composer_id, phrase), write result.json."""
    path = repo / REQUEST_REL
    try:
        request = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _write_result(repo, "", "failed")
    # A JSON array is not a request. Indexing it crashed the host before a result existed.
    if not isinstance(request, dict):
        return _write_result(repo, "", "failed")
    try:
        nonce = str(request["nonce"])
        composer_id = str(request["composerId"])
        phrase = str(request["phrase"])
    except (KeyError, TypeError):
        raw_nonce = request.get("nonce")
        return _write_result(repo, "" if raw_nonce is None else str(raw_nonce), "failed")
    outcome = "sent"
    try:
        submit(composer_id, phrase)
    except Exception:
        outcome = "failed"
    return _write_result(repo, nonce, outcome)

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


def apply_request(repo: Path, submit: Submit) -> dict[str, str]:
    """Read request.json, call submit(composer_id, phrase), write result.json."""
    path = repo / REQUEST_REL
    request = json.loads(path.read_text(encoding="utf-8"))
    nonce = str(request["nonce"])
    composer_id = str(request["composerId"])
    phrase = str(request["phrase"])
    outcome = "sent"
    try:
        submit(composer_id, phrase)
    except Exception:
        outcome = "failed"
    payload = {"nonce": nonce, "outcome": outcome}
    result_path = repo / RESULT_REL
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(payload), encoding="utf-8")
    return payload

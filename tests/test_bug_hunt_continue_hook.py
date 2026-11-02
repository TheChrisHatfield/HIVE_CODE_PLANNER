from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / ".cursor" / "hooks" / "bug_hunt_continue.py"


def _load_hook():
    spec = importlib.util.spec_from_file_location("bug_hunt_continue_hook", HOOK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hook_reads_utf16_le_continue_without_a_bom(tmp_path: Path) -> None:
    hook = _load_hook()
    path = tmp_path / "continue.json"
    payload = {
        "active": True,
        "pause_seconds": 10,
        "ceiling": 50,
        "committed": 1,
        "consecutive_empty": 0,
    }
    path.write_bytes(json.dumps(payload).encode("utf-16-le"))

    loaded = hook._read_state(path)

    assert loaded is not None
    assert loaded["active"] is True
    assert loaded["committed"] == 1

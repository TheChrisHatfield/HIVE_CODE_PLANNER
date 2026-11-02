from __future__ import annotations

import json
from pathlib import Path

from hive_planner.bug_hunt import render_continue_hook
from hive_planner.bug_hunt_continue import _read_state


def test_source_reads_utf16_le_continue_without_a_bom(tmp_path: Path) -> None:
    path = tmp_path / "continue.json"
    payload = {
        "active": True,
        "pause_seconds": 10,
        "ceiling": 50,
        "committed": 1,
        "consecutive_empty": 0,
    }
    path.write_bytes(json.dumps(payload).encode("utf-16-le"))

    loaded = _read_state(path)

    assert loaded is not None
    assert loaded["active"] is True
    assert loaded["committed"] == 1
    assert 'decode("utf-16-le")' in render_continue_hook()

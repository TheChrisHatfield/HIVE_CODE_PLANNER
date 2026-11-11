from __future__ import annotations

import json
from pathlib import Path

from hive_planner.bug_hunt import render_continue_hook
from hive_planner.bug_hunt_continue import _queue_has_candidate, _read_state


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


def test_queue_has_candidate_reads_utf16_le_rank_pass(tmp_path: Path) -> None:
    rank = tmp_path / ".hive" / "bug-hunt" / "rank-pass.json"
    rank.parent.mkdir(parents=True)
    payload = {
        "opened": [],
        "queue": [
            {
                "file": "src/hive_planner/foo.py",
                "signals": {
                    "recent_fix_commits": 0,
                    "thin_test": 1.0,
                    "wiring_hop": 0,
                    "dead_setting": 0,
                    "reverted": 0,
                    "split_stores": 0,
                },
                "findings": 0,
            }
        ],
    }
    rank.write_bytes(json.dumps(payload).encode("utf-16-le"))
    assert _queue_has_candidate(tmp_path, "src/other.py") is True

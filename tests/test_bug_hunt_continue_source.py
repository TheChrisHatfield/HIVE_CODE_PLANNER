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


def test_recovery_limit_does_not_start_another_pass(tmp_path: Path, monkeypatch) -> None:
    """A third recovery-empty must not send followup_message. Ceiling stops return {}."""
    import hive_planner.bug_hunt as ranker
    from hive_planner.bug_hunt_continue import apply_continue

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("def b():\n    return 1\n", encoding="utf-8")

    def fake_signals(_path, rel, **_kwargs):
        return (
            {
                "recent_fix_commits": 0.0,
                "thin_test": 1.0,
                "wiring_hop": 0.0,
                "dead_setting": 0.0,
                "reverted": 0.0,
                "split_stores": 0.0,
            },
            2,
            0,
            0,
            0,
        )

    monkeypatch.setattr(ranker, "_signals_for_file", fake_signals)
    state_dir = tmp_path / ".hive" / "bug-hunt"
    state_dir.mkdir(parents=True)
    (state_dir / "rank-pass.json").write_text(
        json.dumps(
            {
                "opened": ["src/other.py"],
                "queue": [
                    {
                        "file": "src/a.py",
                        "signals": {"thin_test": 1},
                        "findings": 0,
                        "score": 2,
                    },
                    {
                        "file": "src/b.py",
                        "signals": {"thin_test": 1},
                        "findings": 0,
                        "score": 1,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (state_dir / "recovery.json").write_text(
        json.dumps(
            {
                "phase": "recovery",
                "attempts": 2,
                "empty_streak": 2,
                "excluded_locations": ["src/other.py"],
                "excluded_folders": ["src"],
                "lenses_used": ["ui-event"],
                "coverage_by_folder": {"src": 1},
                "last_empty_confidence": 1.0,
            }
        ),
        encoding="utf-8",
    )
    (state_dir / "continue.json").write_text(
        json.dumps(
            {
                "active": True,
                "pause_seconds": 0,
                "ceiling": 50,
                "committed": 0,
                "consecutive_empty": 4,
                "file": "src/a.py",
                "scenario": "empty",
                "outcome": "empty",
                "empty_confidence": 0.5,
                "recovery_lens": "configuration",
            }
        ),
        encoding="utf-8",
    )
    payload = apply_continue(tmp_path, sleep=lambda _seconds: None)
    assert payload == {}
    assert json.loads((state_dir / "continue.json").read_text(encoding="utf-8"))["active"] is False

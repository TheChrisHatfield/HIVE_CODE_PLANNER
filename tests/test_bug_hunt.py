from __future__ import annotations

import io
import os
from contextlib import redirect_stdout
from pathlib import Path

import pytest

import math
import random

from hive_planner.bug_hunt import (
    INITIAL_SLOPES,
    BugHuntError,
    advance_rank_pass,
    commit_isolated_fix,
    fix_commit_feature,
    imaginary_votes,
    rebuild_mean,
    thompson_draw,
    install_bug_hunt,
    is_bug_hunt_request,
    missing_bug_hunt_artifacts,
    preview_agent_prompt,
    render_agent_prompt,
    render_cursor_rule,
    load_rank_rows,
    score_signals,
)
from hive_planner.cli import main


@pytest.mark.parametrize(
    "text",
    [
        "bug hunt",
        "do a bug hunt",
        "do a bung hunt",
        "bug hun",
        "please hunt for bugs",
        "start hunting bugs",
        "run a bug-hunt",
        "/bug-hunt",
        "Can you bughunt the launcher?",
        "perform a bug hunt on Home",
        "start bug hunting",
        "run some bug-hunting",
        "do bug hunts",
        "please hunt for any bugs",
        "use this prompt to check you implenationtat of the bug hunt script",
        "Execute a continuous 50-iteration bug-hunting and wiring verification loop",
        "hunt some bugs",
        "please hunting for more bugs",
        "bu hunt",
        "run another loop to fix bugs",
        "loop to fix bugs",
        "please run another loop to fix bugs",
        "end to end bug hunt",
        "run an end to end bug hunt",
        "don't wait, start a bug hunt",
        "stop explaining and run a bug hunt",
        "cancel that and start a bug hunt",
        "read the bug hunt command and start a bug hunt",
        "look at the script and then run a bug hunt",
        "this bug hunt",
        "please start this bug hunt",
        "Run a bug hunt and explain the bug hunt script",
        "Start a bug hunt; we are not using the bug hunt's old commit rule",
    ],
)
def test_is_bug_hunt_request_starts_the_loop(text: str) -> None:
    assert is_bug_hunt_request(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "fix the login button",
        "how does bug hunt work",
        "where is the bug-hunt command",
        "what is a bug hunt",
        "does bug hunt install files",
        "how do I install bug hunt",
        "please tell me how does bug hunt work",
        "how to run a bug hunt",
        "Can you tell me where is the bug-hunt command",
        "review the bug hunt script for bugs",
        "check the bug hunt script for errors",
        "look at the bug hunt script",
        "summarize the bug hunt script",
        "audit the bug hunt script",
        "describe the bug hunt flow",
        "explain bug hunting",
        "tell me about bug hunts",
        "walk me through the bug hunt",
        "do not run the bug hunt",
        "don't start the bug hunt",
        "do not start a bug hunt",
        "never run the bug hunt",
        "stop the bug hunt",
        "cancel the bug hunt",
        "wait for the bug hunt to finish",
        "the bug hunts of yesterday",
        "skip the bug hunt",
        "disable the bug hunt",
        "turn off the bug hunt",
        "kill the bug hunt",
        "never bug hunt",
        "please never bug hunt",
        "I do not want a bug hunt",
        "without running a bug hunt",
        "Run a prompted bug code review, not using the bug hunt command's own loop",
        "Run a five-loop prompted bug code review of the entire bug hunt script",
        "do not loop to fix bugs",
        "do not ever start a bug hunt",
        "don't loop to fix bugs",
    ],
)
def test_is_bug_hunt_request_rejects_docs_and_noise(text: str) -> None:
    assert is_bug_hunt_request(text) is False


def test_cursor_rule_matches_derivative_phrases() -> None:
    rule = render_cursor_rule()
    assert "alwaysApply: true" in rule
    assert "hunt for bugs" in rule
    assert "run another loop to fix bugs" in rule
    assert "Match intent" in rule
    assert "how to install" in rule
    assert "Do not stop after one bug" in rule
    assert "A request to stop, cancel, pause, skip, disable, or wait for the hunt is not a start signal" in rule
    assert "end to end bug hunt" in rule
    assert "After the outcome row is written" not in rule
    assert "stop hook appends the rank row" in rule


def test_gan_hand_score_matches_ranker() -> None:
    import inspect
    import sys

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    import sandbox_rank_gan as gan

    scored = gan.score_source("unused.py", "def unused():\n    return 1\n", [0.0] * 6)
    values = [float(scored["signals"][key]) for key in gan.weights.SIGNALS]
    assert scored["hand"] == round(score_signals(values), 4)
    holdout_source = inspect.getsource(gan.holdout)
    assert "score_signals" in holdout_source
    assert "dot(weights.HAND" not in holdout_source
    with pytest.raises(ValueError, match="fix-commit count must be >= 0"):
        gan.weights.score_signals([-1, 0, 0, 0, 0, 0])


def test_rebuild_mean_uses_seed_decay_and_both_positive_outcomes() -> None:
    assert imaginary_votes(0) == 20.0
    assert imaginary_votes(40) == pytest.approx(10.0)
    assert rebuild_mean([])[0] == INITIAL_SLOPES
    row = {"signals": {"recent_fix_commits": 0, "thin_test": 1, "wiring_hop": 0, "dead_setting": 0, "reverted": 0, "split_stores": 0}}
    committed = rebuild_mean([{**row, "outcome": "committed"}])[0]
    failed = rebuild_mean([{**row, "outcome": "review-failed"}])[0]
    assert committed == pytest.approx(failed)
    assert committed[1] == pytest.approx(3.3024 + 1.0 / 3.0)
    assert committed[1] > INITIAL_SLOPES[1]
    skipped = rebuild_mean([{**row, "outcome": "skipped"}])[0]
    assert skipped == INITIAL_SLOPES
    empty = rebuild_mean([{**row, "outcome": "empty"}])[0]
    assert empty[1] == pytest.approx(3.3024 - 1.0 / 3.0)
    assert empty[1] > 0.0
    flooded = rebuild_mean([{**row, "outcome": "empty"}] * 80)[0]
    assert flooded[1] > 2.2
    high = {
        "signals": {
            "recent_fix_commits": 1000,
            "thin_test": 0,
            "wiring_hop": 0,
            "dead_setting": 0,
            "reverted": 0,
            "split_stores": 0,
        },
        "outcome": "empty",
    }
    assert rebuild_mean([high] * 40)[0][0] == 0.0
    hop = {"signals": [0, 0, 1, 0, 0, 0], "outcome": "committed"}
    newer_mean, evidence = rebuild_mean([hop, {**row, "outcome": "committed"}])
    older_mean, _older_evidence = rebuild_mean([{**row, "outcome": "committed"}, hop])
    # Newest voted row has weight 1 and the older row has weight 0.9.
    assert newer_mean[1] - older_mean[1] == pytest.approx(0.1 / (2.0 + 1.9))
    assert evidence > 2.0


def test_advance_rank_pass_scores_unopened_files_and_appends_the_row(tmp_path: Path) -> None:
    import json

    first = tmp_path / "src" / "opened.py"
    second = tmp_path / "src" / "next.py"
    first.parent.mkdir(parents=True)
    first.write_text("def unused():\n    return 1\n", encoding="utf-8")
    second.write_text("FLAG = 1\n", encoding="utf-8")
    files = [first, second]
    history: tuple[dict[str, int], set[str]] = ({}, set())
    fresh = advance_rank_pass(tmp_path, None, fresh=True, rng=random.Random(1), files=files, history=history)
    assert fresh["appended"] is False
    saved = json.loads((tmp_path / ".hive" / "bug-hunt" / "rank-pass.json").read_text(encoding="utf-8"))
    assert "mean" not in saved
    assert "draw" not in saved["queue"][0]
    assert len(saved["draw"]) == 6
    names = {item["file"] for item in saved["queue"]}
    assert names == {"src/opened.py", "src/next.py"}
    again = advance_rank_pass(
        tmp_path,
        {"file": "src/opened.py", "scenario": "dead call", "outcome": "committed"},
        fresh=False,
        rng=random.Random(2),
        files=files,
        history=history,
    )
    assert again["appended"] is True
    assert again["top"] == "src/next.py"
    rows = load_rank_rows(tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl")
    assert rows[-1]["outcome"] == "committed"
    assert rows[-1]["signals"]["wiring_hop"] == 1
    opened_item = next(item for item in saved["queue"] if item["file"] == "src/opened.py")
    assert rows[-1]["findings"] == opened_item["findings"]
    assert rows[-1]["score"] == opened_item["score"]
    assert rebuild_mean(rows)[0] != INITIAL_SLOPES
    skipped = advance_rank_pass(
        tmp_path,
        {"file": "src/next.py", "scenario": "skip", "outcome": "skipped"},
        fresh=False,
        rng=random.Random(3),
        files=files,
        history=history,
    )
    assert skipped["appended"] is True
    skipped_rows = load_rank_rows(tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl")
    assert rebuild_mean(skipped_rows)[0] == pytest.approx(rebuild_mean(rows)[0])
    queued = json.loads((tmp_path / ".hive" / "bug-hunt" / "rank-pass.json").read_text(encoding="utf-8"))
    assert len(queued["draw"]) == 6
    assert all("draw" not in item for item in queued["queue"])
    assert len(rows[-1]["draw"]) == 6


def test_missing_file_key_does_not_claim_queue_head(tmp_path: Path) -> None:
    import json

    first = tmp_path / "src" / "opened.py"
    second = tmp_path / "src" / "next.py"
    first.parent.mkdir(parents=True)
    first.write_text("def unused():\n    return 1\n", encoding="utf-8")
    second.write_text("FLAG = 1\n", encoding="utf-8")
    files = [first, second]
    history: tuple[dict[str, int], set[str]] = ({}, set())
    advance_rank_pass(tmp_path, None, fresh=True, rng=random.Random(1), files=files, history=history)
    saved = json.loads((tmp_path / ".hive" / "bug-hunt" / "rank-pass.json").read_text(encoding="utf-8"))
    head = saved["queue"][0]["file"]
    other = saved["queue"][1]["file"]
    again = advance_rank_pass(
        tmp_path,
        {"outcome": "committed", "scenario": "unnamed file"},
        fresh=False,
        rng=random.Random(2),
        files=files,
        history=history,
    )
    rows = load_rank_rows(tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl")
    assert again["appended"] is False
    assert not rows
    assert head not in again["opened"]
    assert other not in again["opened"]


def test_candidate_scan_includes_csharp_files(tmp_path: Path) -> None:
    import json

    py = tmp_path / "src" / "a.py"
    cs = tmp_path / "src" / "b.cs"
    py.parent.mkdir(parents=True)
    py.write_text("x = 1\n", encoding="utf-8")
    cs.write_text("class C {}\n", encoding="utf-8")
    history: tuple[dict[str, int], set[str]] = ({"src/b.cs": 2}, set())
    advance_rank_pass(
        tmp_path,
        None,
        fresh=True,
        rng=random.Random(0),
        files=[py, cs],
        history=history,
    )
    queued = json.loads((tmp_path / ".hive" / "bug-hunt" / "rank-pass.json").read_text(encoding="utf-8"))
    files = {item["file"] for item in queued["queue"]}
    assert "src/b.cs" in files


def test_queue_sort_key_treats_nan_and_inf_as_zero() -> None:
    from hive_planner.bug_hunt import queue_sort_key

    items = [
        {"file": "nan.py", "score": float("nan"), "findings": 0, "lines": 1},
        {"file": "inf.py", "score": float("inf"), "findings": 0, "lines": 1},
        {"file": "ok.py", "score": 2.0, "findings": 0, "lines": 1},
    ]
    items.sort(key=queue_sort_key)
    assert items[0]["file"] == "ok.py"


def test_queue_sort_key_treats_overflow_lines_and_bool_as_zero() -> None:
    from hive_planner.bug_hunt import queue_sort_key

    items = [
        {"file": "huge.py", "score": 1.0, "findings": 0, "lines": 1e999},
        {"file": "flag.py", "score": 1.0, "findings": 0, "lines": True},
        {"file": "ok.py", "score": 1.0, "findings": 0, "lines": 9},
    ]
    items.sort(key=queue_sort_key)
    assert items[0]["file"] == "ok.py"


def test_load_rank_rows_unreadable_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.bug_hunt import load_rank_rows

    path = tmp_path / "rank-rows.jsonl"
    path.write_text("{}\n", encoding="utf-8")

    def _boom(self: Path, *args: object, **kwargs: object) -> str:
        raise OSError("locked")

    monkeypatch.setattr(Path, "read_text", _boom)
    assert load_rank_rows(path) == []


def test_append_rank_row_stores_zero_signals_when_nan(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import SIGNAL_KEYS, _append_rank_row, load_rank_rows

    _append_rank_row(
        tmp_path,
        "src/a.py",
        {
            "recent_fix_commits": float("nan"),
            "thin_test": 0.0,
            "wiring_hop": 0.0,
            "dead_setting": 0.0,
            "reverted": 0.0,
            "split_stores": 0.0,
        },
        "x",
        "committed",
    )
    rows = load_rank_rows(tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl")
    assert rows[-1]["file"] == "src/a.py"
    assert rows[-1]["signals"] == {key: 0.0 for key in SIGNAL_KEYS}


def test_write_json_removes_tmp_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.bug_hunt import _write_json

    path = tmp_path / "rank-pass.json"
    real_replace = os.replace

    def _boom(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if Path(src).name == path.name:
            raise OSError("replace failed")
        real_replace(src, dst)

    monkeypatch.setattr("hive_planner.bug_hunt.os.replace", _boom)
    with pytest.raises(OSError, match="replace failed"):
        _write_json(path, {"opened": []})
    assert not path.with_name(path.name + ".tmp").exists()
    leftovers = [item for item in path.parent.iterdir() if item.name.startswith(".rank-pass.json.")]
    assert leftovers == []


def test_write_json_removes_tmp_when_nan_refused(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import _write_json

    path = tmp_path / "rank-pass.json"
    with pytest.raises(ValueError):
        _write_json(path, {"score": float("nan")})
    assert not path.exists()
    assert not path.with_name(path.name + ".tmp").exists()


def test_load_opened_rejects_corrupt_rank_pass(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import BugHuntError, _load_opened

    path = tmp_path / ".hive" / "bug-hunt" / "rank-pass.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(BugHuntError, match="not valid JSON"):
        _load_opened(tmp_path)


def test_load_opened_rejects_non_list_opened(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import BugHuntError, _load_opened

    path = tmp_path / ".hive" / "bug-hunt" / "rank-pass.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"opened": "src/a.py", "queue": []}\n', encoding="utf-8")
    with pytest.raises(BugHuntError, match="opened list is invalid"):
        _load_opened(tmp_path)


def test_load_opened_skips_non_string_entries(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import _load_opened

    path = tmp_path / ".hive" / "bug-hunt" / "rank-pass.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"opened": ["src/a.py", {"file": "src/b.py"}, null, true, 3], "queue": []}\n',
        encoding="utf-8",
    )
    assert _load_opened(tmp_path) == ["src/a.py"]


def test_candidate_files_skip_tool_caches(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import _candidate_files

    src = tmp_path / "src" / "app.py"
    src.parent.mkdir(parents=True)
    src.write_text("x = 1\n", encoding="utf-8")
    cached = tmp_path / ".mypy_cache" / "3.11" / "app.py"
    cached.parent.mkdir(parents=True)
    cached.write_text("x = 1\n", encoding="utf-8")
    toxed = tmp_path / ".tox" / "py311" / "app.py"
    toxed.parent.mkdir(parents=True)
    toxed.write_text("x = 1\n", encoding="utf-8")
    hook = tmp_path / ".cursor" / "hooks" / "bug_hunt_continue.py"
    hook.parent.mkdir(parents=True)
    hook.write_text("x = 1\n", encoding="utf-8")
    found = {path.resolve() for path in _candidate_files(tmp_path)}
    assert src.resolve() in found
    assert cached.resolve() not in found
    assert toxed.resolve() not in found
    assert hook.resolve() not in found
    import os

    if os.path.normcase("A") != os.path.normcase("a"):
        weird = tmp_path / ".Mypy_Cache" / "app.py"
        weird.parent.mkdir(parents=True)
        weird.write_text("x = 1\n", encoding="utf-8")
        found = {path.resolve() for path in _candidate_files(tmp_path)}
        assert weird.resolve() not in found


def test_git_history_parse_failure_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.bug_hunt import _git_history, _sandbox_detect

    (tmp_path / ".git").mkdir()
    detect = _sandbox_detect()

    def _boom(_text: str):
        raise RecursionError("parse too deep")

    monkeypatch.setattr(detect, "parse_git_log", _boom)
    monkeypatch.setattr(
        "hive_planner.bug_hunt.subprocess.run",
        lambda *args, **kwargs: type(
            "Done",
            (),
            {"returncode": 0, "stdout": "x"},
        )(),
    )
    assert _git_history(tmp_path) == ({}, set())


def test_git_history_memory_error_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.bug_hunt import _git_history, _sandbox_detect

    (tmp_path / ".git").mkdir()
    detect = _sandbox_detect()

    def _boom(_text: str):
        raise MemoryError("log too large")

    monkeypatch.setattr(detect, "parse_git_log", _boom)
    monkeypatch.setattr(
        "hive_planner.bug_hunt.subprocess.run",
        lambda *args, **kwargs: type(
            "Done",
            (),
            {"returncode": 0, "stdout": "x"},
        )(),
    )
    assert _git_history(tmp_path) == ({}, set())


def test_norm_rel_keeps_dot_directories() -> None:
    from hive_planner.bug_hunt import _norm_rel

    assert _norm_rel(".cursor/hooks/x.py") == ".cursor/hooks/x.py"
    assert _norm_rel("./src/a.py") == "src/a.py"
    assert _norm_rel(".\\src\\b.py") == "src/b.py"
    assert _norm_rel("src/c.py") == "src/c.py"


def test_score_unopened_preserves_dot_directory_file(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, score_unopened

    hidden = tmp_path / ".cursor" / "hooks" / "hook.py"
    hidden.parent.mkdir(parents=True)
    hidden.write_text("def build(items=[]):\n    return items\n", encoding="utf-8")
    queue = score_unopened(
        tmp_path,
        [],
        INITIAL_SLOPES,
        files=[hidden],
        history=({}, set()),
    )
    assert queue
    assert queue[0]["file"] == ".cursor/hooks/hook.py"


def test_signals_for_file_skips_recursion_from_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, _sandbox_detect, score_unopened

    target = tmp_path / "src" / "deep.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n", encoding="utf-8")
    detect = _sandbox_detect()

    def _boom(_path, _source):
        raise RecursionError("ast too deep")

    monkeypatch.setattr(detect, "findings_for", _boom)
    queue = score_unopened(
        tmp_path,
        [],
        INITIAL_SLOPES,
        files=[target],
        history=({}, set()),
    )
    assert queue == []


def test_signals_for_file_skips_memory_error_from_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, _sandbox_detect, score_unopened

    target = tmp_path / "src" / "deep.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n", encoding="utf-8")
    detect = _sandbox_detect()

    def _boom(_path, _source):
        raise MemoryError("ast too large")

    monkeypatch.setattr(detect, "findings_for", _boom)
    queue = score_unopened(
        tmp_path,
        [],
        INITIAL_SLOPES,
        files=[target],
        history=({}, set()),
    )
    assert queue == []


def test_signals_for_file_keeps_findings_when_python_signals_recurses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, _sandbox_detect, score_unopened

    target = tmp_path / "src" / "hot.py"
    target.parent.mkdir(parents=True)
    target.write_text("def build(items=[]):\n    return items\n", encoding="utf-8")
    detect = _sandbox_detect()

    def _boom(_source, _thin):
        raise RecursionError("signals too deep")

    monkeypatch.setattr(detect, "python_signals", _boom)
    queue = score_unopened(
        tmp_path,
        [],
        INITIAL_SLOPES,
        files=[target],
        history=({}, set()),
    )
    assert queue
    assert queue[0]["file"] == "src/hot.py"
    assert int(queue[0]["findings"]) >= 1


def test_signals_for_file_keeps_findings_when_python_signals_memory_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, _sandbox_detect, score_unopened

    target = tmp_path / "src" / "hot.py"
    target.parent.mkdir(parents=True)
    target.write_text("def build(items=[]):\n    return items\n", encoding="utf-8")
    detect = _sandbox_detect()

    def _boom(_source, _thin):
        raise MemoryError("signals too large")

    monkeypatch.setattr(detect, "python_signals", _boom)
    queue = score_unopened(
        tmp_path,
        [],
        INITIAL_SLOPES,
        files=[target],
        history=({}, set()),
    )
    assert queue
    assert queue[0]["file"] == "src/hot.py"
    assert int(queue[0]["findings"]) >= 1


def test_signals_for_file_keeps_findings_when_python_signals_type_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, _sandbox_detect, score_unopened

    target = tmp_path / "src" / "hot.py"
    target.parent.mkdir(parents=True)
    target.write_text("def build(items=[]):\n    return items\n", encoding="utf-8")
    detect = _sandbox_detect()

    def _boom(_source, _thin):
        raise TypeError("signals packed wrong")

    monkeypatch.setattr(detect, "python_signals", _boom)
    queue = score_unopened(
        tmp_path,
        [],
        INITIAL_SLOPES,
        files=[target],
        history=({}, set()),
    )
    assert queue
    assert queue[0]["file"] == "src/hot.py"
    assert int(queue[0]["findings"]) >= 1


def test_rebuild_mean_skips_nan_signal_rows() -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, rebuild_mean

    mean, _evidence = rebuild_mean(
        [
            {
                "signals": [float("nan"), 1, 0, 0, 0, 0],
                "outcome": "committed",
            }
        ]
    )
    assert mean == INITIAL_SLOPES


def test_signals_for_file_skips_non_list_findings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, _sandbox_detect, score_unopened

    target = tmp_path / "src" / "odd.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n", encoding="utf-8")
    detect = _sandbox_detect()

    def _bad(_path, _source):
        return object()

    monkeypatch.setattr(detect, "findings_for", _bad)
    queue = score_unopened(
        tmp_path,
        [],
        INITIAL_SLOPES,
        files=[target],
        history=({}, set()),
    )
    assert queue == []


def test_syntax_error_python_still_ranks(tmp_path: Path) -> None:
    import json

    broken = tmp_path / "src" / "broken.py"
    broken.parent.mkdir(parents=True)
    broken.write_text("def broken(\n", encoding="utf-8")
    history: tuple[dict[str, int], set[str]] = ({}, set())
    advance_rank_pass(
        tmp_path,
        None,
        fresh=True,
        rng=random.Random(0),
        files=[broken],
        history=history,
    )
    queued = json.loads((tmp_path / ".hive" / "bug-hunt" / "rank-pass.json").read_text(encoding="utf-8"))
    by_file = {item["file"]: item for item in queued["queue"]}
    assert "src/broken.py" in by_file
    assert int(by_file["src/broken.py"]["findings"]) >= 1


def test_live_queue_uses_sandbox_findings_for(tmp_path: Path) -> None:
    import json

    detect = __import__("hive_planner.bug_hunt", fromlist=["_sandbox_detect"])._sandbox_detect()
    safe = tmp_path / "src" / "safe.py"
    bad = tmp_path / "src" / "bad.py"
    safe.parent.mkdir(parents=True)
    safe.write_text("def build(items=None):\n    return items or []\n", encoding="utf-8")
    bad.write_text("def build(items=[]):\n    return items\n", encoding="utf-8")
    assert detect.findings_for(bad, bad.read_text(encoding="utf-8"))
    assert not detect.findings_for(safe, safe.read_text(encoding="utf-8"))
    history: tuple[dict[str, int], set[str]] = ({}, set())
    advance_rank_pass(
        tmp_path,
        None,
        fresh=True,
        rng=random.Random(0),
        files=[safe, bad],
        history=history,
    )
    queued = json.loads((tmp_path / ".hive" / "bug-hunt" / "rank-pass.json").read_text(encoding="utf-8"))
    by_file = {item["file"]: item for item in queued["queue"]}
    assert by_file["src/bad.py"]["findings"] >= 1
    assert by_file["src/safe.py"]["findings"] == 0
    assert queued["queue"][0]["file"] == "src/bad.py"


def test_findings_file_outranks_equivalent_zero_finding_file(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, score_unopened

    hot = tmp_path / "src" / "hot.py"
    cold = tmp_path / "src" / "cold.py"
    hot.parent.mkdir(parents=True)
    hot.write_text("def build(items=[]):\n    return items\n", encoding="utf-8")
    cold.write_text("def build(items=None):\n    return items or []\n", encoding="utf-8")
    history: tuple[dict[str, int], set[str]] = ({}, set())
    queue = score_unopened(
        tmp_path,
        [],
        INITIAL_SLOPES,
        files=[cold, hot],
        history=history,
    )
    by_file = {item["file"]: item for item in queue}
    assert int(by_file["src/hot.py"]["findings"]) >= 1
    assert int(by_file["src/cold.py"]["findings"]) == 0
    assert queue[0]["file"] == "src/hot.py"


def test_bug_likelihood_outranks_a_tiny_high_churn_file() -> None:
    """Bluetooth shape: 161 fix commits on 4 lines loses to a long test file."""
    from hive_planner.bug_hunt import bug_likelihood, rank_queue_score, score_signals

    version = rank_queue_score(
        score_signals([161, 1, 0, 0, 0, 0]),
        0,
        likelihood=bug_likelihood(lines=4, branches=0, calls=0, findings=0, untested=True),
    )
    router_tests = rank_queue_score(
        score_signals([45, 1, 1, 0, 0, 0]),
        0,
        likelihood=bug_likelihood(lines=2198, branches=80, calls=400, findings=0, untested=False),
    )
    assert router_tests > version
    assert rank_queue_score(score_signals([161, 1, 0, 0, 0, 0]), 0) > version


def test_score_unopened_does_not_open_a_test_file_as_a_hunt_location(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, score_unopened

    version = tmp_path / "src" / "pkg" / "__init__.py"
    tests = tmp_path / "tests" / "test_router.py"
    version.parent.mkdir(parents=True)
    tests.parent.mkdir(parents=True)
    version.write_text('"""package"""\n\n__version__ = "0.3.204"\n', encoding="utf-8")
    tests.write_text(
        "def test_route():\n" + "    if True:\n        helper()\n" * 40,
        encoding="utf-8",
    )
    ranked = score_unopened(
        tmp_path,
        [],
        INITIAL_SLOPES,
        files=[version, tests],
        history=({"src/pkg/__init__.py": 161, "tests/test_router.py": 45}, set()),
    )
    assert [item["file"] for item in ranked] == ["src/pkg/__init__.py"]


def test_clean_activity_cannot_outrank_a_smaller_finding_file(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import score_unopened

    small = tmp_path / "src" / "small.py"
    huge = tmp_path / "src" / "huge.py"
    small.parent.mkdir(parents=True)
    small.write_text("def build(items=[]):\n    return items\n", encoding="utf-8")
    huge.write_text("x = 1\n" * 3000, encoding="utf-8")
    history: tuple[dict[str, int], set[str]] = ({"src/huge.py": 200}, set())
    queue = score_unopened(
        tmp_path,
        [],
        (1_000_000.0, 1_000_000.0, 1_000_000.0, 0.0, 0.0, 0.0),
        files=[huge, small],
        history=history,
        trust_draw=-1_000_000.0,
        place_draws={"src": -1_000_000.0},
    )
    assert queue[0]["file"] == "src/small.py"


def test_huge_finding_count_stays_finite(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import _likelihood_from_row, bug_likelihood

    saved = {
        "file": "missing.py",
        "signals": {"thin_test": 0.0},
        "findings": 10**10000,
        "lines": 1,
        "likelihood": 2.0,
    }
    rebuilt = _likelihood_from_row(tmp_path, saved)
    direct = bug_likelihood(lines=1, branches=0, calls=0, findings=10**10000, untested=False)
    assert math.isfinite(rebuilt) and math.isfinite(direct)
    assert rebuilt > 13 and direct > 13


def test_squash_stays_inside_the_open_cap() -> None:
    from hive_planner.bug_hunt import ACTIVITY_CAP, SURFACE_CAP, _squash_activity, bug_likelihood

    hi = _squash_activity(1_000_000.0)
    lo = _squash_activity(-1_000_000.0)
    assert -ACTIVITY_CAP < lo < _squash_activity(1.0) < hi < ACTIVITY_CAP
    surface = bug_likelihood(
        lines=10**12, branches=10**12, calls=10**12, findings=0, untested=False
    )
    assert 0.0 < surface < SURFACE_CAP


def test_findings_outrank_a_larger_file_with_none() -> None:
    from hive_planner.bug_hunt import bug_likelihood

    smaller = bug_likelihood(lines=500, branches=20, calls=40, findings=1, untested=False)
    larger = bug_likelihood(lines=3000, branches=80, calls=400, findings=0, untested=False)
    assert smaller > larger


def test_likelihood_rebuild_skips_a_file_over_the_byte_cap(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import _likelihood_from_row, bug_likelihood

    big = tmp_path / "src" / "big.py"
    big.parent.mkdir(parents=True)
    big.write_bytes(b"if True:\n    helper()\n" * 30000)
    saved = {
        "file": "src/big.py",
        "signals": {"thin_test": 0.0},
        "findings": 1,
        "lines": 1,
    }
    rebuilt = _likelihood_from_row(tmp_path, saved)
    assert rebuilt == bug_likelihood(lines=1, branches=0, calls=0, findings=1, untested=False)


def test_likelihood_rebuild_ignores_an_embedded_drive(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import _likelihood_from_row, bug_likelihood

    saved = {
        "file": "src/C:secret.py",
        "signals": {"thin_test": 0.0},
        "findings": 1,
        "lines": 1,
    }
    rebuilt = _likelihood_from_row(tmp_path, saved)
    assert rebuilt == bug_likelihood(lines=1, branches=0, calls=0, findings=1, untested=False)


def test_likelihood_rebuild_ignores_a_path_outside_the_repo(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import _likelihood_from_row, bug_likelihood

    outside = tmp_path / "outside.py"
    outside.write_text("if True:\n    helper()\n" * 5, encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    saved = {
        "file": "../outside.py",
        "signals": {"thin_test": 0.0},
        "findings": 1,
        "lines": 1,
    }
    rebuilt = _likelihood_from_row(repo, saved)
    assert rebuilt == bug_likelihood(lines=1, branches=0, calls=0, findings=1, untested=False)


def test_stale_likelihood_below_the_finding_step_is_rebuilt(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import _likelihood_from_row

    small = tmp_path / "src" / "small.py"
    small.parent.mkdir(parents=True)
    small.write_text("def build(items=[]):\n    return items\n", encoding="utf-8")
    saved = {
        "file": "src/small.py",
        "signals": {"thin_test": 1.0},
        "findings": 1,
        "lines": 2,
        "likelihood": 2.0,
    }
    rebuilt = _likelihood_from_row(tmp_path, saved)
    assert rebuilt > 13.0


def test_empty_file_rebuild_does_not_keep_stale_lines(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import _likelihood_from_row, bug_likelihood

    empty = tmp_path / "src" / "gone.py"
    empty.parent.mkdir(parents=True)
    empty.write_text("", encoding="utf-8")
    saved = {
        "file": "src/gone.py",
        "signals": {"thin_test": 0.0},
        "findings": 1,
        "lines": 5000,
    }
    rebuilt = _likelihood_from_row(tmp_path, saved)
    assert rebuilt == bug_likelihood(lines=1, branches=0, calls=0, findings=1, untested=False)


def test_old_queue_row_without_likelihood_is_rebuilt(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import _likelihood_from_row, _queue_row_for_write, bug_likelihood

    small = tmp_path / "src" / "small.py"
    small.parent.mkdir(parents=True)
    small.write_text("def build(items=[]):\n    return items\n", encoding="utf-8")
    saved = {
        "file": "src/small.py",
        "signals": {"thin_test": 1.0},
        "score": 1.0,
        "findings": 1,
        "lines": 2,
    }
    rebuilt = _likelihood_from_row(tmp_path, saved)
    assert rebuilt >= bug_likelihood(lines=2, branches=0, calls=0, findings=1, untested=True)
    written = _queue_row_for_write({**saved, "likelihood": rebuilt})
    assert written["likelihood"] == rebuilt


def test_place_rescore_keeps_likelihood(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, advance_rank_pass

    small = tmp_path / "src" / "small.py"
    huge = tmp_path / "src" / "huge.py"
    small.parent.mkdir(parents=True)
    small.write_text("def build(items=[]):\n    return items\n", encoding="utf-8")
    huge.write_text("x = 1\n" * 3000, encoding="utf-8")
    summary = advance_rank_pass(
        tmp_path,
        None,
        fresh=True,
        files=[small, huge],
        history=({}, set()),
        rng=__import__("random").Random(0),
    )
    assert summary["top"] == "src/small.py"


def test_rank_queue_score_mixes_trust_and_place_not_a_fixed_bonus() -> None:
    from hive_planner.bug_hunt import rank_queue_score, rebuild_mean, score_signals

    six = score_signals([0, 1, 0, 0, 0, 0])
    assert rank_queue_score(six, 0) == six
    assert rank_queue_score(six, 1, trust_draw=2.0) == six + 2.0
    assert rank_queue_score(six, 4, trust_draw=2.0) == six + 2.0
    assert rank_queue_score(six, 1, trust_draw=-3.0, place_draw=0.5) == six - 3.0 + 0.5
    assert rank_queue_score(six, 0, trust_draw=9.0, place_draw=1.0) == six + 1.0
    assert rank_queue_score(six, True, trust_draw=2.0) == six
    mean, evidence = rebuild_mean(
        [{"signals": [0, 1, 0, 0, 0, 0], "outcome": "committed"}]
    )
    assert len(mean) == 6
    assert evidence > 0
    assert rank_queue_score(six, 1, trust_draw="bad", place_draw=1.0) == 0.0


def test_exploration_bonus_is_bounded_and_loses_coverage_novelty() -> None:
    from hive_planner.bug_hunt import exploration_bonus

    cold = exploration_bonus(20.0, 20.0, 20.0, 0, 0)
    observed = exploration_bonus(20.0, 20.0, 20.0, 4, 8)

    assert cold == pytest.approx(0.25)
    assert 0.0 <= observed < cold


def test_attribution_uses_log_fix_commit_feature() -> None:
    from hive_planner.bug_hunt import _attribution

    attribution = _attribution(
        rel="src/a.py",
        mode="rank",
        values=[3.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        draw=[2.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        findings=0,
        trust_draw=0.0,
        place_draw=0.0,
        likelihood=0.0,
        exploit_score=2.0 * math.log1p(3.0),
        exploration=0.0,
    )

    assert attribution["six_signal"]["recent_fix_commits"] == pytest.approx(2.0 * math.log1p(3.0))


def test_direct_override_is_qualified_and_calibrated(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt import advance_rank_pass

    target = tmp_path / "src" / "plain.py"
    target.parent.mkdir(parents=True)
    target.write_text("value = 1\n", encoding="utf-8")
    state = {"requested_file": "src/plain.py", "requested_line": 1}

    first = advance_rank_pass(tmp_path, state, fresh=True, files=[target], rng=random.Random(2))
    assert first["top"] == "src/plain.py"
    pass_state = json.loads((tmp_path / ".hive" / "bug-hunt" / "rank-pass.json").read_text())
    attribution = pass_state["queue"][0]["attribution"]
    assert attribution["mode"] == "override"
    assert attribution["final_score"] == pytest.approx(
        attribution["exploit_score"] + attribution["exploration"]
    )
    assert "likelihood" in attribution["top"]
    assert "exploration" in attribution["top"]

    advance_rank_pass(
        tmp_path,
        {
            "file": "src/plain.py",
            "scenario": "direct override",
            "outcome": "committed",
            "requested_file": "src/plain.py",
            "requested_line": 1,
        },
        files=[target],
        rng=random.Random(2),
    )
    calibration = (tmp_path / ".hive" / "bug-hunt" / "calibration.jsonl").read_text()
    assert json.loads(calibration)["file"] == "src/plain.py"


def test_invalid_direct_override_fails_before_appending_outcome(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import BugHuntError, advance_rank_pass

    target = tmp_path / "src" / "plain.py"
    target.parent.mkdir(parents=True)
    target.write_text("value = 1\n", encoding="utf-8")

    with pytest.raises(BugHuntError, match="requested_line"):
        advance_rank_pass(
            tmp_path,
            {
                "file": "src/plain.py",
                "scenario": "invalid override",
                "outcome": "committed",
                "requested_file": "src/plain.py",
                "requested_line": 99,
            },
            fresh=True,
            files=[target],
        )

    assert not (tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl").exists()


def test_boolean_direct_override_line_is_rejected(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import BugHuntError, advance_rank_pass

    target = tmp_path / "src" / "plain.py"
    target.parent.mkdir(parents=True)
    target.write_text("value = 1\n", encoding="utf-8")

    with pytest.raises(BugHuntError, match="requested_line"):
        advance_rank_pass(
            tmp_path,
            {
                "file": "src/plain.py",
                "scenario": "boolean line",
                "outcome": "committed",
                "requested_file": "src/plain.py",
                "requested_line": True,
            },
            fresh=True,
            files=[target],
        )

    assert not (tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl").exists()


@pytest.mark.parametrize("requested_line", [1.5, 0])
def test_non_integer_or_empty_file_override_line_is_rejected(
    tmp_path: Path, requested_line: object
) -> None:
    from hive_planner.bug_hunt import BugHuntError, advance_rank_pass

    target = tmp_path / "src" / "plain.py"
    target.parent.mkdir(parents=True)
    target.write_text("" if requested_line == 0 else "value = 1\n", encoding="utf-8")

    match = "positive integer"
    with pytest.raises(BugHuntError, match=match):
        advance_rank_pass(
            tmp_path,
            {
                "file": "src/plain.py",
                "scenario": "line boundary",
                "outcome": "committed",
                "requested_file": "src/plain.py",
                "requested_line": requested_line,
            },
            fresh=True,
            files=[target],
        )

    assert not (tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl").exists()


def test_empty_file_override_line_is_rejected(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import BugHuntError, advance_rank_pass

    target = tmp_path / "src" / "empty.py"
    target.parent.mkdir(parents=True)
    target.write_text("", encoding="utf-8")

    with pytest.raises(BugHuntError, match="outside the file"):
        advance_rank_pass(
            tmp_path,
            {
                "file": "src/empty.py",
                "scenario": "empty line boundary",
                "outcome": "committed",
                "requested_file": "src/empty.py",
                "requested_line": 1,
            },
            fresh=True,
            files=[target],
        )

    assert not (tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl").exists()


def test_calibration_io_failure_does_not_replay_learning_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from hive_planner.bug_hunt import advance_rank_pass

    target = tmp_path / "src" / "plain.py"
    target.parent.mkdir(parents=True)
    target.write_text("value = 1\n", encoding="utf-8")

    advance_rank_pass(
        tmp_path,
        {"requested_file": "src/plain.py", "requested_line": 1},
        fresh=True,
        files=[target],
        rng=random.Random(2),
    )

    def fail_calibration(*args: object, **kwargs: object) -> None:
        from hive_planner.bug_hunt import BugHuntError

        raise BugHuntError("calibration unavailable")

    monkeypatch.setattr("hive_planner.bug_hunt._append_calibration", fail_calibration)
    advance_rank_pass(
        tmp_path,
        {
            "file": "src/plain.py",
            "scenario": "calibration failure",
            "outcome": "committed",
            "requested_file": "src/plain.py",
            "requested_line": 1,
        },
        files=[target],
        rng=random.Random(2),
    )

    rows = [
        json.loads(line)
        for line in (tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl").read_text().splitlines()
    ]
    assert len(rows) == 1


def test_draw_width_stays_finite_on_bad_evidence() -> None:
    from hive_planner.bug_hunt import draw_width

    assert draw_width(20.0, 1.0) > 0.0
    assert draw_width(0.0, 1.0) == 1.0
    assert draw_width(float("nan"), 2.0) == 2.0
    assert draw_width(20.0, float("inf")) == pytest.approx(1.0 / math.sqrt(20.0))
    assert draw_width(-1.0, 1.0) == 1.0
    assert draw_width(float("inf"), 1.0) == 0.0


def test_rebuild_mean_falls_back_when_slot_is_non_finite() -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, rebuild_mean, rebuild_scalar_mean

    huge = {
        "outcome": "committed",
        "signals": [1e308, 1e308, 1e308, 1e308, 1e308, 1e308],
        "findings": 1,
        "file": "src/a.py",
    }
    mean, evidence = rebuild_mean([huge, huge, huge])
    assert mean == INITIAL_SLOPES
    assert evidence > 0.0
    trust, _mass = rebuild_scalar_mean(
        [{"outcome": "committed", "findings": 1}],
        float("inf"),
        lambda row: True,
    )
    assert math.isfinite(trust)


def test_rebuild_mean_preserves_supplied_seed_on_non_finite_update() -> None:
    from hive_planner.bug_hunt import rebuild_mean

    seed = (9.0, 8.0, 7.0, -0.5, 6.0, 5.0)
    huge = {
        "outcome": "committed",
        "signals": [1e308, 1e308, 1e308, 1e308, 1e308, 1e308],
        "findings": 1,
        "file": "src/a.py",
    }

    mean, evidence = rebuild_mean([huge, huge, huge], seed=seed)

    assert mean == seed
    assert evidence > 0.0


def test_bool_score_is_not_a_ranking_disagreement() -> None:
    from hive_planner.bug_hunt import _finite_score, _surprise_score, queue_sort_key, surprise_scale

    assert _finite_score(True) == 0.0
    assert _surprise_score({"score": True}) is None
    assert surprise_scale([{"outcome": "empty", "score": True}]) == 1.0
    assert queue_sort_key({"file": "a.py", "score": True, "findings": 0, "lines": 1})[0] == -0.0


def test_thompson_draw_rejects_bad_mean() -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, thompson_draw, thompson_scalar

    rng = random.Random(0)
    draw = thompson_draw((float("nan"),) * 6, 20.0, rng, 1.0)
    assert len(draw) == 6
    assert all(math.isfinite(value) for value in draw)
    seed = random.Random(1)
    expected = thompson_draw(INITIAL_SLOPES, 20.0, random.Random(1), 1.0)
    again = thompson_draw((float("inf"),) * 6, 20.0, seed, 1.0)
    assert again == expected
    assert math.isfinite(thompson_scalar(float("nan"), 20.0, random.Random(2), 1.0))


def test_findings_sort_edges_empty_negative_ties_and_extreme_draw(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, queue_sort_key, score_unopened

    assert score_unopened(tmp_path, [], INITIAL_SLOPES, files=[], history=({}, set())) == []

    tied = [
        {"file": "src/one.py", "score": 1003.3024, "findings": 1, "lines": 4},
        {"file": "src/many.py", "score": 1003.3024, "findings": 4, "lines": 4},
    ]
    tied.sort(key=queue_sort_key)
    assert tied[0]["file"] == "src/many.py"

    hot = tmp_path / "src" / "hot.py"
    cold = tmp_path / "src" / "cold.py"
    hot.parent.mkdir(parents=True)
    hot.write_text("def build(items=[]):\n    return items\n", encoding="utf-8")
    cold.write_text("def add(left, right):\n    return left + right\n", encoding="utf-8")
    history: tuple[dict[str, int], set[str]] = ({"src/cold.py": 80}, set())
    negative = score_unopened(
        tmp_path,
        [],
        (-1.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        files=[cold, hot],
        history=history,
    )
    assert negative[0]["file"] == "src/hot.py"
    extreme = score_unopened(
        tmp_path,
        [],
        (1_000_000.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        files=[cold, hot],
        history=history,
    )
    assert extreme[0]["file"] == "src/hot.py"
    assert int(extreme[0]["findings"]) >= 1


def test_detector_finding_qualifies_when_six_signals_are_zero(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, score_unopened

    hot = tmp_path / "src" / "hot.py"
    paired = tmp_path / "tests" / "test_hot.py"
    hot.parent.mkdir(parents=True)
    paired.parent.mkdir(parents=True)
    hot.write_text("def build(items=[]):\n    return items\n", encoding="utf-8")
    paired.write_text("def test_hot():\n    assert True\n", encoding="utf-8")
    queue = score_unopened(
        tmp_path,
        [],
        INITIAL_SLOPES,
        files=[hot],
        history=({}, set()),
    )
    assert queue
    assert queue[0]["file"] == "src/hot.py"
    assert int(queue[0]["findings"]) >= 1
    signals = queue[0]["signals"]
    assert isinstance(signals, dict)
    assert any(float(signals[key]) != 0.0 for key in signals) or int(queue[0]["findings"]) >= 1


def test_fallback_row_keeps_git_signals(tmp_path: Path) -> None:
    path = tmp_path / "src" / "a.py"
    path.parent.mkdir(parents=True)
    path.write_text("def unused():\n    return 1\n", encoding="utf-8")
    history = ({"src/a.py": 4}, set())
    advance_rank_pass(
        tmp_path,
        {"file": "src/a.py", "outcome": "review-failed", "scenario": "fix commits"},
        fresh=False,
        rng=random.Random(1),
        files=[path],
        history=history,
    )
    rows = load_rank_rows(tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl")
    assert rows[-1]["signals"]["recent_fix_commits"] == 4
    assert rows[-1]["findings"] == 0
    assert rows[-1]["score"] == 0.0


def test_append_rank_row_persists_findings_and_score(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import _append_rank_row, load_rank_rows

    _append_rank_row(
        tmp_path,
        "src/a.py",
        {
            "recent_fix_commits": 0.0,
            "thin_test": 0.0,
            "wiring_hop": 1.0,
            "dead_setting": 0.0,
            "reverted": 0.0,
            "split_stores": 0.0,
        },
        "x",
        "empty",
        findings=3,
        score=12.5,
    )
    rows = load_rank_rows(tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl")
    assert rows[-1]["findings"] == 3
    assert rows[-1]["score"] == 12.5

    _append_rank_row(
        tmp_path,
        "src/b.py",
        {
            "recent_fix_commits": 0.0,
            "thin_test": 0.0,
            "wiring_hop": 1.0,
            "dead_setting": 0.0,
            "reverted": 0.0,
            "split_stores": 0.0,
        },
        "x",
        "empty",
        findings="nope",
        score=float("nan"),
    )
    rows = load_rank_rows(tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl")
    assert rows[-1]["findings"] == 0
    assert rows[-1]["score"] == 0.0


def test_signal_list_rejects_bool_slots() -> None:
    from hive_planner.bug_hunt import SIGNAL_KEYS, _signal_list, rebuild_mean, INITIAL_SLOPES

    raw = {key: 0.0 for key in SIGNAL_KEYS}
    raw["thin_test"] = True
    assert _signal_list(raw) is None
    mean, _evidence = rebuild_mean(
        [{"signals": raw, "outcome": "committed"}]
    )
    assert mean == INITIAL_SLOPES


def test_signal_list_accepts_six_tuple() -> None:
    from hive_planner.bug_hunt import _signal_list

    parsed = _signal_list((0.0, 1.0, 2.0, 3.0, 4.0, 5.0))
    assert parsed == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]


def test_score_signals_overflow_is_value_error() -> None:
    from hive_planner.bug_hunt import score_signals

    class Huge:
        def __float__(self) -> float:
            raise OverflowError

    with pytest.raises(ValueError, match="non-numeric"):
        score_signals([0.0, Huge(), 0.0, 0.0, 0.0, 0.0])


def test_finite_score_overflow_is_zero() -> None:
    from hive_planner.bug_hunt import _finite_score, _surprise_score, queue_sort_key

    class Huge:
        def __float__(self) -> float:
            raise OverflowError

    assert _finite_score(Huge()) == 0.0
    assert _surprise_score({"score": Huge()}) is None
    assert queue_sort_key({"file": "a.py", "score": Huge()}) == (-0.0, 0, 0, "a.py")


def test_score_unopened_skips_unreadable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner import bug_hunt
    from hive_planner.bug_hunt import INITIAL_SLOPES, score_unopened

    target = tmp_path / "src" / "blocked.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n", encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise OSError("locked")

    monkeypatch.setattr(bug_hunt, "_signals_for_file", boom)
    ranked = score_unopened(
        tmp_path,
        [],
        INITIAL_SLOPES,
        files=[target],
        history=({}, set()),
    )
    assert ranked == []


def test_later_hunt_appends_row_when_last_jsonl_file_matches(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt import RANK_ROWS_REL, _append_rank_row, load_rank_rows

    zeros = {
        "recent_fix_commits": 0.0,
        "thin_test": 1.0,
        "wiring_hop": 0.0,
        "dead_setting": 0.0,
        "reverted": 0.0,
        "split_stores": 0.0,
    }
    _append_rank_row(tmp_path, "src/a.py", zeros, "prior hunt", "committed", findings=1, score=1.0)
    target = tmp_path / "src" / "a.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n", encoding="utf-8")
    pass_path = tmp_path / ".hive" / "bug-hunt" / "rank-pass.json"
    pass_path.write_text(
        '{"opened": [], "queue": [{"file": "src/a.py", "signals": '
        + json.dumps(zeros)
        + ', "findings": 2, "score": 4.5, "lines": 1}]}\n',
        encoding="utf-8",
    )
    advance_rank_pass(
        tmp_path,
        {"file": "src/a.py", "scenario": "new hunt", "outcome": "empty"},
        fresh=False,
        rng=random.Random(0),
        files=[target],
        history=({}, set()),
    )
    rows = load_rank_rows(tmp_path / RANK_ROWS_REL)
    assert len(rows) == 2
    assert rows[-1]["file"] == "src/a.py"
    assert rows[-1]["outcome"] == "empty"
    assert rows[-1]["findings"] == 2
    assert rows[-1]["score"] == 4.5


def test_finding_count_rejects_lists_and_bools() -> None:
    from hive_planner.bug_hunt import _finding_count

    assert _finding_count([{"kind": "hit"}]) == 0
    assert _finding_count(True) == 0
    assert _finding_count("3") == 3
    assert _finding_count("2.0") == 2
    assert _finding_count("2.5") == 0
    assert _finding_count("nan") == 0
    assert _finding_count(float("nan")) == 0


def test_load_rank_rows_skips_nan_findings_and_memory_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.bug_hunt import TRUST_SEED, load_rank_rows, rebuild_trust

    path = tmp_path / "rank-rows.jsonl"
    path.write_text(
        '{"file": "a.py", "outcome": "empty", "findings": NaN, "score": 1}\n'
        '{"file": "b.py", "outcome": "committed", "findings": 1, "score": 1}\n',
        encoding="utf-8",
    )
    rows = load_rank_rows(path)
    assert len(rows) == 2
    mean, _evidence = rebuild_trust(rows)
    assert mean == pytest.approx(TRUST_SEED + 1.0 / 3.0)

    def _boom(_text: str, *args: object, **kwargs: object):
        raise MemoryError("line too large")

    monkeypatch.setattr("hive_planner.bug_hunt.json.loads", _boom)
    assert load_rank_rows(path) == []


def test_load_rank_rows_memory_error_on_read_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.bug_hunt import load_rank_rows

    path = tmp_path / "rank-rows.jsonl"
    path.write_text("{}\n", encoding="utf-8")

    def _boom(self: Path, *args: object, **kwargs: object) -> str:
        raise MemoryError("file too large")

    monkeypatch.setattr(Path, "read_text", _boom)
    assert load_rank_rows(path) == []


def test_advance_copies_queue_findings_and_score_before_rewrite(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt import RANK_PASS_REL, RANK_ROWS_REL, advance_rank_pass

    target = tmp_path / "src" / "a.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n", encoding="utf-8")
    pass_path = tmp_path / RANK_PASS_REL
    pass_path.parent.mkdir(parents=True)
    pass_path.write_text(
        json.dumps(
            {
                "opened": [],
                "queue": [
                    {
                        "file": "src/a.py",
                        "signals": {
                            "recent_fix_commits": 0.0,
                            "thin_test": 1.0,
                            "wiring_hop": 0.0,
                            "dead_setting": 0.0,
                            "reverted": 0.0,
                            "split_stores": 0.0,
                        },
                        "findings": 4,
                        "score": 7.5,
                        "lines": 2,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    advance_rank_pass(
        tmp_path,
        {"file": "src/a.py", "scenario": "scan", "outcome": "empty"},
        fresh=False,
        rng=random.Random(0),
        files=[target],
        history=({}, set()),
    )
    rows = load_rank_rows(tmp_path / RANK_ROWS_REL)
    assert rows[-1]["file"] == "src/a.py"
    assert rows[-1]["findings"] == 4
    assert rows[-1]["score"] == 7.5


def test_subsystem_uses_first_slash_part() -> None:
    from hive_planner.bug_hunt import _subsystem

    assert _subsystem("readme.md") == "."
    assert _subsystem(".cursor/hooks/x.py") == ".cursor"
    assert _subsystem("src/hive_planner/bug_hunt.py") == "src"
    assert _subsystem("") == "."


def test_stopping_pass_saves_the_outcome_row(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt_continue import apply_continue

    target = tmp_path / "src" / "a.py"
    target.parent.mkdir(parents=True)
    target.write_text("def unused():\n    return 1\n", encoding="utf-8")
    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "active": True,
                "pause_seconds": 0,
                "ceiling": 1,
                "committed": 1,
                "file": "src/a.py",
                "scenario": "last fix",
                "outcome": "committed",
            }
        ),
        encoding="utf-8",
    )
    assert apply_continue(tmp_path, sleep=lambda _seconds: None) == {}
    rows = (tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl").read_text(encoding="utf-8")
    assert "src/a.py" in rows
    assert "committed" in rows


def test_empty_stop_pass_saves_rank_row_when_active_already_false(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt_continue import apply_continue

    target = tmp_path / "tests" / "test_gpu_governor.py"
    target.parent.mkdir(parents=True)
    target.write_text("def test_gpu_governor():\n    assert True\n", encoding="utf-8")
    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "active": False,
                "pause_seconds": 10,
                "ceiling": 50,
                "committed": 2,
                "consecutive_empty": 2,
                "file": "tests/test_gpu_governor.py",
                "scenario": "empty search",
                "outcome": "empty",
            }
        ),
        encoding="utf-8",
    )
    assert apply_continue(tmp_path, sleep=lambda _seconds: None) == {}
    rows = (tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl").read_text(encoding="utf-8").splitlines()
    assert any("test_gpu_governor.py" in line and '"empty"' in line for line in rows)
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False
    assert apply_continue(tmp_path, sleep=lambda _seconds: None) == {}
    assert len((tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl").read_text(encoding="utf-8").splitlines()) == len(
        rows
    )


def test_continue_hook_ranks_the_next_pass(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt_continue import apply_continue

    target = tmp_path / "src" / "next.py"
    target.parent.mkdir(parents=True)
    target.write_text("def unused():\n    return 1\n", encoding="utf-8")
    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "active": True,
                "pause_seconds": 0,
                "file": "src/next.py",
                "scenario": "unused",
                "outcome": "committed",
            }
        ),
        encoding="utf-8",
    )
    payload = apply_continue(tmp_path, sleep=lambda _seconds: None)
    assert "Do not rebuild the weights yourself" in payload["followup_message"] or "no qualifying" in payload["followup_message"]
    rows = (tmp_path / ".hive" / "bug-hunt" / "rank-rows.jsonl").read_text(encoding="utf-8")
    assert "committed" in rows
    saved = json.loads((tmp_path / ".hive" / "bug-hunt" / "rank-pass.json").read_text(encoding="utf-8"))
    assert len(saved["draw"]) == 6
    assert all("draw" not in item for item in saved["queue"])


def test_rebuild_trust_falls_after_empty_on_finding() -> None:
    from hive_planner.bug_hunt import TRUST_SEED, rebuild_trust

    seed_mean, _seed_ev = rebuild_trust([])
    assert seed_mean == pytest.approx(TRUST_SEED)
    rows = [
        {"file": "src/a.py", "findings": 1, "outcome": "empty"},
        {"file": "src/b.py", "findings": 1, "outcome": "empty"},
        {"file": "src/c.py", "findings": 0, "outcome": "empty"},
        {"file": "src/d.py", "findings": 1, "outcome": "skipped"},
    ]
    mean, _evidence = rebuild_trust(rows)
    assert mean < TRUST_SEED
    skipped_only = rebuild_trust([{"file": "src/a.py", "findings": 1, "outcome": "skipped"}])[0]
    assert skipped_only == pytest.approx(TRUST_SEED)


def test_empty_confidence_scales_negative_learning() -> None:
    from hive_planner.bug_hunt import rebuild_mean

    full = rebuild_mean(
        [{"file": "src/a.py", "signals": {"recent_fix_commits": 1, "thin_test": 0, "wiring_hop": 0, "dead_setting": 0, "reverted": 0, "split_stores": 0}, "outcome": "empty"}]
    )[0]
    half = rebuild_mean(
        [{"file": "src/a.py", "signals": {"recent_fix_commits": 1, "thin_test": 0, "wiring_hop": 0, "dead_setting": 0, "reverted": 0, "split_stores": 0}, "outcome": "empty", "empty_confidence": 0.5}]
    )[0]
    assert half[0] > full[0]


def test_recovery_hook_appends_before_state_and_prefers_new_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    import hive_planner.bug_hunt as ranker
    from hive_planner.bug_hunt_continue import apply_continue

    (tmp_path / "src").mkdir()
    (tmp_path / "lib").mkdir()
    (tmp_path / "src" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "lib" / "b.py").write_text("def b():\n    return 1\n", encoding="utf-8")

    def fake_signals(_path, rel, **_kwargs):
        return (
            {"recent_fix_commits": 0.0, "thin_test": 1.0, "wiring_hop": 0.0, "dead_setting": 0.0, "reverted": 0.0, "split_stores": 0.0},
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
                "opened": [],
                "queue": [
                    {"file": "src/a.py", "signals": {"thin_test": 1}, "findings": 0, "score": 2},
                    {"file": "lib/b.py", "signals": {"thin_test": 1}, "findings": 0, "score": 1},
                ],
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
                "consecutive_empty": 2,
                "file": "src/a.py",
                "scenario": "empty",
                "outcome": "empty",
                "empty_confidence": 0.25,
                "recovery_lens": "ui-event",
            }
        ),
        encoding="utf-8",
    )
    payload = apply_continue(tmp_path, sleep=lambda _seconds: None)
    recovery = json.loads((state_dir / "recovery.json").read_text(encoding="utf-8"))
    rows = (state_dir / "rank-rows.jsonl").read_text(encoding="utf-8").splitlines()
    queue = json.loads((state_dir / "rank-pass.json").read_text(encoding="utf-8"))["queue"]
    assert payload["followup_message"]
    assert recovery["phase"] == "recovery"
    assert recovery["excluded_locations"] == ["src/a.py"]
    assert json.loads(rows[0])["empty_confidence"] == pytest.approx(0.25)
    assert queue[0]["file"] == "lib/b.py"


def test_rebuild_place_holds_empty_folder_at_zero() -> None:
    from hive_planner.bug_hunt import PLACE_SEED, rebuild_place

    rows = [
        {"file": "src/a.py", "outcome": "empty"},
        {"file": "src/b.py", "outcome": "empty"},
        {"file": "tests/t.py", "outcome": "committed"},
    ]
    src_mean, src_ev = rebuild_place(rows, "src")
    tests_mean, _tests_ev = rebuild_place(rows, "tests")
    unused_mean, unused_ev = rebuild_place(rows, "lib")
    assert src_mean == pytest.approx(0.0)
    assert src_ev != pytest.approx(20.0)
    assert tests_mean > PLACE_SEED
    assert unused_mean == pytest.approx(PLACE_SEED)
    assert unused_ev == pytest.approx(20.0)


def test_surprise_scale_widens_on_mismatch_and_on_rows_without_findings() -> None:
    from hive_planner.bug_hunt import surprise_scale

    assert surprise_scale([]) == 1.0
    missing = [{"outcome": "empty"}, {"outcome": "committed"}]
    assert surprise_scale(missing) == pytest.approx(2.0)
    stored = [
        {"outcome": "empty", "findings": 0},
        {"outcome": "committed", "findings": 0},
    ]
    assert surprise_scale(stored) == 1.0
    matched = [
        {"outcome": "committed", "score": 2.0},
        {"outcome": "empty", "score": -1.0},
    ]
    assert surprise_scale(matched) == 1.0
    missed = [
        {"outcome": "empty", "score": 4.0},
        {"outcome": "committed", "score": -1.0},
    ]
    assert surprise_scale(missed) == pytest.approx(2.0)
    skipped = [{"outcome": "skipped", "score": 9.0}, {"outcome": "empty", "score": 1.0}]
    assert surprise_scale(skipped) == pytest.approx(2.0)
    assert surprise_scale([{"outcome": "committed", "score": False}]) == 1.0


def test_finding_step_beats_a_negative_trust_draw(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import score_unopened

    hot = tmp_path / "src" / "hot.py"
    cold = tmp_path / "src" / "cold.py"
    hot.parent.mkdir(parents=True)
    hot.write_text("def build(items=[]):\n    return items\n", encoding="utf-8")
    cold.write_text("def add(left, right):\n    return left + right\n", encoding="utf-8")
    history: tuple[dict[str, int], set[str]] = ({}, set())
    queue = score_unopened(
        tmp_path,
        [],
        (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        files=[cold, hot],
        history=history,
        trust_draw=-1.0,
    )
    assert queue[0]["file"] == "src/hot.py"
    assert int(queue[0]["findings"]) >= 1


def test_place_empty_in_src_can_prefer_other_folder(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import score_unopened

    src_file = tmp_path / "src" / "a.py"
    lib_file = tmp_path / "lib" / "b.py"
    for path in (src_file, lib_file):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def unused():\n    return 1\n", encoding="utf-8")
    queue = score_unopened(
        tmp_path,
        [],
        (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        files=[src_file, lib_file],
        history=({}, set()),
        place_draws={"src": -2.0, "lib": 0.5},
    )
    assert queue[0]["file"] == "lib/b.py"


def test_queue_persists_top_limit_after_scoring_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    monkeypatch.setattr("hive_planner.bug_hunt.QUEUE_LIMIT", 2)
    files = []
    for name in ("a.py", "b.py", "c.py"):
        path = tmp_path / "src" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def unused():\n    return 1\n", encoding="utf-8")
        files.append(path)
    summary = advance_rank_pass(
        tmp_path,
        None,
        fresh=True,
        rng=random.Random(1),
        files=files,
        history=({}, set()),
    )
    queued = json.loads((tmp_path / ".hive" / "bug-hunt" / "rank-pass.json").read_text(encoding="utf-8"))
    assert len(queued["queue"]) == 2
    assert summary["top"] == queued["queue"][0]["file"]
    assert len(queued["draw"]) == 6
    assert all("draw" not in item for item in queued["queue"])


def test_stop_without_outcome_appends_row_and_spares_queue_head(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt import RANK_ROWS_REL, load_rank_rows, save_stopped_outcome

    path = tmp_path / ".hive" / "bug-hunt" / "rank-pass.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "opened": [],
                "queue": [
                    {
                        "file": "src/head.py",
                        "signals": {
                            "recent_fix_commits": 0,
                            "thin_test": 1,
                            "wiring_hop": 0,
                            "dead_setting": 0,
                            "reverted": 0,
                            "split_stores": 0,
                        },
                        "score": 1.0,
                        "findings": 3,
                        "lines": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = save_stopped_outcome(tmp_path, {"active": False, "committed": 50, "ceiling": 50})
    assert result["appended"] is True
    assert result["missing_outcome"] is False
    rows = load_rank_rows(tmp_path / RANK_ROWS_REL)
    assert len(rows) == 1
    assert rows[0]["outcome"] == "stopped"
    assert rows[0]["file"] == ""
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert "src/head.py" not in saved.get("opened", [])
    assert "stop_warning" not in saved
    again = save_stopped_outcome(tmp_path, {"active": False, "committed": 50, "ceiling": 50})
    assert again["appended"] is False
    assert len(load_rank_rows(tmp_path / RANK_ROWS_REL)) == 1
    named = save_stopped_outcome(
        tmp_path,
        {"active": False, "file": "src/named.py", "scenario": "ceiling"},
    )
    assert named["appended"] is True
    named_rows = load_rank_rows(tmp_path / RANK_ROWS_REL)
    assert named_rows[-1]["file"] == "src/named.py"
    assert named_rows[-1]["outcome"] == "stopped"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["opened"] == ["src/named.py"]
    path.write_text(
        json.dumps({"opened": ["src/held.py"], "queue": []}),
        encoding="utf-8",
    )
    held = save_stopped_outcome(tmp_path, {"file": "src/held.py"})
    assert held["appended"] is True
    held_saved = json.loads(path.read_text(encoding="utf-8"))
    assert held_saved["opened"] == ["src/held.py"]
    assert load_rank_rows(tmp_path / RANK_ROWS_REL)[-1]["file"] == "src/held.py"


def test_legacy_rows_without_findings_move_trust() -> None:
    from hive_planner.bug_hunt import TRUST_SEED, rebuild_trust

    legacy_mean, legacy_ev = rebuild_trust([{"file": "src/a.py", "outcome": "empty"}])
    assert legacy_mean < TRUST_SEED
    assert legacy_ev != pytest.approx(20.0)
    held_mean, held_ev = rebuild_trust(
        [{"file": "src/a.py", "findings": 0, "outcome": "empty"}]
    )
    assert held_mean == pytest.approx(TRUST_SEED)
    assert held_ev == pytest.approx(20.0)


def test_rank_pass_draws_trust_as_well_as_six_slopes(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import rank_pass

    rows = tmp_path / "rank-rows.jsonl"
    rows.write_text("", encoding="utf-8")
    result = rank_pass(rows, rng=random.Random(0))
    assert len(result["draw"]) == 6
    assert math.isfinite(float(result["trust_draw"]))
    assert result["trust_mean"] == pytest.approx(1.0)


def test_opened_persists_when_queue_rewrite_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from hive_planner import bug_hunt
    from hive_planner.bug_hunt import RANK_PASS_REL, RANK_ROWS_REL, advance_rank_pass

    target = tmp_path / "src" / "a.py"
    target.parent.mkdir(parents=True)
    target.write_text("def build(items=[]):\n    return items\n", encoding="utf-8")
    files = [target]
    history: tuple[dict[str, int], set[str]] = ({}, set())
    first = advance_rank_pass(
        tmp_path, None, fresh=True, rng=random.Random(1), files=files, history=history
    )
    real_write = bug_hunt._write_json
    calls = {"n": 0}

    def wrapped(path, payload):
        if Path(path).name != "rank-pass.json":
            return real_write(path, payload)
        calls["n"] += 1
        if calls["n"] >= 2:
            raise OSError("queue rewrite failed")
        return real_write(path, payload)

    monkeypatch.setattr(bug_hunt, "_write_json", wrapped)
    with pytest.raises(OSError, match="queue rewrite failed"):
        advance_rank_pass(
            tmp_path,
            {"file": first["top"], "scenario": "empty", "outcome": "empty"},
            rng=random.Random(2),
            files=files,
            history=history,
        )
    saved = json.loads((tmp_path / RANK_PASS_REL).read_text(encoding="utf-8"))
    assert saved["opened"] == [first["top"]]
    queued_files = [item.get("file") for item in saved.get("queue", [])]
    assert first["top"] not in queued_files
    rows = (tmp_path / RANK_ROWS_REL).read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1


def test_failed_append_does_not_skip_file_forever(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from hive_planner.bug_hunt import RANK_PASS_REL, RANK_ROWS_REL, _load_opened

    first = tmp_path / "src" / "opened.py"
    second = tmp_path / "src" / "next.py"
    first.parent.mkdir(parents=True)
    first.write_text("def unused():\n    return 1\n", encoding="utf-8")
    second.write_text("FLAG = 1\n", encoding="utf-8")
    files = [first, second]
    history: tuple[dict[str, int], set[str]] = ({}, set())
    advance_rank_pass(tmp_path, None, fresh=True, rng=random.Random(1), files=files, history=history)
    original_open = Path.open
    block_append = {"on": True}

    def fail_jsonl_append(self, *args, **kwargs):
        mode = args[0] if args else kwargs.get("mode", "r")
        if (
            block_append["on"]
            and self.name == "rank-rows.jsonl"
            and isinstance(mode, str)
            and "a" in mode
        ):
            raise OSError("append failed")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_jsonl_append)
    with pytest.raises(BugHuntError, match="could not append"):
        advance_rank_pass(
            tmp_path,
            {"file": "src/opened.py", "scenario": "dead call", "outcome": "committed"},
            rng=random.Random(2),
            files=files,
            history=history,
        )
    block_append["on"] = False
    rows_path = tmp_path / RANK_ROWS_REL
    assert (not rows_path.is_file()) or rows_path.read_text(encoding="utf-8").strip() == ""
    saved = json.loads((tmp_path / RANK_PASS_REL).read_text(encoding="utf-8"))
    assert "src/opened.py" not in saved["opened"]
    assert "src/opened.py" not in _load_opened(tmp_path)
    retry = advance_rank_pass(
        tmp_path,
        {"file": "src/opened.py", "scenario": "dead call", "outcome": "committed"},
        rng=random.Random(2),
        files=files,
        history=history,
    )
    assert retry["appended"] is True
    assert "src/opened.py" in retry["opened"]
    rows = load_rank_rows(rows_path)
    assert len(rows) == 1
    assert rows[0]["file"] == "src/opened.py"
    assert rows[0]["outcome"] == "committed"


def test_persist_opened_rewrites_nan_queue_scores(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt import RANK_PASS_REL, _persist_opened

    path = tmp_path / RANK_PASS_REL
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "opened": [],
                "queue": [
                    {"file": "src/keep.py", "score": float("nan"), "findings": True, "lines": 3},
                    {"file": "src/done.py", "score": 1.0, "findings": 1},
                ],
            }
        ),
        encoding="utf-8",
    )
    _persist_opened(tmp_path, ["src/done.py"])
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["opened"] == ["src/done.py"]
    assert saved["queue"][0]["file"] == "src/keep.py"
    assert saved["queue"][0]["score"] == 0.0
    assert saved["queue"][0]["findings"] == 0
    assert saved["queue"][0]["lines"] == 3
    assert saved["queue"][0]["signals"] == {
        "recent_fix_commits": 0.0,
        "thin_test": 0.0,
        "wiring_hop": 0.0,
        "dead_setting": 0.0,
        "reverted": 0.0,
        "split_stores": 0.0,
    }


def test_fallback_signals_uses_the_same_file_list_as_scoring(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import _fallback_signals

    src = tmp_path / "src" / "util.py"
    test = tmp_path / "tests" / "test_util.py"
    src.parent.mkdir(parents=True)
    test.parent.mkdir(parents=True)
    src.write_text("value = 1\n", encoding="utf-8")
    test.write_text("def test_add():\n    assert True\n", encoding="utf-8")
    history: tuple[dict[str, int], set[str]] = ({}, set())
    only_src = _fallback_signals(tmp_path, "src/util.py", history, files=[src])
    with_test = _fallback_signals(tmp_path, "src/util.py", history, files=[src, test])
    assert only_src["thin_test"] == 1.0
    assert with_test["thin_test"] == 0.0


def test_rel_for_path_falls_back_when_resolve_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner.bug_hunt import _rel_for_path

    target = tmp_path / "src" / "broken.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n", encoding="utf-8")
    original = Path.resolve

    def resolve(self):
        if Path(self).name == "broken.py":
            raise OSError("unreadable")
        return original(self)

    monkeypatch.setattr(Path, "resolve", resolve)
    rel = _rel_for_path(tmp_path, target)
    assert rel
    assert "broken.py" in rel.replace("\\", "/")


def test_persist_opened_rewrites_nan_signal_slots(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt import RANK_PASS_REL, SIGNAL_KEYS, _persist_opened

    path = tmp_path / RANK_PASS_REL
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "opened": [],
                "queue": [
                    {
                        "file": "src/keep.py",
                        "score": 1.0,
                        "findings": 2,
                        "lines": float("nan"),
                        "signals": {key: float("nan") for key in SIGNAL_KEYS},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _persist_opened(tmp_path, [])
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["queue"][0]["lines"] == 0
    assert saved["queue"][0]["signals"] == {key: 0.0 for key in SIGNAL_KEYS}


def test_save_stopped_appends_when_rank_pass_is_corrupt(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt import RANK_ROWS_REL, save_stopped_outcome

    rank_pass = tmp_path / ".hive" / "bug-hunt" / "rank-pass.json"
    rank_pass.parent.mkdir(parents=True)
    rank_pass.write_text("{not-json", encoding="utf-8")
    target = tmp_path / "src" / "a.py"
    target.parent.mkdir(parents=True)
    target.write_text("x = 1\n", encoding="utf-8")
    result = save_stopped_outcome(
        tmp_path,
        {"file": "src/a.py", "scenario": "empty", "outcome": "empty"},
        history=({}, set()),
    )
    assert result["appended"] is True
    rows = (tmp_path / RANK_ROWS_REL).read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    saved = json.loads(rank_pass.read_text(encoding="utf-8"))
    assert saved["opened"] == ["src/a.py"]


def test_continue_hook_surfaces_rank_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    from hive_planner.bug_hunt_continue import apply_continue

    def boom(*_args, **_kwargs):
        raise RuntimeError("scan failed")

    monkeypatch.setattr("hive_planner.bug_hunt.advance_rank_pass", boom)
    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"active": True, "pause_seconds": 0}), encoding="utf-8")
    payload = apply_continue(tmp_path, sleep=lambda _seconds: None)
    assert "Rank rebuild failed" in payload["followup_message"]


def test_window_closes_at_200_archives_and_commits(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt import (
        INITIAL_SLOPES,
        PLACE_LOCAL_REL,
        SLOPE_WINDOWS_REL,
        _append_rank_row,
        load_rank_rows,
        rebuild_mean,
    )

    repo = _git_repo(tmp_path)
    (repo / "notes.txt").write_text("leave me\n", encoding="utf-8")
    signals = {
        "recent_fix_commits": 0,
        "thin_test": 1,
        "wiring_hop": 0,
        "dead_setting": 0,
        "reverted": 0,
        "split_stores": 0,
    }
    for index in range(5):
        _append_rank_row(repo, f"src/skip{index}.py", signals, "skip", "skipped")
    for index in range(200):
        _append_rank_row(repo, f"src/vote{index}.py", signals, "thin", "committed", findings=1)
    rows = load_rank_rows(repo / ".hive" / "bug-hunt" / "rank-rows.jsonl")
    voted = [row for row in rows if row["outcome"] == "committed"]
    skipped = [row for row in rows if row["outcome"] == "skipped"]
    assert len(voted) == 200
    assert skipped and "window" not in skipped[0]
    window_id = voted[0]["window"]
    assert all(row["window"] == window_id for row in voted)
    saved = json.loads((repo / SLOPE_WINDOWS_REL).read_text(encoding="utf-8"))
    assert saved["closed"][0]["id"] == window_id
    assert saved["closed"][0]["cycles"] == 200
    assert "place" not in saved["closed"][0]
    assert saved["open"]["id"] != window_id
    assert saved["open"]["count"] == 0
    place = json.loads((repo / PLACE_LOCAL_REL).read_text(encoding="utf-8"))
    assert place["src"] > 0
    learned = saved["closed"][0]["slopes"]
    offset = tuple(learned)
    mean, _evidence = rebuild_mean(rows, seed=offset, closed_ids={window_id})
    assert mean == pytest.approx(offset)
    assert learned[1] > INITIAL_SLOPES[1]
    names = _git(repo, "show", "--name-only", "--format=", "HEAD")
    assert "slope-windows.json" in names
    assert "place-local.json" not in names
    assert "notes.txt" not in names
    assert (repo / "notes.txt").read_text(encoding="utf-8") == "leave me\n"


def test_donor_uses_first_committed_archive_and_fix_skips_it(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt import (
        DONORS_REL,
        INITIAL_SLOPES,
        SLOPE_WINDOWS_REL,
        TRUST_SEED,
        _learning_offsets,
        commit_isolated_fix,
    )

    def archive(slopes: list[float], trust: float, cycles: int = 200) -> dict:
        return {
            "open": {"id": "w-open", "count": 0},
            "closed": [
                {"id": "w-closed", "cycles": cycles, "slopes": slopes, "trust": trust}
            ],
        }

    def commit_archive(repo: Path, payload: dict) -> None:
        path = repo / SLOPE_WINDOWS_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        _git(repo, "add", SLOPE_WINDOWS_REL.as_posix())
        _git(repo, "commit", "-m", "archive")

    donor_root = tmp_path / "donor"
    weak_root = tmp_path / "weak"
    borrower_root = tmp_path / "borrower"
    donor_root.mkdir()
    weak_root.mkdir()
    borrower_root.mkdir()
    donor = _git_repo(donor_root)
    weak = _git_repo(weak_root)
    borrower = _git_repo(borrower_root)
    good = archive([1, 4, 1, -0.1, 0, 0], 2.0)
    commit_archive(donor, good)
    (donor / SLOPE_WINDOWS_REL).write_text(
        json.dumps(archive([9, 9, 9, -0.1, 9, 9], 9.0)),
        encoding="utf-8",
    )
    commit_archive(weak, archive([-1, 4, 1, -0.1, 0, 0], 1.0))
    empty = {"open": {"id": "", "count": 0}, "closed": []}
    assert _learning_offsets(borrower, empty)[0] == pytest.approx(INITIAL_SLOPES)
    (borrower / DONORS_REL).parent.mkdir(parents=True, exist_ok=True)
    (borrower / DONORS_REL).write_text(
        json.dumps(
            {
                "donors": [
                    str(borrower),
                    str(weak),
                    str(donor / SLOPE_WINDOWS_REL),
                ]
            }
        ),
        encoding="utf-8",
    )
    slopes, trust = _learning_offsets(borrower, empty)
    assert slopes[1] == pytest.approx(4.0)
    assert trust == pytest.approx(2.0)
    own = archive([1, 2, 1, -0.1, 0, 0], 1.0)
    held, _held_trust = _learning_offsets(borrower, own)
    assert held[1] == pytest.approx(2.0)
    app = borrower / "src" / "app.py"
    app.parent.mkdir(parents=True)
    app.write_text("before\n", encoding="utf-8")
    archive_path = borrower / SLOPE_WINDOWS_REL
    archive_path.write_text("{}\n", encoding="utf-8")
    _git(borrower, "add", "src/app.py")
    _git(borrower, "commit", "-m", "base")
    before_app = borrower / "app-before.txt"
    before_archive = borrower / "archive-before.txt"
    before_app.write_text("before\n", encoding="utf-8")
    before_archive.write_text("{}\n", encoding="utf-8")
    app.write_text("after\n", encoding="utf-8")
    archive_path.write_text('{"closed": []}\n', encoding="utf-8")
    result = commit_isolated_fix(
        borrower,
        message="Fix app",
        snapshots={"src/app.py": before_app, SLOPE_WINDOWS_REL.as_posix(): before_archive},
    )
    assert result["ok"] is True
    names = _git(borrower, "show", "--name-only", "--format=", "HEAD")
    assert "src/app.py" in names
    assert "slope-windows.json" not in names


def test_stored_draw_does_not_move_a_zero_file_signal() -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, rebuild_mean

    row = {
        "signals": [0, 0, 0, 0, 0, 0],
        "outcome": "committed",
        "draw": [0.0, 0.0, 0.0, 0.0, 0.4, 0.2],
    }
    mean, _evidence = rebuild_mean([row])
    assert mean[4] == pytest.approx(INITIAL_SLOPES[4])
    assert mean[5] == pytest.approx(INITIAL_SLOPES[5])
    bare = rebuild_mean([{**row, "draw": None}])[0]
    assert bare == mean


def test_corrupt_archive_is_not_replaced(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import SLOPE_WINDOWS_REL, _append_rank_row

    repo = tmp_path
    archive = repo / SLOPE_WINDOWS_REL
    archive.parent.mkdir(parents=True)
    archive.write_text("{", encoding="utf-8")
    _append_rank_row(
        repo,
        "src/a.py",
        {
            "recent_fix_commits": 0,
            "thin_test": 1,
            "wiring_hop": 0,
            "dead_setting": 0,
            "reverted": 0,
            "split_stores": 0,
        },
        "thin",
        "committed",
        findings=1,
    )
    assert archive.read_text(encoding="utf-8") == "{"


def test_corrupt_archive_keeps_closed_rows_from_voting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner import bug_hunt
    from hive_planner.bug_hunt import (
        INITIAL_SLOPES,
        SLOPE_WINDOWS_REL,
        _append_rank_row,
        _learning_context,
        load_rank_rows,
        rebuild_mean,
    )

    monkeypatch.setattr(bug_hunt, "WINDOW_VOTE_LIMIT", 1)
    repo = tmp_path
    (repo / ".git").mkdir()
    signals = {
        "recent_fix_commits": 0,
        "thin_test": 1,
        "wiring_hop": 0,
        "dead_setting": 0,
        "reverted": 0,
        "split_stores": 0,
    }
    _append_rank_row(repo, "src/a.py", signals, "thin", "committed", findings=1)
    rows = load_rank_rows(repo / ".hive" / "bug-hunt" / "rank-rows.jsonl")
    window = rows[0]["window"]
    (repo / SLOPE_WINDOWS_REL).write_text("{", encoding="utf-8")
    closed, seed, _trust, _place = _learning_context(repo)
    assert window in closed
    assert seed == INITIAL_SLOPES
    mean, _evidence = rebuild_mean(rows, seed=seed, closed_ids=closed)
    assert mean == pytest.approx(INITIAL_SLOPES)


def test_non_list_closed_archive_is_not_rewritten(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import SLOPE_WINDOWS_REL, _append_rank_row

    repo = tmp_path
    archive = repo / SLOPE_WINDOWS_REL
    archive.parent.mkdir(parents=True)
    payload = '{"open": {"id": "w-open", "count": 0}, "closed": "wipe-me"}'
    archive.write_text(payload, encoding="utf-8")
    _append_rank_row(
        repo,
        "src/a.py",
        {
            "recent_fix_commits": 0,
            "thin_test": 1,
            "wiring_hop": 0,
            "dead_setting": 0,
            "reverted": 0,
            "split_stores": 0,
        },
        "thin",
        "committed",
        findings=1,
    )
    assert archive.read_text(encoding="utf-8") == payload


def test_corrupt_archive_keeps_an_open_window_voting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hive_planner import bug_hunt
    from hive_planner.bug_hunt import (
        INITIAL_SLOPES,
        PLACE_PENDING_REL,
        SLOPE_WINDOWS_REL,
        _append_rank_row,
        _learning_context,
        load_rank_rows,
        rebuild_mean,
    )

    monkeypatch.setattr(bug_hunt, "WINDOW_VOTE_LIMIT", 3)
    repo = tmp_path
    (repo / ".git").mkdir()
    signals = {
        "recent_fix_commits": 0,
        "thin_test": 1,
        "wiring_hop": 0,
        "dead_setting": 0,
        "reverted": 0,
        "split_stores": 0,
    }
    _append_rank_row(repo, "src/a.py", signals, "thin", "committed", findings=1)
    rows = load_rank_rows(repo / ".hive" / "bug-hunt" / "rank-rows.jsonl")
    open_id = rows[0]["window"]
    (repo / PLACE_PENDING_REL).write_text('{"window": "w-x", "src": 0.3}', encoding="utf-8")
    (repo / SLOPE_WINDOWS_REL).write_text("{", encoding="utf-8")
    closed, seed, _trust, _place = _learning_context(repo)
    assert open_id not in closed
    mean, _evidence = rebuild_mean(rows, seed=seed, closed_ids=closed)
    assert mean[1] > INITIAL_SLOPES[1]
    _append_rank_row(repo, "src/b.py", signals, "thin", "committed", findings=1)
    later = load_rank_rows(repo / ".hive" / "bug-hunt" / "rank-rows.jsonl")
    assert "window" not in later[-1]
    closed_after, seed_after, _t, _p = _learning_context(repo)
    unstamped_mean, _ev = rebuild_mean(later, seed=seed_after, closed_ids=closed_after)
    assert unstamped_mean[1] == pytest.approx(mean[1])
    assert (repo / PLACE_PENDING_REL).is_file()


def test_unusable_own_closed_still_takes_a_donor(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt import (
        DONORS_REL,
        INITIAL_SLOPES,
        SLOPE_WINDOWS_REL,
        TRUST_SEED,
        _learning_offsets,
    )

    donor_root = tmp_path / "donor"
    borrower_root = tmp_path / "borrower"
    donor_root.mkdir()
    borrower_root.mkdir()
    donor = _git_repo(donor_root)
    borrower = _git_repo(borrower_root)
    path = donor / SLOPE_WINDOWS_REL
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "open": {"id": "w-open", "count": 0},
                "closed": [
                    {
                        "id": "w-closed",
                        "cycles": 200,
                        "slopes": [1, 4, 1, -0.1, 0, 0],
                        "trust": 2.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _git(donor, "add", SLOPE_WINDOWS_REL.as_posix())
    _git(donor, "commit", "-m", "archive")
    (borrower / DONORS_REL).parent.mkdir(parents=True)
    (borrower / DONORS_REL).write_text(
        json.dumps({"donors": [str(donor)]}),
        encoding="utf-8",
    )
    junk = {
        "open": {"id": "w-open", "count": 0},
        "closed": [
            {
                "id": "w-bad",
                "cycles": 1,
                "slopes": [1, 9, 1, -0.1, 0, 0],
                "trust": 9.0,
            }
        ],
    }
    slopes, trust = _learning_offsets(borrower, junk)
    assert slopes[1] == pytest.approx(4.0)
    assert trust == pytest.approx(2.0)


def test_late_row_opens_a_new_window(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    from hive_planner import bug_hunt
    from hive_planner.bug_hunt import SLOPE_WINDOWS_REL, _append_rank_row, load_rank_rows

    monkeypatch.setattr(bug_hunt, "WINDOW_VOTE_LIMIT", 2)
    repo = tmp_path
    (repo / ".git").mkdir()
    signals = {
        "recent_fix_commits": 0,
        "thin_test": 1,
        "wiring_hop": 0,
        "dead_setting": 0,
        "reverted": 0,
        "split_stores": 0,
    }
    for index in range(3):
        _append_rank_row(repo, f"src/v{index}.py", signals, "thin", "committed", findings=1)
    rows = load_rank_rows(repo / ".hive" / "bug-hunt" / "rank-rows.jsonl")
    saved = json.loads((repo / SLOPE_WINDOWS_REL).read_text(encoding="utf-8"))
    assert rows[0]["window"] == rows[1]["window"]
    assert rows[2]["window"] != rows[0]["window"]
    assert rows[2]["window"] == saved["open"]["id"]
    assert saved["closed"][0]["id"] == rows[0]["window"]
    assert saved["closed"][0]["cycles"] == 2


def test_place_is_not_added_twice_when_the_archive_write_is_late(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from hive_planner import bug_hunt
    from hive_planner.bug_hunt import PLACE_LOCAL_REL, SLOPE_WINDOWS_REL, _sync_window

    monkeypatch.setattr(bug_hunt, "WINDOW_VOTE_LIMIT", 1)
    repo = tmp_path
    (repo / ".git").mkdir()
    _append = bug_hunt._append_rank_row
    _append(
        repo,
        "src/a.py",
        {
            "recent_fix_commits": 0,
            "thin_test": 0,
            "wiring_hop": 0,
            "dead_setting": 0,
            "reverted": 0,
            "split_stores": 0,
        },
        "thin",
        "committed",
        findings=1,
    )
    place = json.loads((repo / PLACE_LOCAL_REL).read_text(encoding="utf-8"))
    archive = json.loads((repo / SLOPE_WINDOWS_REL).read_text(encoding="utf-8"))
    closed_id = archive["closed"][0]["id"]
    first = place["src"]
    archive["open"] = {"id": closed_id, "count": 1}
    archive["closed"] = []
    (repo / SLOPE_WINDOWS_REL).write_text(json.dumps(archive), encoding="utf-8")
    place["archive_commit_pending"] = True
    place["window"] = closed_id
    (repo / PLACE_LOCAL_REL).write_text(json.dumps(place), encoding="utf-8")
    _sync_window(repo)
    again = json.loads((repo / PLACE_LOCAL_REL).read_text(encoding="utf-8"))
    assert again["src"] == pytest.approx(first)
    saved = json.loads((repo / SLOPE_WINDOWS_REL).read_text(encoding="utf-8"))
    assert saved["closed"][0]["id"] == closed_id


def test_place_advances_on_the_next_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from hive_planner import bug_hunt
    from hive_planner.bug_hunt import PLACE_LOCAL_REL, _append_rank_row

    monkeypatch.setattr(bug_hunt, "WINDOW_VOTE_LIMIT", 1)
    repo = tmp_path
    (repo / ".git").mkdir()
    empty = {
        "recent_fix_commits": 0,
        "thin_test": 1,
        "wiring_hop": 0,
        "dead_setting": 0,
        "reverted": 0,
        "split_stores": 0,
    }
    wire = {
        "recent_fix_commits": 0,
        "thin_test": 0,
        "wiring_hop": 1,
        "dead_setting": 0,
        "reverted": 0,
        "split_stores": 0,
    }
    _append_rank_row(repo, "alpha/a.py", empty, "empty", "empty", findings=1)
    first = json.loads((repo / PLACE_LOCAL_REL).read_text(encoding="utf-8"))
    assert first.get("alpha", 0.0) == 0.0
    _append_rank_row(repo, "beta/b.py", wire, "thin", "committed", findings=1)
    second = json.loads((repo / PLACE_LOCAL_REL).read_text(encoding="utf-8"))
    assert second.get("beta", 0.0) > 0.0


def test_queue_skips_tests_and_still_ranks_wiring(tmp_path: Path) -> None:
    import json

    thin = tmp_path / "alpha" / "thin_00.py"
    wire = tmp_path / "beta" / "wire_00.py"
    test = tmp_path / "tests" / "test_wire_00.py"
    thin.parent.mkdir(parents=True)
    wire.parent.mkdir(parents=True)
    test.parent.mkdir(parents=True)
    thin.write_text("value = 1\n", encoding="utf-8")
    wire.write_text("def unused_handler():\n    return 1\n", encoding="utf-8")
    test.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    files = [thin, wire, test]
    history: tuple[dict[str, int], set[str]] = ({}, set())
    first = advance_rank_pass(
        tmp_path, None, fresh=True, rng=random.Random(0), files=files, history=history
    )
    saved = json.loads((tmp_path / ".hive" / "bug-hunt" / "rank-pass.json").read_text(encoding="utf-8"))
    names = [item["file"] for item in saved["queue"]]
    assert first["top"] == "alpha/thin_00.py"
    assert "tests/test_wire_00.py" not in names
    assert "beta/wire_00.py" in names
    later = advance_rank_pass(
        tmp_path,
        {"file": "alpha/thin_00.py", "scenario": "thin", "outcome": "committed"},
        rng=random.Random(0),
        files=files,
        history=history,
    )
    assert later["top"] == "beta/wire_00.py"


def test_untested_flag_does_not_outrank_tested_wiring(tmp_path: Path) -> None:
    import json

    thin = tmp_path / "alpha" / "thin_00.py"
    wire = tmp_path / "beta" / "wire_00.py"
    flag = tmp_path / "gamma" / "flag_00.py"
    test = tmp_path / "tests" / "test_wire_00.py"
    thin.parent.mkdir(parents=True)
    wire.parent.mkdir(parents=True)
    flag.parent.mkdir(parents=True)
    test.parent.mkdir(parents=True)
    thin.write_text("value = 1\n", encoding="utf-8")
    wire.write_text("def unused_handler():\n    return 1\n", encoding="utf-8")
    flag.write_text("UNUSED_FLAG = True\n", encoding="utf-8")
    test.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    files = [thin, wire, flag, test]
    history: tuple[dict[str, int], set[str]] = ({}, set())
    first = advance_rank_pass(
        tmp_path, None, fresh=True, rng=random.Random(0), files=files, history=history
    )
    saved = json.loads((tmp_path / ".hive" / "bug-hunt" / "rank-pass.json").read_text(encoding="utf-8"))
    by_file = {item["file"]: item["signals"] for item in saved["queue"]}
    assert first["top"] == "alpha/thin_00.py"
    assert by_file["gamma/flag_00.py"]["thin_test"] == 0.0
    assert by_file["gamma/flag_00.py"]["dead_setting"] == 1.0
    assert by_file["alpha/thin_00.py"]["thin_test"] == 1.0
    later = advance_rank_pass(
        tmp_path,
        {"file": "alpha/thin_00.py", "scenario": "thin", "outcome": "committed"},
        rng=random.Random(0),
        files=files,
        history=history,
    )
    assert later["top"] == "beta/wire_00.py"


def test_thin_counted_once_clears_thin_when_another_defect_is_on() -> None:
    from hive_planner.bug_hunt import SIGNAL_KEYS, _thin_counted_once

    base = {key: 0.0 for key in SIGNAL_KEYS}
    only_thin = dict(base, thin_test=1.0)
    assert _thin_counted_once(only_thin)["thin_test"] == 1.0
    for key in ("wiring_hop", "dead_setting", "reverted", "split_stores"):
        stacked = dict(base, thin_test=1.0)
        stacked[key] = 1.0
        out = _thin_counted_once(stacked)
        assert out["thin_test"] == 0.0
        assert out[key] == 1.0


def test_untested_wiring_file_does_not_keep_the_thin_bit(tmp_path: Path) -> None:
    from hive_planner.bug_hunt import INITIAL_SLOPES, score_unopened

    thin = tmp_path / "alpha" / "thin_00.py"
    wire = tmp_path / "beta" / "wire_00.py"
    thin.parent.mkdir(parents=True)
    wire.parent.mkdir(parents=True)
    thin.write_text("value = 1\n", encoding="utf-8")
    wire.write_text("def unused_handler():\n    return 1\n", encoding="utf-8")
    ranked = score_unopened(
        tmp_path,
        [],
        INITIAL_SLOPES,
        files=[thin, wire],
        history=({}, set()),
    )
    by_file = {item["file"]: item["signals"] for item in ranked}
    assert by_file["alpha/thin_00.py"]["thin_test"] == 1.0
    assert by_file["beta/wire_00.py"]["wiring_hop"] == 1.0
    assert by_file["beta/wire_00.py"]["thin_test"] == 0.0
    assert ranked[0]["file"] == "alpha/thin_00.py"


def test_csharp_wiring_signals_are_extracted() -> None:
    from hive_planner.sandbox_rank_detect import csharp_signals

    signals = csharp_signals(
        "// public void Fake() { }\n"
        'class Handler { public void Unused() { } public static bool UNUSED_FLAG = true; }\n'
        'string note = "public void StringFake() { }";\n',
        thin=0,
    )
    assert signals.thin_test == 0
    assert signals.wiring_hop == 1
    assert signals.dead_setting == 1


def test_index_update_failure_does_not_stick_the_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json
    import subprocess

    from hive_planner import bug_hunt
    from hive_planner.bug_hunt import PLACE_LOCAL_REL, _append_rank_row

    monkeypatch.setattr(bug_hunt, "WINDOW_VOTE_LIMIT", 1)
    real_run = subprocess.run

    def wrapped(args, *pos, **kwargs):
        cmd = args if isinstance(args, list) else []
        if "update-index" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "index failed")
        return real_run(args, *pos, **kwargs)

    monkeypatch.setattr(bug_hunt.subprocess, "run", wrapped)
    repo = tmp_path
    repo.mkdir(exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "hunt@example.com")
    _git(repo, "config", "user.name", "Hunt")
    _append_rank_row(
        repo,
        "src/a.py",
        {
            "recent_fix_commits": 0,
            "thin_test": 1,
            "wiring_hop": 0,
            "dead_setting": 0,
            "reverted": 0,
            "split_stores": 0,
        },
        "thin",
        "committed",
        findings=1,
    )
    place = json.loads((repo / PLACE_LOCAL_REL).read_text(encoding="utf-8"))
    assert place.get("archive_commit_pending") is not True
    names = _git(repo, "show", "--name-only", "--format=", "HEAD")
    assert "slope-windows.json" in names


def test_zero_signal_commit_does_not_dilute_other_slopes() -> None:
    thin = {"signals": [0, 1, 0, 0, 0, 0], "outcome": "committed"}
    zero = {"signals": [0, 0, 0, 0, 0, 0], "outcome": "committed"}
    first, evidence = rebuild_mean([thin])
    second, again = rebuild_mean([thin, zero])
    assert second == pytest.approx(first)
    assert again == pytest.approx(evidence)


def test_thompson_draw_is_not_stored_in_the_next_mean() -> None:
    row = {"signals": [0, 1, 0, 0, 0, 0], "outcome": "committed"}
    mean, evidence = rebuild_mean([row])
    draw = thompson_draw(mean, evidence, random.Random(1))
    assert draw != mean
    again, _evidence = rebuild_mean([row])
    assert again == mean
    wide = rebuild_mean([row] * 400)[0]
    moved = rebuild_mean([row] * 400 + [{"signals": [0, 0, 1, 0, 0, 0], "outcome": "committed"}])[0]
    assert moved != wide


def test_score_signals_uses_fitted_slopes_and_log1p() -> None:
    assert INITIAL_SLOPES == (0.7118, 3.3024, 1.0245, -0.1424, 0.0, 0.0)
    assert fix_commit_feature(0) == 0.0
    assert math.isfinite(fix_commit_feature(1e308))
    assert score_signals([0, float("inf"), 0, 0, 0, 0]) == 0.0
    assert score_signals([0, 0, 0, 0, 0, 0]) == 0.0
    assert score_signals([0, 1, 0, 0, 0, 0]) == pytest.approx(3.3024)
    assert score_signals([0, 0, 1, 0, 0, 0]) == pytest.approx(1.0245)
    assert score_signals([0, 0, 0, 1, 0, 0]) == pytest.approx(-0.1424)
    assert score_signals([1, 0, 0, 0, 0, 0]) == pytest.approx(0.7118 * math.log1p(1))
    with pytest.raises(ValueError, match="fix-commit count must be >= 0"):
        score_signals([-1, 0, 0, 0, 0, 0])


def test_prompt_keeps_the_loop_moving() -> None:
    text = render_agent_prompt(50)
    assert "50 committed fixes is the ceiling" in text
    assert "Do not ask the user whether to continue" in text
    assert "not skippable" in text
    assert "10 seconds" in text
    assert "continue.json" in text
    assert "not a wait between passes" in text
    assert "Pause on this step" not in text
    assert "Do not end the hunt here" not in text
    assert "repeat across separate inference passes" in text
    assert "Do not ask the user whether to continue" in text
    assert "Do not push" in text
    assert "Wiring audit" in text
    assert "Rows in the open window are votes" in text
    assert "A zero file signal adds no credit" in text
    assert "does not change vote weights" in text
    assert "A test file is not a hunt location" in text
    assert "not stacked on a wiring hop" in text
    assert "Potential:" in text
    assert "two readers of the same fact" in text
    assert "neither a confirmed bug nor a potential bug" in text
    assert "I did not reproduce it this session" in text
    assert "Where to look" in text
    assert "0.35" in text
    assert "Do not fit a logistic regression" in text
    assert "detector trust" in text
    assert "The queue keeps the top 50 scored files" in text
    assert "Finding count then line count break remaining ties" in text
    assert "Qualifying means any of the six signals or a detector finding" in text
    assert "Fit a logistic regression only after" not in text
    assert "recorded and skipped" in text
    assert "not a quota" in text
    assert "reverted commit" in text
    assert "record-and-skip" in text
    assert "Fit a classifier only after at least 30 completed rows" in text
    assert "do not invent a probability" in text
    assert "bell curve" in text
    assert "decay by 0.9 in row order" in text
    assert "review-failed row pulls" in text
    assert "does not freeze" in text
    assert "rank-pass.json" in text
    assert "print_rank_pass" not in text
    assert "Do not append the row yourself" in text
    assert "file`, `scenario`, `outcome`" in text
    assert "when the regression is fit" not in text
    assert "per-folder place attention" in text
    assert "once the location model exists" not in text
    assert "Rank which tests to run" in text
    assert "The ranker has no probability floor" in text
    assert "An unopened location is not an empty search" in text
    assert "do not run the self-review" in text
    assert "bug-hunt-commit" in text
    assert "do not stash the repository" in text
    assert "A confirmed bug that meets the step 1 bar is **fix**" in text
    assert "0.65" in text
    assert "at least 30 completed rows" in text
    assert "restore only this iteration's uncommitted edits" in text
    assert "A failed review is not an empty search" in text
    assert "If that commit fails, restore only this iteration's uncommitted edits and use `review-failed` instead." in text
    assert "review-failed" in text
    assert "written once, after the outcome is known" in text
    assert "Do not append a second row for the same location in this run" in text
    assert "Do not end the hunt here" not in text
    assert "The ranker has no probability floor" in text
    assert "log1p of recent bug-fix commits × 0.7118" in text
    assert "× 3.3024" in text
    assert "× 1.0245" in text
    assert "× -0.1424" in text
    assert "× 0.0, two stores for one fact" in text
    assert "which a later rebuild starts from" in text
    assert ".hive/bug-hunt/rank-rows.jsonl" in text
    assert "Do not fit a logistic regression" in text
    assert "Residual mismatch" in text
    assert "including when the harness is missing" in text
    assert "marks this run's opened set" in text
    assert "A hunt starts after `active` was written false for a stop condition" in text


def test_pause_zero_skips_the_wait() -> None:
    text = render_agent_prompt(50, pause_seconds=0)
    assert "pause is 0 seconds" in text
    assert "do not wait between passes" in text
    assert "The hook waits, then" not in text
    assert "The hook appends the rank row, then sets active to false, then starts the next inference pass." in text
    assert "The hook still appends that pass's rank row first" in text
    assert "not skippable" not in text
    assert "Do not ask the user whether to continue" in text
    assert "two consecutive empty searches" in text


def test_pause_blank_is_ten_and_a_positive_number_is_the_wait() -> None:
    from hive_planner.bug_hunt import parse_pause_seconds, validate_pause_seconds

    assert validate_pause_seconds(None) == 10
    assert parse_pause_seconds("") == 10
    assert parse_pause_seconds("  ") == 10
    assert parse_pause_seconds("0") == 0
    assert parse_pause_seconds("0.0") == 0
    assert parse_pause_seconds("15") == 15
    assert parse_pause_seconds("10.0") == 10
    with pytest.raises(BugHuntError):
        parse_pause_seconds("-1")
    with pytest.raises(BugHuntError):
        parse_pause_seconds("soon")
    with pytest.raises(BugHuntError):
        parse_pause_seconds("9223372037")
    text = render_agent_prompt(4, pause_seconds=15)
    assert "15 seconds" in text
    assert "not skippable" in text


def test_cli_pause_accepts_a_whole_decimal(tmp_path: Path) -> None:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = main(["--root", str(tmp_path), "bug-hunt", "--print", "--pause-seconds", "10.0"])
    assert code == 0
    assert "pause is 10 seconds" in stdout.getvalue()
    assert not (tmp_path / ".cursor" / "commands" / "bug-hunt.md").exists()


def test_cli_iterations_accepts_a_whole_decimal(tmp_path: Path) -> None:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = main(["--root", str(tmp_path), "bug-hunt", "--print", "--iterations", "50.0"])
    assert code == 0
    assert "50 committed fixes is the ceiling" in stdout.getvalue()


def test_install_ignores_the_pending_place_file(tmp_path: Path) -> None:
    install_bug_hunt(tmp_path, iterations=1)
    ignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".hive/bug-hunt/place-local.pending.json" in ignore.splitlines()


def test_install_writes_the_pause_into_the_script(tmp_path: Path) -> None:
    result = install_bug_hunt(tmp_path, iterations=4, pause_seconds=0)
    command = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert result.pause_seconds == 0
    assert "pause is 0 seconds" in command
    assert "do not wait between passes" in command
    assert result.to_dict()["pause_seconds"] == 0


def test_continue_hook_claims_the_token_before_the_pause(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt_continue import apply_continue

    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps({"active": True, "pause_seconds": 10, "committed": 1, "consecutive_empty": 0}),
        encoding="utf-8",
    )
    seen: list[dict] = []

    def pause(seconds: int) -> None:
        assert seconds == 10
        seen.append(apply_continue(tmp_path, sleep=lambda _seconds: None))
        state_path.write_text(
            json.dumps({"active": True, "pause_seconds": 0, "committed": 4, "consecutive_empty": 0}),
            encoding="utf-8",
        )

    payload = apply_continue(tmp_path, sleep=pause)
    assert payload == {}
    assert seen == [{}]
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["active"] is True
    assert saved["committed"] == 4
    assert not (state_path.with_name(state_path.name + ".lock")).exists()


def test_continue_hook_does_not_follow_up_after_a_stop_written_during_the_pause(
    tmp_path: Path,
) -> None:
    import json

    from hive_planner.bug_hunt_continue import apply_continue

    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps({"active": True, "pause_seconds": 10, "ceiling": 50, "committed": 1, "consecutive_empty": 0}),
        encoding="utf-8",
    )

    def pause(_seconds: int) -> None:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["consecutive_empty"] = 2
        state_path.write_text(json.dumps(state), encoding="utf-8")

    assert apply_continue(tmp_path, sleep=pause) == {}
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["active"] is False
    assert "resume_pid" not in saved


def test_continue_hook_resumes_when_the_waiter_died(tmp_path: Path) -> None:
    import json
    import time

    from hive_planner.bug_hunt_continue import apply_continue

    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "active": False,
                "pause_seconds": 10,
                "ceiling": 50,
                "committed": 1,
                "consecutive_empty": 0,
                "resume_pid": 999999,
                "resume_deadline": time.time() + 60,
            }
        ),
        encoding="utf-8",
    )
    payload = apply_continue(tmp_path, sleep=lambda _seconds: None)
    assert "followup_message" in payload
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["active"] is False
    assert "resume_pid" not in saved


def test_continue_hook_waits_then_starts_the_next_pass(tmp_path: Path) -> None:
    import json
    import time

    from hive_planner.bug_hunt_continue import apply_continue, plan_continue

    waited: list[int] = []
    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"active": True, "pause_seconds": 10}), encoding="utf-8")
    payload = apply_continue(tmp_path, sleep=lambda seconds: waited.append(seconds))
    assert waited == [10]
    assert "followup_message" in payload
    assert "next inference pass" in payload["followup_message"]
    assert "Open the first file in .hive/bug-hunt/rank-pass.json" in payload["followup_message"]
    assert "appends the rank row before it treats active false" in payload["followup_message"]
    assert "file, scenario, outcome" in payload["followup_message"]
    assert "consecutive-empty count named in that script" in payload["followup_message"]
    assert "pause_seconds\": 0" not in payload["followup_message"]
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False
    assert apply_continue(tmp_path, sleep=lambda seconds: waited.append(seconds)) == {}
    assert plan_continue({"active": 1, "pause_seconds": "10.0"})[0] == 10
    assert plan_continue({"active": "true", "pause_seconds": "0"})[1]["followup_message"]
    assert plan_continue({"active": True, "pause_seconds": 0})[0] == 0
    assert plan_continue({"active": True, "pause_seconds": "10"})[0] == 10
    assert plan_continue({"active": True, "pause_seconds": 10.0})[0] == 10
    assert plan_continue({"active": False, "pause_seconds": 10})[1] == {}
    state_path.write_text(
        json.dumps({"active": True, "pause_seconds": "soon"}),
        encoding="utf-8",
    )
    assert apply_continue(tmp_path, sleep=lambda seconds: waited.append(seconds)) == {}
    assert waited == [10]
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False
    assert not (state_path.with_name(state_path.name + ".tmp")).exists()


def test_continue_hook_reads_a_utf16_active_file(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt_continue import apply_continue

    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps({"active": True, "pause_seconds": 0, "ceiling": 50, "committed": 1}),
        encoding="utf-16",
    )
    slept: list[int] = []
    payload = apply_continue(tmp_path, sleep=lambda seconds: slept.append(seconds))
    assert slept == []
    assert "followup_message" in payload
    saved = json.loads(state_path.read_text(encoding="utf-8-sig"))
    assert saved["active"] is False
    assert saved["committed"] == 1


def test_continue_hook_zero_does_not_wait_and_abort_consumes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    from hive_planner.bug_hunt_continue import main

    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"active": True, "pause_seconds": 0}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin.read", lambda: '{"status":"completed"}')
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main() == 0
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False

    state_path.write_text(json.dumps({"active": True, "pause_seconds": 10}), encoding="utf-8")
    slept: list[int] = []
    monkeypatch.setattr("hive_planner.bug_hunt_continue.time.sleep", lambda seconds: slept.append(seconds))
    monkeypatch.setattr("sys.stdin.read", lambda: '{"status":"aborted"}')
    assert main() == 0
    assert slept == []
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False


def test_pause_beyond_the_sleep_limit_falls_back_to_the_script(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt_continue import apply_continue

    command = tmp_path / ".cursor" / "commands" / "bug-hunt.md"
    command.parent.mkdir(parents=True)
    command.write_text("This run's pause is 10 seconds.\n", encoding="utf-8")
    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text('{"active": true, "pause_seconds": 100000000000000000000}', encoding="utf-8")
    slept: list[int] = []
    payload = apply_continue(tmp_path, sleep=lambda seconds: slept.append(seconds))
    assert slept == [10]
    assert "followup_message" in payload
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False


def test_missing_pause_uses_the_script_not_the_ten_second_default(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt_continue import apply_continue

    command = tmp_path / ".cursor" / "commands" / "bug-hunt.md"
    command.parent.mkdir(parents=True)
    command.write_text("This run's pause is 0 seconds.\n", encoding="utf-8")
    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text('{"active": true}', encoding="utf-8")
    slept: list[int] = []
    payload = apply_continue(tmp_path, sleep=lambda seconds: slept.append(seconds))
    assert slept == []
    assert "followup_message" in payload
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False


def test_missing_pause_reads_a_utf16_script(tmp_path: Path) -> None:
    from hive_planner.bug_hunt_continue import apply_continue

    command = tmp_path / ".cursor" / "commands" / "bug-hunt.md"
    command.parent.mkdir(parents=True)
    command.write_text("This run's pause is 0 seconds.\n", encoding="utf-16")
    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text('{"active": true}', encoding="utf-8")
    slept: list[int] = []
    payload = apply_continue(tmp_path, sleep=lambda seconds: slept.append(seconds))
    assert slept == []
    assert "followup_message" in payload


def test_continue_hook_finds_the_file_above_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from hive_planner.bug_hunt_continue import main

    repo = tmp_path / "repo"
    sub = repo / "src"
    sub.mkdir(parents=True)
    state_path = repo / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"active": True, "pause_seconds": 0}), encoding="utf-8")
    monkeypatch.chdir(sub)
    monkeypatch.setattr("sys.stdin.read", lambda: '{"status":"completed"}')
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main() == 0
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False


def test_continue_hook_honors_state_counters_when_active_was_left_true(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt_continue import apply_continue

    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        '{"active": true, "pause_seconds": 0, "ceiling": 50, "committed": 50, "consecutive_empty": 0}',
        encoding="utf-8",
    )
    slept: list[int] = []
    payload = apply_continue(tmp_path, sleep=lambda seconds: slept.append(seconds))
    assert payload == {}
    assert slept == []
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False

    state_path.write_text(
        '{"active": true, "pause_seconds": 0, "ceiling": 50, "committed": 3, "consecutive_empty": 2}',
        encoding="utf-8",
    )
    payload = apply_continue(tmp_path, sleep=lambda seconds: slept.append(seconds))
    assert payload == {}
    assert slept == []
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False

    state_path.write_text(
        '{"active": true, "pause_seconds": 0, "stop": 1}',
        encoding="utf-8",
    )
    payload = apply_continue(tmp_path, sleep=lambda seconds: slept.append(seconds))
    assert payload == {}
    assert slept == []
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False


def test_continue_hook_ignores_boolean_and_fractional_counters(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt_continue import apply_continue

    state_path = tmp_path / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        '{"active": true, "pause_seconds": 0, "ceiling": 1, "committed": true}',
        encoding="utf-8",
    )
    slept: list[int] = []
    payload = apply_continue(tmp_path, sleep=lambda seconds: slept.append(seconds))
    assert slept == []
    assert "followup_message" in payload

    state_path.write_text(
        '{"active": true, "pause_seconds": 0, "ceiling": 1.5, "committed": 1}',
        encoding="utf-8",
    )
    payload = apply_continue(tmp_path, sleep=lambda seconds: slept.append(seconds))
    assert "followup_message" in payload

    state_path.write_text(
        '{"active": true, "pause_seconds": 0, "ceiling": "1", "committed": "1"}',
        encoding="utf-8",
    )
    payload = apply_continue(tmp_path, sleep=lambda seconds: slept.append(seconds))
    assert payload == {}
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is False


def test_continue_hook_does_not_use_a_parent_projects_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from hive_planner.bug_hunt_continue import main

    outer = tmp_path / "outer"
    child = outer / "child"
    (child / "src").mkdir(parents=True)
    (child / ".git").mkdir()
    state_path = outer / ".hive" / "bug-hunt" / "continue.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"active": True, "pause_seconds": 0}), encoding="utf-8")
    monkeypatch.chdir(child / "src")
    monkeypatch.setattr("sys.stdin.read", lambda: '{"status":"completed"}')
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main() == 0
    assert json.loads(state_path.read_text(encoding="utf-8"))["active"] is True


def test_render_continue_hook_reads_packaged_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hive_planner.bug_hunt import render_continue_hook

    packaged = tmp_path / "hive_planner" / "bug_hunt_continue.py"
    packaged.parent.mkdir(parents=True)
    packaged.write_text("# packaged hook\n", encoding="utf-8")
    monkeypatch.setattr("hive_planner.bug_hunt.__file__", str(tmp_path / "missing" / "bug_hunt.py"))
    monkeypatch.setattr("hive_planner.bug_hunt.sys._MEIPASS", str(tmp_path), raising=False)
    assert render_continue_hook() == "# packaged hook\n"


def test_install_registers_continue_hook_and_keeps_other_events(tmp_path: Path) -> None:
    import json

    hooks = tmp_path / ".cursor" / "hooks.json"
    hooks.parent.mkdir(parents=True)
    hooks.write_text(
        json.dumps({"version": 1, "hooks": {"workspaceOpen": [{"command": "py -3.11 keep.py"}]}}),
        encoding="utf-8",
    )
    install_bug_hunt(tmp_path, iterations=50, pause_seconds=10)
    command = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert "50 committed fixes is the ceiling" in command
    assert "This ceiling counts committed fixes, not inference passes." in command
    data = json.loads(hooks.read_text(encoding="utf-8"))
    assert data["hooks"]["workspaceOpen"][0]["command"] == "py -3.11 keep.py"
    stop = data["hooks"]["stop"]
    assert any(item["command"] == "py -3.11 .cursor/hooks/bug_hunt_continue.py" for item in stop)
    assert stop[-1]["timeout"] == 86400
    assert (tmp_path / ".cursor" / "hooks" / "bug_hunt_continue.py").is_file()
    assert missing_bug_hunt_artifacts(tmp_path) == []
    install_bug_hunt(tmp_path, iterations=50, pause_seconds=100000)
    data = json.loads(hooks.read_text(encoding="utf-8"))
    assert data["hooks"]["workspaceOpen"][0]["command"] == "py -3.11 keep.py"
    assert data["hooks"]["stop"][-1]["timeout"] == 100030


def test_high_fix_ceiling_raises_the_continue_hook_loop_limit(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt import continue_hook_loop_limit

    assert continue_hook_loop_limit(50) == 210
    assert continue_hook_loop_limit(106) == 266
    install_bug_hunt(tmp_path, iterations=200, pause_seconds=10)
    data = json.loads((tmp_path / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
    assert data["hooks"]["stop"][-1]["loop_limit"] == 360
    install_bug_hunt(tmp_path, iterations=50, pause_seconds=10)
    data = json.loads((tmp_path / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
    assert data["hooks"]["stop"][-1]["loop_limit"] == 360


def test_install_does_not_replace_broken_hooks_json(tmp_path: Path) -> None:
    hooks = tmp_path / ".cursor" / "hooks.json"
    hooks.parent.mkdir(parents=True)
    original = '{"version": 1, "hooks": {"workspaceOpen": [}'
    hooks.write_text(original, encoding="utf-8")
    with pytest.raises(BugHuntError, match="not valid JSON"):
        install_bug_hunt(tmp_path, iterations=50)
    assert hooks.read_text(encoding="utf-8") == original
    assert not (tmp_path / ".cursor" / "commands" / "bug-hunt.md").exists()


def test_install_merges_a_hooks_file_with_a_bom_or_utf16(tmp_path: Path) -> None:
    import json

    original = {"version": 1, "hooks": {"workspaceOpen": [{"command": "py -3.11 keep.py"}]}}
    payload = json.dumps(original)
    for encoding, write in (
        ("utf-8-sig", lambda path: path.write_bytes(b"\xef\xbb\xbf" + payload.encode("utf-8"))),
        ("utf-16", lambda path: path.write_text(payload, encoding="utf-16")),
        ("utf-16-le", lambda path: path.write_bytes(payload.encode("utf-16-le"))),
    ):
        project = tmp_path / encoding
        hooks = project / ".cursor" / "hooks.json"
        hooks.parent.mkdir(parents=True)
        write(hooks)
        install_bug_hunt(project, iterations=50, pause_seconds=10)
        data = json.loads(hooks.read_text(encoding="utf-8"))
        assert data["hooks"]["workspaceOpen"][0]["command"] == "py -3.11 keep.py"
        assert any(
            item["command"] == "py -3.11 .cursor/hooks/bug_hunt_continue.py"
            for item in data["hooks"]["stop"]
        )
        assert missing_bug_hunt_artifacts(project) == []


def test_utf16_hooks_json_that_already_has_the_stop_hook_is_rewritten(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt import (
        CONTINUE_HOOK_COMMAND,
        CONTINUE_HOOK_LOOP_LIMIT,
        CONTINUE_HOOK_TIMEOUT,
        ensure_continue_hook,
    )

    hooks = tmp_path / ".cursor" / "hooks.json"
    hooks.parent.mkdir(parents=True)
    original = {
        "version": 1,
        "hooks": {
            "workspaceOpen": [{"command": "py -3.11 keep.py"}],
            "stop": [
                {
                    "command": CONTINUE_HOOK_COMMAND,
                    "timeout": CONTINUE_HOOK_TIMEOUT,
                    "loop_limit": CONTINUE_HOOK_LOOP_LIMIT,
                }
            ],
        },
    }
    hooks.write_text(json.dumps(original), encoding="utf-16")

    changed = ensure_continue_hook(tmp_path, pause_seconds=10)

    raw = hooks.read_bytes()
    assert changed is True
    assert not raw.startswith(b"\xff\xfe")
    data = json.loads(raw.decode("utf-8"))
    assert data["hooks"]["workspaceOpen"][0]["command"] == "py -3.11 keep.py"
    assert data["hooks"]["stop"][0]["command"] == CONTINUE_HOOK_COMMAND
    assert data["hooks"]["stop"][0]["timeout"] == CONTINUE_HOOK_TIMEOUT


def test_plain_hooks_json_with_the_stop_hook_is_left_alone(tmp_path: Path) -> None:
    import json

    from hive_planner.bug_hunt import (
        CONTINUE_HOOK_COMMAND,
        CONTINUE_HOOK_LOOP_LIMIT,
        CONTINUE_HOOK_TIMEOUT,
        ensure_continue_hook,
    )

    hooks = tmp_path / ".cursor" / "hooks.json"
    hooks.parent.mkdir(parents=True)
    original = {
        "version": 1,
        "hooks": {
            "stop": [
                {
                    "command": CONTINUE_HOOK_COMMAND,
                    "timeout": CONTINUE_HOOK_TIMEOUT,
                    "loop_limit": CONTINUE_HOOK_LOOP_LIMIT,
                }
            ]
        },
    }
    hooks.write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8", newline="\n")

    changed = ensure_continue_hook(tmp_path, pause_seconds=10)

    data = json.loads(hooks.read_text(encoding="utf-8"))
    assert changed is True
    assert data["hooks"]["stop"] == original["hooks"]["stop"]
    assert data["hooks"]["beforeSubmitPrompt"][0]["command"] == CONTINUE_HOOK_COMMAND
    assert data["hooks"]["beforeSubmitPrompt"][0]["timeout"] == 86400
    again = hooks.read_bytes()
    assert ensure_continue_hook(tmp_path, pause_seconds=10) is False
    assert hooks.read_bytes() == again


def test_install_leaves_no_tmp_bug_hunt_files(tmp_path: Path) -> None:
    install_bug_hunt(tmp_path, iterations=50)
    leftovers = [path for path in tmp_path.rglob("*.tmp") if path.is_file()]
    assert leftovers == []
    assert (tmp_path / ".cursor" / "commands" / "bug-hunt.md").is_file()


def test_install_writes_command_and_packet(tmp_path: Path) -> None:
    result = install_bug_hunt(tmp_path, iterations=50)
    command = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    packet = (tmp_path / ".hive" / "bug-hunt" / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    rule = (tmp_path / ".cursor" / "rules" / "bug-hunt.mdc").read_text(encoding="utf-8")
    scripts = (tmp_path / "scripts" / "bug-hunt.md").read_text(encoding="utf-8")
    assert command.startswith("---\n")
    assert "50 committed fixes is the ceiling" in command
    assert "50 committed fixes is the ceiling" in packet
    assert "50 committed fixes is the ceiling" in scripts
    assert "alwaysApply: true" in rule
    assert "bug hunt" in rule
    assert "bug hun" in rule
    assert "bung hunt" in rule
    assert "do a bug hunt" in rule
    assert "do a bung hunt" in rule
    assert "hunt for bugs" in rule
    assert "dual-lane" not in command
    assert result.command_path.is_file()
    assert result.rule_path.is_file()
    assert result.packet_path.is_file()
    assert ".cursor/commands/bug-hunt.md" in result.files_written
    assert "bung hunt" in command
    assert "do a bug hunt" in command
    assert "or a detector finding" in command
    assert "or a detector finding" in packet
    assert "still appends that pass's rank row first" in command
    hook = (tmp_path / ".cursor" / "hooks" / "bug_hunt_continue.py").read_text(encoding="utf-8")
    assert "Open the first file in .hive/bug-hunt/rank-pass.json" in hook
    assert "appends the rank row before it treats active false" in hook


def test_install_appends_repo_overlay(tmp_path: Path) -> None:
    overlay = tmp_path / ".hive" / "bug-hunt" / "repo-overlay.md"
    overlay.parent.mkdir(parents=True)
    overlay.write_text("## This repo\n\nRun coco_bug_hunt_audit.py after each fix.\n", encoding="utf-8")
    result = install_bug_hunt(tmp_path, iterations=8)
    command = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    scripts = (tmp_path / "scripts" / "bug-hunt.md").read_text(encoding="utf-8")
    assert "coco_bug_hunt_audit.py" in command
    assert "coco_bug_hunt_audit.py" in scripts
    assert command.count("coco_bug_hunt_audit.py") == 1
    assert ".cursor/commands/bug-hunt.md" in result.files_written
    install_bug_hunt(tmp_path, iterations=8)
    again = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert again.count("coco_bug_hunt_audit.py") == 1


def test_install_keeps_a_utf16_repo_overlay(tmp_path: Path) -> None:
    overlay = tmp_path / ".hive" / "bug-hunt" / "repo-overlay.md"
    overlay.parent.mkdir(parents=True)
    overlay.write_text(
        "## This repo\n\nRun coco_bug_hunt_audit.py after each fix.\n",
        encoding="utf-16",
    )
    install_bug_hunt(tmp_path, iterations=8)
    command = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert "coco_bug_hunt_audit.py" in command
    assert command.count("coco_bug_hunt_audit.py") == 1


def test_install_skips_unreadable_overlay(tmp_path: Path) -> None:
    overlay = tmp_path / ".hive" / "bug-hunt" / "repo-overlay.md"
    overlay.parent.mkdir(parents=True)
    overlay.write_bytes(b"\xff\xfe\x00\x00")
    result = install_bug_hunt(tmp_path, iterations=4)
    command = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert "4 committed fixes is the ceiling" in command
    assert result.command_path.is_file()
    assert preview_agent_prompt(tmp_path, 4).count("4 committed fixes is the ceiling") == 1


def test_install_skips_existing_when_not_forced(tmp_path: Path) -> None:
    first = install_bug_hunt(tmp_path, iterations=10)
    assert first.files_written
    command = tmp_path / ".cursor" / "commands" / "bug-hunt.md"
    command.write_text("custom\n", encoding="utf-8")
    second = install_bug_hunt(tmp_path, iterations=20, force=False)
    assert second.files_written == []
    assert command.read_text(encoding="utf-8") == "custom\n"


def test_install_force_does_not_report_unchanged_files(tmp_path: Path) -> None:
    first = install_bug_hunt(tmp_path, iterations=10, pause_seconds=10)
    assert ".cursor/commands/bug-hunt.md" in first.files_written
    second = install_bug_hunt(tmp_path, iterations=10, pause_seconds=10)
    assert second.files_written == []


def test_install_appends_dual_lane_when_rule_present(tmp_path: Path) -> None:
    dual = tmp_path / ".cursor" / "rules" / "bug-hunt-dual-lane.mdc"
    dual.parent.mkdir(parents=True)
    dual.write_text("---\nalwaysApply: true\n---\n# dual\n", encoding="utf-8")
    install_bug_hunt(tmp_path, iterations=10)
    command = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert "10 committed fixes is the ceiling" in command
    assert "dual-lane" in command
    assert "bug-hunt-dual-lane.mdc" not in command
    assert "One location per iteration still holds" in command
    assert "Batch related findings" not in command


def test_install_resolves_code_workspace_to_folder(tmp_path: Path) -> None:
    import json

    folder = tmp_path / "app"
    folder.mkdir()
    (folder / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    workspace = tmp_path / "hive.code-workspace"
    workspace.write_text(json.dumps({"folders": [{"path": "app"}]}), encoding="utf-8")
    result = install_bug_hunt(workspace, iterations=3)
    assert result.root == folder.resolve()
    assert (folder / ".cursor" / "commands" / "bug-hunt.md").is_file()
    assert missing_bug_hunt_artifacts(workspace) == []
    overlay = folder / ".hive" / "bug-hunt" / "repo-overlay.md"
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.write_text("workspace-overlay-token\n", encoding="utf-8")
    assert "workspace-overlay-token" in preview_agent_prompt(workspace, 3)


def test_iterations_out_of_range(tmp_path: Path) -> None:
    with pytest.raises(BugHuntError):
        install_bug_hunt(tmp_path, iterations=0)


def test_bug_hunt_cli_help_names_committed_fixes() -> None:
    stdout = io.StringIO()
    with redirect_stdout(stdout), pytest.raises(SystemExit) as caught:
        main(["bug-hunt", "--help"])
    assert caught.value.code in (0, None)
    text = stdout.getvalue()
    assert "Committed fixes" in text
    assert "1-200" in text
    assert "Default 10" in text


def test_cli_print_does_not_write(tmp_path: Path) -> None:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = main(["--root", str(tmp_path), "bug-hunt", "--print"])
    assert code == 0
    assert "50 committed fixes is the ceiling" in stdout.getvalue()
    assert not (tmp_path / ".cursor" / "commands" / "bug-hunt.md").exists()


def test_cli_print_includes_repo_overlay(tmp_path: Path) -> None:
    overlay = tmp_path / ".hive" / "bug-hunt" / "repo-overlay.md"
    overlay.parent.mkdir(parents=True)
    overlay.write_text("## This repo\n\nRun coco_bug_hunt_audit.py after each fix.\n", encoding="utf-8")
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = main(["--root", str(tmp_path), "bug-hunt", "--print", "--iterations", "8"])
    assert code == 0
    text = stdout.getvalue()
    assert "8 committed fixes is the ceiling" in text
    assert "coco_bug_hunt_audit.py" in text
    assert preview_agent_prompt(tmp_path, 8).count("coco_bug_hunt_audit.py") == 1
    assert not (tmp_path / ".cursor" / "commands" / "bug-hunt.md").exists()


def test_missing_bug_hunt_artifacts_lists_absent_files(tmp_path: Path) -> None:
    assert missing_bug_hunt_artifacts(tmp_path) == [
        ".cursor/commands/bug-hunt.md",
        ".cursor/rules/bug-hunt.mdc",
        ".hive/bug-hunt/AGENT_PROMPT.md",
        "scripts/bug-hunt.md",
        ".cursor/hooks/bug_hunt_continue.py",
        ".cursor/hooks.json#stop:py -3.11 .cursor/hooks/bug_hunt_continue.py",
        ".cursor/hooks.json#beforeSubmitPrompt:py -3.11 .cursor/hooks/bug_hunt_continue.py",
    ]
    install_bug_hunt(tmp_path, iterations=4)
    assert missing_bug_hunt_artifacts(tmp_path) == []
    (tmp_path / ".cursor" / "rules" / "bug-hunt.mdc").unlink()
    assert missing_bug_hunt_artifacts(tmp_path) == [".cursor/rules/bug-hunt.mdc"]


def test_utf16_hooks_json_is_not_counted_as_installed(tmp_path: Path) -> None:
    install_bug_hunt(tmp_path, iterations=4)
    hooks = tmp_path / ".cursor" / "hooks.json"
    hooks.write_text(hooks.read_text(encoding="utf-8"), encoding="utf-16")
    missing = missing_bug_hunt_artifacts(tmp_path)
    assert any(item.startswith(".cursor/hooks.json#stop:") for item in missing)
    plain = hooks.read_text(encoding="utf-16")
    hooks.write_bytes(plain.encode("utf-16-le"))
    missing = missing_bug_hunt_artifacts(tmp_path)
    assert any(item.startswith(".cursor/hooks.json#stop:") for item in missing)
    assert any(item.startswith(".cursor/hooks.json#beforeSubmitPrompt:") for item in missing)


def test_missing_artifacts_reports_prompt_hook_without_stop(tmp_path: Path) -> None:
    import json

    install_bug_hunt(tmp_path, iterations=4)
    hooks_path = tmp_path / ".cursor" / "hooks.json"
    data = json.loads(hooks_path.read_text(encoding="utf-8"))
    data["hooks"].pop("beforeSubmitPrompt", None)
    hooks_path.write_text(json.dumps(data), encoding="utf-8")
    missing = missing_bug_hunt_artifacts(tmp_path)
    assert missing == [
        ".cursor/hooks.json#beforeSubmitPrompt:py -3.11 .cursor/hooks/bug_hunt_continue.py",
    ]


def test_portable_spec_packages_sandbox_detector() -> None:
    spec = Path(__file__).resolve().parents[1] / "packaging" / "hive_planner_portable.spec"
    text = spec.read_text(encoding="utf-8")
    assert 'root / "scripts" / "sandbox_rank_detect.py"' in text
    assert 'pkg / "sandbox_rank_detect.py"' in text
    assert '"hive_planner.sandbox_rank_detect"' in text
    assert '"hive_planner.bug_hunt"' in text
    assert '"hive_planner.bug_hunt_continue"' in text


def test_sandbox_detector_is_importable_from_the_package() -> None:
    from hive_planner import sandbox_rank_detect as packaged
    from hive_planner.bug_hunt import _sandbox_detect

    detect = _sandbox_detect()
    assert detect.findings_for is packaged.findings_for
    scripts = Path(__file__).resolve().parents[1] / "scripts" / "sandbox_rank_detect.py"
    packaged_path = Path(packaged.__file__).resolve()
    assert packaged_path.is_file()
    assert packaged_path.read_bytes() == scripts.read_bytes()


def test_load_detector_from_path_registers_module_for_dataclass(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    from hive_planner.bug_hunt import _load_detector_from_path, _sandbox_detect

    scripts = Path(__file__).resolve().parents[1] / "scripts" / "sandbox_rank_detect.py"
    _sandbox_detect.cache_clear()
    monkeypatch.setitem(sys.modules, "hive_sandbox_rank_detect", None)
    try:
        mod = _load_detector_from_path(scripts)
        assert sys.modules["hive_sandbox_rank_detect"] is mod
        assert callable(mod.findings_for)
        assert callable(mod.python_signals)
    finally:
        _sandbox_detect.cache_clear()


def test_sandbox_detect_falls_back_when_package_import_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    import hive_planner
    from hive_planner.bug_hunt import _sandbox_detect

    _sandbox_detect.cache_clear()
    monkeypatch.delattr(hive_planner, "sandbox_rank_detect", raising=False)
    monkeypatch.setitem(sys.modules, "hive_planner.sandbox_rank_detect", None)
    try:
        detect = _sandbox_detect()
        assert callable(detect.findings_for)
        assert callable(detect.python_signals)
    finally:
        _sandbox_detect.cache_clear()


def test_sandbox_detect_falls_back_when_package_init_raises_typeerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    import hive_planner
    from hive_planner.bug_hunt import _sandbox_detect

    class Boom:
        def __getattr__(self, name: str) -> object:
            raise TypeError("broken detector")

    boom = Boom()
    _sandbox_detect.cache_clear()
    monkeypatch.setattr(hive_planner, "sandbox_rank_detect", boom)
    monkeypatch.setitem(sys.modules, "hive_planner.sandbox_rank_detect", boom)
    try:
        detect = _sandbox_detect()
        assert callable(detect.findings_for)
        assert callable(detect.parse_git_log)
    finally:
        _sandbox_detect.cache_clear()


def test_sandbox_detect_skips_unloadable_candidate_and_loads_next(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    import hive_planner
    from hive_planner.bug_hunt import _sandbox_detect

    broken = tmp_path / "sandbox_rank_detect.py"
    broken.write_text("this is not valid python @@@@\n", encoding="utf-8")
    good = Path(__file__).resolve().parents[1] / "scripts" / "sandbox_rank_detect.py"
    _sandbox_detect.cache_clear()
    monkeypatch.delattr(hive_planner, "sandbox_rank_detect", raising=False)
    monkeypatch.setitem(sys.modules, "hive_planner.sandbox_rank_detect", None)
    monkeypatch.setattr(
        "hive_planner.bug_hunt._detector_file_candidates",
        lambda: [broken, good],
    )
    try:
        detect = _sandbox_detect()
        assert callable(detect.findings_for)
        assert callable(detect.python_signals)
    finally:
        _sandbox_detect.cache_clear()


def test_sandbox_detect_skips_module_missing_parse_git_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    import hive_planner
    from hive_planner.bug_hunt import _sandbox_detect

    stub = tmp_path / "sandbox_rank_detect.py"
    stub.write_text(
        "def findings_for(path, source):\n    return []\n"
        "def python_signals(source, thin):\n    return None\n",
        encoding="utf-8",
    )
    good = Path(__file__).resolve().parents[1] / "scripts" / "sandbox_rank_detect.py"
    _sandbox_detect.cache_clear()
    monkeypatch.delattr(hive_planner, "sandbox_rank_detect", raising=False)
    monkeypatch.setitem(sys.modules, "hive_planner.sandbox_rank_detect", None)
    monkeypatch.setattr(
        "hive_planner.bug_hunt._detector_file_candidates",
        lambda: [stub, good],
    )
    try:
        detect = _sandbox_detect()
        assert callable(detect.parse_git_log)
        assert isinstance(detect.Signals, type)
    finally:
        _sandbox_detect.cache_clear()


def test_sandbox_detect_skips_module_with_non_callable_signals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    import hive_planner
    from hive_planner.bug_hunt import _sandbox_detect

    stub = tmp_path / "sandbox_rank_detect.py"
    stub.write_text(
        "def findings_for(path, source):\n    return []\n"
        "def python_signals(source, thin):\n    return None\n"
        "def parse_git_log(text):\n    return {}, set()\n"
        "def Signals(**kwargs):\n    return None\n",
        encoding="utf-8",
    )
    good = Path(__file__).resolve().parents[1] / "scripts" / "sandbox_rank_detect.py"
    _sandbox_detect.cache_clear()
    monkeypatch.delattr(hive_planner, "sandbox_rank_detect", raising=False)
    monkeypatch.setitem(sys.modules, "hive_planner.sandbox_rank_detect", None)
    monkeypatch.setattr(
        "hive_planner.bug_hunt._detector_file_candidates",
        lambda: [stub, good],
    )
    try:
        detect = _sandbox_detect()
        assert isinstance(detect.Signals, type)
    finally:
        _sandbox_detect.cache_clear()


def test_sandbox_detect_skips_module_missing_findings_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    import hive_planner
    from hive_planner.bug_hunt import _sandbox_detect

    stub = tmp_path / "sandbox_rank_detect.py"
    stub.write_text("x = 1\n", encoding="utf-8")
    good = Path(__file__).resolve().parents[1] / "scripts" / "sandbox_rank_detect.py"
    _sandbox_detect.cache_clear()
    monkeypatch.delattr(hive_planner, "sandbox_rank_detect", raising=False)
    monkeypatch.setitem(sys.modules, "hive_planner.sandbox_rank_detect", None)
    monkeypatch.setattr(
        "hive_planner.bug_hunt._detector_file_candidates",
        lambda: [stub, good],
    )
    try:
        detect = _sandbox_detect()
        assert callable(detect.findings_for)
    finally:
        _sandbox_detect.cache_clear()


def test_sandbox_detect_missing_file_raises_bug_hunt_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    import hive_planner
    from hive_planner.bug_hunt import BugHuntError, _sandbox_detect

    _sandbox_detect.cache_clear()
    monkeypatch.delattr(hive_planner, "sandbox_rank_detect", raising=False)
    monkeypatch.setitem(sys.modules, "hive_planner.sandbox_rank_detect", None)
    monkeypatch.setattr(
        "hive_planner.bug_hunt._detector_file_candidates",
        lambda: [Path("missing-sandbox_rank_detect.py")],
    )
    try:
        with pytest.raises(BugHuntError, match="sandbox detector is missing"):
            _sandbox_detect()
    finally:
        _sandbox_detect.cache_clear()


def test_detector_file_candidates_include_package_and_scripts() -> None:
    from hive_planner.bug_hunt import _detector_file_candidates

    paths = _detector_file_candidates()
    assert paths[0].name == "sandbox_rank_detect.py"
    assert any(path.as_posix().endswith("scripts/sandbox_rank_detect.py") for path in paths)


def test_detector_candidates_ignore_meipass_when_not_frozen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hive_planner.bug_hunt as bh

    fake = tmp_path / "hive_planner" / "sandbox_rank_detect.py"
    fake.parent.mkdir(parents=True)
    fake.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(bh.sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(bh.sys, "frozen", False, raising=False)
    resolved = {path.resolve() for path in bh._detector_file_candidates()}
    assert fake.resolve() not in resolved
    assert bh._detector_path_trusted(tmp_path / "other.py") is False


def test_preview_and_install_accept_str_root(tmp_path: Path) -> None:
    overlay = tmp_path / ".hive" / "bug-hunt" / "repo-overlay.md"
    overlay.parent.mkdir(parents=True)
    overlay.write_text("Run coco_bug_hunt_audit.py after each fix.\n", encoding="utf-8")
    text = preview_agent_prompt(str(tmp_path), 7)
    assert "7 committed fixes is the ceiling" in text
    assert "coco_bug_hunt_audit.py" in text
    result = install_bug_hunt(str(tmp_path), iterations=7)
    assert result.command_path.is_file()
    assert missing_bug_hunt_artifacts(str(tmp_path)) == []


def test_cli_installs_into_workspace_folder(tmp_path: Path) -> None:
    import json

    folder = tmp_path / "app"
    folder.mkdir()
    (folder / "START_HERE.md").write_text("# start\n", encoding="utf-8")
    workspace = tmp_path / "hive.code-workspace"
    workspace.write_text(json.dumps({"folders": [{"path": "app"}]}), encoding="utf-8")
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = main(["--root", str(workspace), "bug-hunt", "--iterations", "5"])
    assert code == 0
    assert (folder / ".cursor" / "commands" / "bug-hunt.md").is_file()
    assert "5 committed fixes is the ceiling" in (folder / ".cursor" / "commands" / "bug-hunt.md").read_text(
        encoding="utf-8"
    )
    out = stdout.getvalue()
    assert str(folder.resolve()) in out
    assert f"Root: {workspace}" not in out


def test_cli_reports_oserror_instead_of_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(_root, **_kwargs):
        raise OSError("Permission denied")

    monkeypatch.setattr("hive_planner.bug_hunt.install_bug_hunt", _boom)
    stderr = io.StringIO()
    stdout = io.StringIO()
    from contextlib import redirect_stderr

    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(["--root", str(tmp_path), "bug-hunt"])
    assert code == 1
    assert "Permission denied" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()
    assert "Traceback" not in stdout.getvalue()


def test_cli_installs_into_root(tmp_path: Path) -> None:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = main(["--root", str(tmp_path), "bug-hunt", "--iterations", "12"])
    assert code == 0
    text = (tmp_path / ".cursor" / "commands" / "bug-hunt.md").read_text(encoding="utf-8")
    assert "12 committed fixes is the ceiling" in text
    assert "command" in stdout.getvalue()


def _git(repo: Path, *args: str) -> str:
    import subprocess

    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout


def _git_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "hunt@example.com")
    _git(tmp_path, "config", "user.name", "Hunt")
    _git(tmp_path, "config", "core.autocrlf", "false")
    return tmp_path


def test_commit_isolated_fix_keeps_unrelated_lines_out_of_the_commit(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    target = repo / "src" / "app.py"
    target.parent.mkdir()
    target.write_bytes(b"alpha\nbeta\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-m", "base")
    before = b"alpha dirty\nbeta\n"
    target.write_bytes(before)
    snapshot = repo / "snapshot.txt"
    snapshot.write_bytes(before)
    target.write_bytes(b"alpha dirty\nbeta fix\n")
    (repo / "notes.txt").write_bytes(b"leave me\n")
    _git(repo, "add", "notes.txt")
    result = commit_isolated_fix(repo, message="Fix beta", snapshots={"src/app.py": snapshot})
    assert result["ok"] is True
    assert _git(repo, "show", "HEAD:src/app.py") == "alpha\nbeta fix\n"
    assert target.read_bytes() == b"alpha dirty\nbeta fix\n"
    assert (repo / "notes.txt").read_bytes() == b"leave me\n"
    names = _git(repo, "show", "--name-only", "--format=", "HEAD")
    assert "src/app.py" in names
    assert "notes.txt" not in names
    staged = _git(repo, "diff", "--cached", "--name-only")
    assert "notes.txt" in staged
    assert "src/app.py" not in staged


def test_commit_isolated_fix_refuses_an_overlapping_edit(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    target = repo / "app.py"
    target.write_bytes(b"alpha\n")
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-m", "base")
    before = b"alpha dirty\n"
    target.write_bytes(before)
    snapshot = repo / "snapshot.txt"
    snapshot.write_bytes(before)
    target.write_bytes(b"ALPHA dirty\n")
    result = commit_isolated_fix(repo, message="Fix alpha", snapshots={"app.py": snapshot})
    assert result["ok"] is False
    assert "could not be separated" in result["error"]
    assert target.read_bytes() == b"ALPHA dirty\n"
    assert _git(repo, "log", "-1", "--format=%s") == "base\n"


def test_commit_isolated_fix_ignores_crlf_in_the_working_tree(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    target = repo / "app.py"
    target.write_bytes(b"alpha\nbeta\n")
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-m", "base")
    before = b"alpha dirty\r\nbeta\r\n"
    target.write_bytes(before)
    snapshot = repo / "snapshot.txt"
    snapshot.write_bytes(before)
    after = b"alpha dirty\r\nbeta fix\r\n"
    target.write_bytes(after)
    result = commit_isolated_fix(repo, message="Fix beta", snapshots={"app.py": snapshot})
    assert result["ok"] is True
    assert _git(repo, "show", "HEAD:app.py") == "alpha\nbeta fix\n"
    assert target.read_bytes() == after


def test_commit_isolated_fix_keeps_both_files_when_two_commits_overlap(
    tmp_path: Path,
) -> None:
    import threading

    repo = _git_repo(tmp_path)
    for name in ("a.py", "b.py"):
        path = repo / name
        path.write_bytes(b"one\n")
        _git(repo, "add", name)
    _git(repo, "commit", "-m", "base")
    errors: list[str] = []

    def fix(name: str, line: bytes) -> None:
        path = repo / name
        before = path.read_bytes()
        snapshot = repo / f"{name}.before"
        snapshot.write_bytes(before)
        path.write_bytes(before + line)
        result = commit_isolated_fix(repo, message=f"Fix {name}", snapshots={name: snapshot})
        if not result["ok"]:
            errors.append(result["error"])

    first = threading.Thread(target=fix, args=("a.py", b"fix-a\n"))
    second = threading.Thread(target=fix, args=("b.py", b"fix-b\n"))
    first.start()
    second.start()
    first.join()
    second.join()
    assert errors == []
    assert _git(repo, "show", "HEAD:a.py") == "one\nfix-a\n"
    assert _git(repo, "show", "HEAD:b.py") == "one\nfix-b\n"


def test_index_cleanup_failure_still_reports_the_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _git_repo(tmp_path)
    target = repo / "app.py"
    target.write_bytes(b"alpha\n")
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-m", "base")
    before = b"alpha\n"
    snapshot = repo / "snapshot.txt"
    snapshot.write_bytes(before)
    target.write_bytes(b"alpha fix\n")
    real_unlink = Path.unlink

    def unlink(self: Path, missing_ok: bool = False) -> None:
        if self.name.startswith("hive-bug-hunt-index-"):
            raise OSError("busy")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink)
    result = commit_isolated_fix(repo, message="Fix alpha", snapshots={"app.py": snapshot})
    assert result["ok"] is True
    assert _git(repo, "log", "-1", "--format=%s") == "Fix alpha\n"

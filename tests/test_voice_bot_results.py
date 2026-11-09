"""T011 — evidence-backed spoken summaries and full written results; R8 test-state mapping (SC-013).

Test status comes from the task's evidence record file, which the runner writes at completion
from the tool-call evidence the provider streamed. Spoken claims are checked against that status.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.voice_task import (
    build_spoken_summary,
    evidence_record_path,
)
from hive_planner.voice_task import tests_status_for_task as read_test_status
from hive_planner.voice_task import tests_status_from_record as map_test_status
from voice_turn_support import make_repo, make_runner, wait_for, wait_task_state, wait_task_terminal


@pytest.fixture
def repo(tmp_path: Path):
    return make_repo(tmp_path)


@pytest.fixture
def runner(repo):
    r = make_runner(repo)
    yield r
    r.close()


# -- R8 mapping, unit over the four states -----------------------------------


def test_r8_missing_or_unparsable_record_is_unknown_never_not_run():
    assert map_test_status(None) == "unknown"
    assert map_test_status("not a dict") == "unknown"
    assert map_test_status({}) == "unknown"  # no test_commands list
    assert map_test_status({"test_commands": "pytest"}) == "unknown"


def test_r8_present_record_without_test_commands_is_not_run():
    assert map_test_status({"test_commands": []}) == "not_run"


def test_r8_passed_failed_and_missing_exit_code():
    assert map_test_status({"test_commands": [{"command": "pytest", "exit_code": 0}]}) == "passed"
    assert map_test_status({"test_commands": [{"command": "pytest", "exit_code": 1}]}) == "failed"
    mixed = {"test_commands": [{"command": "a", "exit_code": 0}, {"command": "b", "exit_code": 2}]}
    assert map_test_status(mixed) == "failed"
    assert map_test_status({"test_commands": [{"command": "pytest"}]}) == "unknown"


def test_r8_missing_record_file_maps_to_unknown(repo):
    assert read_test_status(repo, "task_missing") == "unknown"


# -- integrated: real runs through the protocol ------------------------------


def test_passing_tests_are_spoken_as_passed(runner):
    out = runner.submit("RUN_TESTS_PASS", client_request_id="t-pass")
    assert wait_task_terminal(runner, out["task_id"]) == "completed"
    task = runner.state.coding_tasks[out["task_id"]]
    assert task.evidence.tests_status == "passed"
    assert task.evidence.spoken_update.startswith("Tests passed.")


def test_failing_tests_are_spoken_as_failed(runner):
    out = runner.submit("RUN_TESTS_FAIL", client_request_id="t-fail")
    assert wait_task_terminal(runner, out["task_id"]) == "completed"
    task = runner.state.coding_tasks[out["task_id"]]
    assert task.evidence.tests_status == "failed"
    assert task.evidence.spoken_update.startswith("Tests failed.")


def test_non_test_command_does_not_claim_tests_passed(runner):
    out = runner.submit("RUN_LINT", client_request_id="t-lint")
    assert wait_task_terminal(runner, out["task_id"]) == "completed"
    task = runner.state.coding_tasks[out["task_id"]]
    assert task.evidence.tests_status == "not_run"
    assert "Tests were not run." in task.evidence.spoken_update
    assert "passed" not in task.evidence.spoken_update.lower()  # Story 4, SC-005


def test_spoken_and_written_results_differ_and_share_one_record(runner):
    out = runner.submit("RUN_TESTS_PASS", client_request_id="t-both")
    wait_task_terminal(runner, out["task_id"])
    task = runner.state.coding_tasks[out["task_id"]]
    assert task.evidence.written_result.strip() == "ran tests, exit 0"
    assert task.evidence.spoken_update != task.evidence.written_result  # SC-008
    record = json.loads(evidence_record_path(runner.paths, out["task_id"]).read_text(encoding="utf-8"))
    assert record["test_commands"] == [{"command": "pytest -q", "exit_code": 0}]


def test_sc013_every_completed_task_spoken_claim_matches_its_test_state(runner):
    cases = {
        "RUN_TESTS_PASS": "passed",
        "RUN_TESTS_FAIL": "failed",
        "RUN_LINT": "not_run",
        "plain question": "not_run",
    }
    seen: dict[str, str] = {}
    for n, (prompt, expected) in enumerate(cases.items()):
        out = runner.submit(prompt, client_request_id=f"sc13-{n}")
        assert wait_task_terminal(runner, out["task_id"]) == "completed"
        task = runner.state.coding_tasks[out["task_id"]]
        assert task.evidence.tests_status == expected
        assert read_test_status(runner.paths, out["task_id"]) == expected
        seen[prompt] = task.evidence.spoken_update
    assert seen["RUN_TESTS_PASS"].startswith("Tests passed.")
    assert seen["RUN_TESTS_FAIL"].startswith("Tests failed.")
    assert seen["RUN_LINT"].startswith("Tests were not run.")
    assert seen["plain question"].startswith("Tests were not run.")


def test_r14_progress_speech_is_limited_to_one_per_interval(repo):
    """R14: at most one progress update per interval (30 s default). Uses an injected clock."""
    now = [1000.0]
    r = make_runner(repo, clock=lambda: now[0])
    try:
        out = r.submit("CANCEL_ME hold", client_request_id="cad-1")
        wait_task_state(r, out["task_id"], "running")
        # Let the turn's own first chunk pass through the pump before the fake clock takes over.
        assert wait_for(lambda: "working" in r.written_result(out["task_id"]))
        with r._lock:
            task = r.state.coding_tasks[out["task_id"]]
            task.evidence.spoken_update = ""
            r._progress_last.pop(out["task_id"], None)
            spoken: list[float] = []
            for t in (1000.0, 1010.0, 1029.9, 1030.0, 1045.0, 1061.0):
                now[0] = t
                task.evidence.spoken_update = ""  # same text each time: clear to see each speech
                r._maybe_progress_speech(task)
                if task.evidence.spoken_update:
                    spoken.append(t)
        assert spoken == [1000.0, 1030.0, 1061.0]  # first, then each full 30 s interval
        r.cancel(out["task_id"])
        wait_task_terminal(r, out["task_id"])
    finally:
        r.close()


def test_missing_record_after_completion_is_unknown_and_spoken_as_unknown(runner):
    out = runner.submit("RUN_TESTS_PASS", client_request_id="t-gone")
    wait_task_terminal(runner, out["task_id"])
    evidence_record_path(runner.paths, out["task_id"]).unlink()
    assert read_test_status(runner.paths, out["task_id"]) == "unknown"
    assert build_spoken_summary("completed", "end_turn", "unknown", 300).startswith("Test status is unknown.")


def test_spoken_update_cap_keeps_the_test_claim(repo):
    cfg_dir = repo.root / ".hive" / "voice-bot"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.json").write_text(json.dumps({"spoken_update_max_chars": 20}), encoding="utf-8")
    r = make_runner(repo)
    try:
        out = r.submit("RUN_TESTS_FAIL", client_request_id="t-cap")
        wait_task_terminal(r, out["task_id"])
        spoken = r.state.coding_tasks[out["task_id"]].evidence.spoken_update
        # "Tests failed. Task completed." is 29 characters, so the 20-character cap must truncate it.
        assert len(spoken) == 20 and spoken.endswith("...")
        assert spoken.startswith("Tests failed.")  # the test claim survives truncation
        assert "exit 1" in r.state.coding_tasks[out["task_id"]].evidence.written_result
    finally:
        r.close()

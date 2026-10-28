from hive_planner.bug_hunt import is_bug_hunt_request


def test_enabled_questions_do_not_start_a_bug_hunt() -> None:
    assert not is_bug_hunt_request("is the bug hunt enabled")
    assert not is_bug_hunt_request("whether the bug hunt is installed")
    assert is_bug_hunt_request("start a bug hunt")
    assert is_bug_hunt_request("bug hunt")

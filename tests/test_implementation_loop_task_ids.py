"""Task-id parsing for PersonaPlex-style bold ids and parent (container) checkboxes."""

from __future__ import annotations

from hive_planner.implementation_loop import (
    _first_open_task,
    _leading_task_id,
    _open_task_for_current,
    _task_token_matches,
    parse_result_entries,
    _entry_task_matches,
)


def test_leading_task_id_handles_t_and_bold_prefixed_ids() -> None:
    assert _leading_task_id("T001 do the thing") == "T001"
    assert _leading_task_id("T0010 longer") == "T0010"
    assert _leading_task_id("**PP-T12** Architecture delta") == "PP-T12"
    assert _leading_task_id("PP-T10a Port QLinear") == "PP-T10a"
    assert _leading_task_id("Tests run first") == ""
    assert _leading_task_id("Phase-2 notes") == ""


def test_bold_task_ids_are_recognized_and_match_result_entries() -> None:
    text = "# tasks\n\n- [ ] **PP-T12** Architecture delta + port\n- [ ] **PP-T3** RAG context\n"
    task_id, _heading, body = _first_open_task(text)
    assert task_id == "PP-T12"
    assert body.startswith("**PP-T12**")

    entries = parse_result_entries("- task: PP-T12\n  role: coder\n  outcome: pass\n")
    assert _entry_task_matches(entries[0], body) is True
    assert _entry_task_matches(entries[0], "**PP-T3** RAG context") is False


def test_task_id_prefix_is_not_a_match() -> None:
    assert _task_token_matches("T0010 longer", "T001", "T001 short") is False
    assert _task_token_matches("**PP-T10** parent", "PP-T10a", "PP-T10a child") is False


def test_parent_checkbox_with_open_children_is_not_a_task() -> None:
    text = (
        "# tasks\n\n## Agent navigation\n\n"
        "- [ ] **PP-T10** Proper quantization (parent)\n"
        "  - [ ] **PP-T10a** Port QLinear\n"
        "  - [ ] **PP-T10b** Local export\n"
        "- [ ] **PP-T3** RAG context\n"
    )
    task_id, _heading, body = _first_open_task(text)
    assert task_id == "PP-T10a"
    assert body.startswith("**PP-T10a**")


def test_childless_checkbox_is_still_a_task() -> None:
    text = "# tasks\n\n- [ ] **PP-T7** Test file\n- [ ] **PP-T8** Step-in\n"
    assert _first_open_task(text)[0] == "PP-T7"


def test_current_task_lookup_skips_parent_and_matches_child() -> None:
    text = (
        "# tasks\n\n- [ ] **PP-T10** parent\n  - [ ] **PP-T10a** child\n"
    )
    # The current task is stored as the full body string (as coordinator_start does).
    child_body = "**PP-T10a** child"
    task_id, _heading, body = _open_task_for_current(text, child_body, action="handoff")
    assert task_id == "PP-T10a"
    assert body == child_body

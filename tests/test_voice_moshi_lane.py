"""Moshi tool lane: parse Moshi text into proposals. Never executes; never reads final transcripts."""

from __future__ import annotations

import pytest

from hive_planner.voice_moshi import MoshiConversation
from hive_planner.voice_moshi_lane import ToolLaneError, parse_tool_proposal


def test_read_only_tool_needs_no_approval() -> None:
    p = parse_tool_proposal('TOOL: task_status {"task_id": "t1"}')
    assert (p.tool, p.args, p.requires_approval, p.status) == ("task_status", {"task_id": "t1"}, False, "proposed")


def test_write_tool_requires_approval_and_is_not_executed() -> None:
    p = parse_tool_proposal('TOOL: submit_coding_task {"instruction": "add a test", "mode": "ask"}')
    assert p.requires_approval is True
    assert p.status == "proposed"


def test_unknown_tool_is_refused() -> None:
    with pytest.raises(ToolLaneError, match="unknown_tool"):
        parse_tool_proposal('TOOL: run_shell {"cmd": "rm -rf ."}')


def test_no_tool_line_is_refused() -> None:
    with pytest.raises(ToolLaneError, match="no_tool_line"):
        parse_tool_proposal("just talking about the code")


def test_two_tool_lines_are_ambiguous() -> None:
    text = 'TOOL: task_status {"task_id": "a"}\nTOOL: task_diff {"task_id": "b"}'
    with pytest.raises(ToolLaneError, match="ambiguous_tool_line"):
        parse_tool_proposal(text)


def test_non_json_and_non_object_args_are_refused() -> None:
    with pytest.raises(ToolLaneError, match="args_not_json"):
        parse_tool_proposal("TOOL: task_status {task_id: a}")
    with pytest.raises(ToolLaneError, match="no_tool_line"):
        parse_tool_proposal("TOOL: task_status [1, 2]")


def test_oversized_args_are_refused() -> None:
    big = '{"instruction": "' + "x" * 4_100 + '"}'
    with pytest.raises(ToolLaneError, match="args_too_long"):
        parse_tool_proposal(f"TOOL: submit_coding_task {big}")


class _FakeSession:
    def __init__(self) -> None:
        self.sent: list[bytes] = []

    def send_audio(self, opus: bytes) -> None:
        self.sent.append(opus)


def test_moshi_text_frames_stay_transcript_only_and_do_not_submit() -> None:
    """Separation check: a TOOL line in Moshi text is kept as transcript and never sent as audio or a task."""
    conv = MoshiConversation(_FakeSession())
    assert conv.handle_frame(0x02, b'TOOL: submit_coding_task {"instruction": "x"}') is None
    assert conv.transcript == ['TOOL: submit_coding_task {"instruction": "x"}']
    assert conv._session.sent == []

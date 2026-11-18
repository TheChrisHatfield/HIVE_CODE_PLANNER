from __future__ import annotations

import re
from pathlib import Path

SRC = (
    Path(__file__).resolve().parents[1]
    / "code-improvements"
    / "unity-mcp"
    / "MCPForUnity"
    / "Editor"
    / "Services"
    / "EditorStateCache.cs"
)


def _source() -> str:
    return SRC.read_text(encoding="utf-8")


def test_play_mode_transition_is_xor_not_or_will_change():
    text = _source()
    match = re.search(
        r"internal static bool IsPlayModeTransition\(bool isPlaying, bool isPlayingOrWillChangePlaymode\)\s*\{\s*return ([^;]+);",
        text,
    )
    assert match is not None
    assert match.group(1).strip() == "isPlayingOrWillChangePlaymode != isPlaying"
    assert text.count("IsPlayModeTransition(") >= 4
    assert 'activityPhase = "playmode_transition"' in text
    lone = re.findall(
        r"else if \(EditorApplication\.isPlayingOrWillChangePlaymode\)",
        text,
    )
    assert lone == []
    assert "IsChanging = EditorApplication.isPlayingOrWillChangePlaymode" not in text


def test_play_mode_transition_truth_table():
    def is_transition(is_playing: bool, or_will: bool) -> bool:
        return or_will != is_playing

    assert is_transition(False, True) is True
    assert is_transition(True, True) is False
    assert is_transition(False, False) is False
    assert is_transition(True, False) is True

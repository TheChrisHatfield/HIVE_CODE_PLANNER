from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = (
    ROOT / "src" / "hive_planner" / "vendor_templates" / "continual-learning" / "hooks" / "continual-learning-stop.py",
    ROOT / ".cursor" / "plugins" / "hive-continual-learning" / "hooks" / "continual-learning-stop.py",
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_utf16_transcript_still_suppresses_the_memory_notice(tmp_path: Path) -> None:
    transcript = tmp_path / "chat.jsonl"
    transcript.write_text(
        '{"role":"user","message":{"content":"bug hunt"}}\n',
        encoding="utf-16",
    )
    for index, path in enumerate(HOOKS):
        module = _load(path, f"cl_stop_{index}")
        assert module._bug_hunt_in_transcript(str(transcript)) is True


def test_plugin_utf16_le_transcript_without_a_bom_still_suppresses_the_notice(tmp_path: Path) -> None:
    transcript = tmp_path / "chat.jsonl"
    transcript.write_bytes(
        '{"role":"user","message":{"content":"bug hunt"}}\n'.encode("utf-16-le")
    )
    module = _load(HOOKS[1], "cl_stop_plugin_le")
    assert module._bug_hunt_in_transcript(str(transcript)) is True


def test_vendor_utf16_le_transcript_without_a_bom_still_suppresses_the_notice(tmp_path: Path) -> None:
    transcript = tmp_path / "chat.jsonl"
    transcript.write_bytes(
        '{"role":"user","message":{"content":"bug hunt"}}\n'.encode("utf-16-le")
    )
    module = _load(HOOKS[0], "cl_stop_vendor_le")
    assert module._bug_hunt_in_transcript(str(transcript)) is True


def test_utf16_le_state_keeps_turn_count(tmp_path: Path, monkeypatch) -> None:
    state_path = tmp_path / "continual-learning.json"
    payload = {
        "version": 1,
        "lastRunAtMs": 1,
        "turnsSinceLastRun": 7,
        "lastTranscriptMtimeMs": None,
        "lastProcessedGenerationId": None,
        "trialStartedAtMs": None,
    }
    state_path.write_bytes(json.dumps(payload).encode("utf-16-le"))
    module = _load(HOOKS[0], "cl_stop_state_le")
    monkeypatch.setattr(module, "STATE_PATH", state_path)
    loaded = module._load_state()
    assert loaded["turnsSinceLastRun"] == 7


def test_cursor_plugins_vendor_utf16_le_state_keeps_turn_count(tmp_path: Path, monkeypatch) -> None:
    """vendor/cursor-plugins stop hook must keep turn count from UTF-16-LE state."""
    state_path = tmp_path / "continual-learning.json"
    payload = {
        "version": 1,
        "lastRunAtMs": 1,
        "turnsSinceLastRun": 7,
        "lastTranscriptMtimeMs": None,
        "lastProcessedGenerationId": None,
        "trialStartedAtMs": None,
    }
    state_path.write_bytes(json.dumps(payload).encode("utf-16-le"))
    hook = (
        ROOT
        / "vendor"
        / "cursor-plugins"
        / "continual-learning"
        / "hooks"
        / "continual-learning-stop.py"
    )
    module = _load(hook, "cl_stop_cursor_plugins_state_le")
    monkeypatch.setattr(module, "STATE_PATH", state_path)
    loaded = module._load_state()
    assert loaded["turnsSinceLastRun"] == 7


def test_undecodable_transcript_does_not_raise(tmp_path: Path) -> None:
    transcript = tmp_path / "chat.jsonl"
    raw = bytearray(b'{"role":"user","message":{"content":"bug hunt"}}\n')
    raw[2] = 0xE9
    transcript.write_bytes(bytes(raw))
    module = _load(HOOKS[0], "cl_stop_vendor")
    assert module._bug_hunt_in_transcript(str(transcript)) is False

from __future__ import annotations

import importlib.util
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


def test_undecodable_transcript_does_not_raise(tmp_path: Path) -> None:
    transcript = tmp_path / "chat.jsonl"
    raw = bytearray(b'{"role":"user","message":{"content":"bug hunt"}}\n')
    raw[2] = 0xE9
    transcript.write_bytes(bytes(raw))
    module = _load(HOOKS[0], "cl_stop_vendor")
    assert module._bug_hunt_in_transcript(str(transcript)) is False

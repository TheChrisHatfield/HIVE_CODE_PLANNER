"""Settings microphone device field: `input_device` read from .hive/voice-bot/config.json.

Mirrors the `stt_provider` read site in tests/test_voice_stt.py. Test only; no UI.
"""

from __future__ import annotations

import json
from pathlib import Path

from hive_planner.config import RepoPaths
from hive_planner.voice_bot import (
    VoiceBotConfig,
    load_voice_bot_config,
    save_voice_bot_config,
    voice_bot_config_path,
)


def _write_config(root: Path, data: dict) -> RepoPaths:
    paths = RepoPaths(root=root)
    cfg = voice_bot_config_path(paths)
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(data), encoding="utf-8")
    return paths


def test_input_device_defaults_to_null(tmp_path: Path):
    paths = RepoPaths(root=tmp_path)
    assert load_voice_bot_config(paths).input_device is None


def test_input_device_is_read_from_config_json(tmp_path: Path):
    paths = _write_config(tmp_path, {"input_device": "Microphone (USB Audio)"})
    cfg = load_voice_bot_config(paths)
    assert cfg.input_device == "Microphone (USB Audio)"


def test_input_device_round_trips_through_save_and_load(tmp_path: Path):
    paths = RepoPaths(root=tmp_path)
    save_voice_bot_config(paths, VoiceBotConfig(input_device="Microphone (USB Audio)"))
    stored = json.loads(voice_bot_config_path(paths).read_text(encoding="utf-8"))
    assert stored["input_device"] == "Microphone (USB Audio)"
    assert load_voice_bot_config(paths).input_device == "Microphone (USB Audio)"


def test_input_device_from_dict_round_trips(tmp_path: Path):
    cfg = VoiceBotConfig.from_dict({"input_device": "Headset Mic"})
    assert cfg.input_device == "Headset Mic"
    assert VoiceBotConfig.from_dict({}).input_device is None

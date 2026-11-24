"""Tests for the voice_bot config object (T001a, R21 limits, R24 budgets)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hive_planner.config import RepoPaths
from hive_planner.voice_bot import (
    ContextSnapshot,
    PERSONAPLEX_KEYS,
    VoiceBotConfig,
    VoiceBotError,
    create_context_snapshot,
    init_voice_session,
    load_state,
    load_voice_bot_config,
    validate_context_snapshot,
    voice_bot_config_path,
)


@pytest.fixture
def repo(tmp_path: Path) -> RepoPaths:
    return RepoPaths(root=tmp_path)


def _snap(instruction: str = "explain", selection: str = "x") -> ContextSnapshot:
    return ContextSnapshot(
        workspace_root="/ws",
        file_path="src/a.py",
        selection_text=selection,
        document_version=1,
        dirty=False,
        instruction=instruction,
    )


def test_defaults_match_r21_provisional_limits() -> None:
    cfg = VoiceBotConfig()
    assert cfg.instruction_max_chars == 4_000
    assert cfg.snapshot_max_bytes == 64 * 1024
    assert cfg.approval_timeout_s == 120
    assert cfg.queue_depth == 5
    assert cfg.spoken_update_max_chars == 300
    assert cfg.diff_max_bytes == 256 * 1024
    assert cfg.progress_interval_s == 30
    assert cfg.reconnect_window_s == 300
    assert cfg.edits_enabled is False


def test_r24_latency_targets_default_to_measured_ceiling() -> None:
    cfg = VoiceBotConfig()
    assert cfg.latency_target_ms == 8_000
    assert cfg.first_spoken_update_target_ms == 8_000


def test_r24_targets_can_be_unset_explicitly() -> None:
    cfg = VoiceBotConfig.from_dict({"latency_target_ms": None, "first_spoken_update_target_ms": None})
    assert cfg.latency_target_ms is None
    assert cfg.first_spoken_update_target_ms is None


def test_missing_config_file_loads_defaults(repo: RepoPaths) -> None:
    assert not voice_bot_config_path(repo).exists()
    assert load_voice_bot_config(repo) == VoiceBotConfig()


def test_config_file_overrides_only_listed_keys(repo: RepoPaths) -> None:
    path = voice_bot_config_path(repo)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"queue_depth": 2}), encoding="utf-8")
    cfg = load_voice_bot_config(repo)
    assert cfg.queue_depth == 2
    assert cfg.approval_timeout_s == 120


@pytest.mark.parametrize(
    "payload",
    [
        {"not_a_limit": 1},
        {"queue_depth": 0},
        {"queue_depth": -3},
        {"queue_depth": "5"},
        {"queue_depth": True},
        {"latency_target_ms": 0},
    ],
)
def test_invalid_config_is_rejected(repo: RepoPaths, payload: dict) -> None:
    path = voice_bot_config_path(repo)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(VoiceBotError):
        load_voice_bot_config(repo)


def test_instruction_limit_is_read_from_config() -> None:
    text = "a" * 10
    validate_context_snapshot(_snap(instruction=text))  # default 4,000 accepts
    with pytest.raises(VoiceBotError, match="instruction exceeds"):
        validate_context_snapshot(_snap(instruction=text), VoiceBotConfig(instruction_max_chars=5))


def test_selection_limit_is_read_from_config_in_bytes() -> None:
    selection = "é" * 10  # 20 bytes, 10 characters
    validate_context_snapshot(_snap(selection=selection), VoiceBotConfig(snapshot_max_bytes=20))
    with pytest.raises(VoiceBotError, match="selection_text exceeds"):
        validate_context_snapshot(_snap(selection=selection), VoiceBotConfig(snapshot_max_bytes=19))


def test_file_content_limit_is_read_from_config_in_bytes() -> None:
    snap = _snap()
    snap.file_content = "é" * 10  # 20 bytes, 10 characters
    validate_context_snapshot(snap, VoiceBotConfig(snapshot_max_bytes=20))
    with pytest.raises(VoiceBotError, match="file_content exceeds"):
        validate_context_snapshot(snap, VoiceBotConfig(snapshot_max_bytes=19))


def test_default_snapshot_limit_is_64kb(repo: RepoPaths) -> None:
    state = init_voice_session(repo, "Voice_Bot")
    at_limit = _snap(selection="a" * (64 * 1024))
    create_context_snapshot(repo, state, at_limit)
    over = _snap(selection="a" * (64 * 1024 + 1))
    stored = create_context_snapshot(repo, load_state(repo), over)
    assert stored.truncated is True
    assert len(stored.selection_text.encode("utf-8")) == 64 * 1024


def test_snapshot_path_honors_config_file(repo: RepoPaths) -> None:
    """Integrated path: the config file, not a code default, decides acceptance."""
    state = init_voice_session(repo, "Voice_Bot")
    path = voice_bot_config_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"instruction_max_chars": 3}), encoding="utf-8")
    with pytest.raises(VoiceBotError, match="instruction exceeds"):
        create_context_snapshot(repo, state, _snap(instruction="four"))
    assert load_state(repo).context_snapshots == {}


def test_pp_t8_speech_child_and_personaplex_keys() -> None:
    assert VoiceBotConfig().speech_child == "moshi_q8"
    with pytest.raises(VoiceBotError, match="speech_child"):
        VoiceBotConfig.from_dict({"speech_child": "other"})
    with pytest.raises(VoiceBotError, match="personaplex_weights"):
        VoiceBotConfig.from_dict({"personaplex_weights": "C:/w.safetensors"})
    assert PERSONAPLEX_KEYS[0] == "personaplex_weights"

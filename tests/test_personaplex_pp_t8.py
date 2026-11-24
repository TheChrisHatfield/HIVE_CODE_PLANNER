"""PP-T8: speech_child discriminator, PERSONAPLEX keys, NVIDIA argv, query URL."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from hive_planner.voice_bot import PERSONAPLEX_KEYS, VoiceBotConfig, VoiceBotError
from hive_planner.voice_bot import speech_adapter
from hive_planner.voice_moshi import CONNECT_TIMEOUT_S
from hive_planner.voice_moshi_server import (
    moshi_child_env,
    moshi_session_url,
    personaplex_handshake_url,
    personaplex_server_command,
    q8_server_command,
)


def test_pp_t8_default_speech_child_is_moshi_q8():
    assert VoiceBotConfig().speech_child == "moshi_q8"


def test_pp_t8_unknown_speech_child_refused():
    with pytest.raises(VoiceBotError, match="speech_child"):
        VoiceBotConfig(speech_child="moshika")


def test_pp_t8_personaplex_keys_all_or_nothing():
    with pytest.raises(VoiceBotError, match="personaplex_weights"):
        VoiceBotConfig(personaplex_weights="C:/w.safetensors")


def test_pp_t8_personaplex_requires_src_and_keys():
    with pytest.raises(VoiceBotError, match="personaplex_src"):
        VoiceBotConfig(
            speech_child="personaplex",
            personaplex_weights="C:/w.safetensors",
            personaplex_mimi="C:/m.safetensors",
            personaplex_tokenizer="C:/t.model",
        )


def test_pp_t8_query_url_has_prompt_keys():
    cfg = VoiceBotConfig(
        speech_child="personaplex",
        personaplex_src="C:/src",
        personaplex_weights="C:/w.safetensors",
        personaplex_mimi="C:/m.safetensors",
        personaplex_tokenizer="C:/t.model",
        personaplex_text_prompt="hello",
        personaplex_voice_prompt="D:/voices/a.wav",
    )
    url = personaplex_handshake_url("ws://127.0.0.1:8998/api/chat", cfg)
    assert "text_prompt=hello" in url
    assert "voice_prompt=a.wav" in url
    assert "D:" not in url.split("?")[-1]


def test_pp_t8_argv_is_nvidia_not_q8(tmp_path: Path):
    src = tmp_path / "moshi"
    src.mkdir()
    cfg = VoiceBotConfig(
        speech_child="personaplex",
        personaplex_src=str(src),
        personaplex_weights=str(tmp_path / "w.safetensors"),
        personaplex_mimi=str(tmp_path / "m.safetensors"),
        personaplex_tokenizer=str(tmp_path / "t.model"),
        personaplex_voice_prompt=str(tmp_path / "voices" / "n.wav"),
    )
    cmd = personaplex_server_command("ws://127.0.0.1:8998/api/chat", cfg)
    joined = " ".join(cmd)
    assert "personaplex_server.py" in joined
    assert "--moshi-weight" in cmd
    assert "--q8" not in cmd
    assert "--config" not in cmd
    assert "--max-reference-tokens" not in cmd
    assert "--voice-prompt-dir" in cmd
    assert str(tmp_path / "voices") in cmd


def test_pp_t8_q8_command_unchanged_when_q8_keys_set(tmp_path: Path):
    cfg = VoiceBotConfig(
        speech_child="moshi_q8",
        moshi_q8_weights="C:/q8/model.q8.safetensors",
        moshi_mimi_weights="C:/bf16/tokenizer.safetensors",
        moshi_tokenizer="C:/bf16/tokenizer.model",
        moshi_model_config="C:/q8/config.local.json",
    )
    cmd = q8_server_command("ws://127.0.0.1:8998/api/chat", cfg)
    assert "moshi_q8_server.py" in " ".join(cmd)
    assert "personaplex_server.py" not in " ".join(cmd)


def test_pp_t8_pythonpath_overlay(tmp_path: Path):
    src = tmp_path / "personaplex-migrate" / "moshi"
    src.mkdir(parents=True)
    cfg = VoiceBotConfig(
        speech_child="personaplex",
        personaplex_src=str(src),
        personaplex_weights=str(tmp_path / "w.safetensors"),
        personaplex_mimi=str(tmp_path / "m.safetensors"),
        personaplex_tokenizer=str(tmp_path / "t.model"),
        moshi_rag_env={"PYTHONPATH": str(tmp_path / "moshi-rag-src")},
    )
    env = moshi_child_env({}, cfg)
    assert env["PYTHONPATH"] == str(src)


def test_pp_t8_rag_off_sets_ref_disable(tmp_path: Path):
    src = tmp_path / "moshi"
    src.mkdir()
    cfg = VoiceBotConfig(
        speech_child="personaplex",
        personaplex_src=str(src),
        personaplex_weights=str(tmp_path / "w.safetensors"),
        personaplex_mimi=str(tmp_path / "m.safetensors"),
        personaplex_tokenizer=str(tmp_path / "t.model"),
        retrieval_enabled=False,
    )
    env = moshi_child_env({}, cfg)
    assert env.get("HIVE_REF_DISABLE") == "1"
    assert env.get("HIVE_RETRIEVAL_ENABLED") == "0"


def test_pp_t8_launcher_source_has_no_stt_or_q8_argv():
    text = (Path(__file__).resolve().parents[1] / "scripts" / "personaplex_server.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(text)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    assert "moshi.stt" not in names
    assert "moshi.stt.local_stt" not in names
    assert "install_loop_probe" not in text
    assert "moshi_server_argv" not in text
    assert "CheckpointInfo" not in text
    assert "q8 step" in text or "install_step_counter" in text
    assert "REFERENCE_MAX_TOKENS" in text


def test_pp_t8_personaplex_keys_tuple():
    assert PERSONAPLEX_KEYS == ("personaplex_weights", "personaplex_mimi", "personaplex_tokenizer")


def test_pp_t8_session_url_on_open_and_adapter():
    cfg = VoiceBotConfig(
        speech_child="personaplex",
        personaplex_src="C:/src",
        personaplex_weights="C:/w.safetensors",
        personaplex_mimi="C:/m.safetensors",
        personaplex_tokenizer="C:/t.model",
        personaplex_voice_prompt="D:/voices/n.wav",
        moshi_url="ws://127.0.0.1:8998/api/chat",
    )
    url = moshi_session_url(cfg.moshi_url, cfg)
    assert "voice_prompt=n.wav" in url
    adapter = speech_adapter(cfg)
    assert "voice_prompt=n.wav" in adapter.url
    q8 = VoiceBotConfig(moshi_url="ws://127.0.0.1:8998/api/chat")
    assert moshi_session_url(q8.moshi_url, q8) == q8.moshi_url
    assert CONNECT_TIMEOUT_S == 15.0

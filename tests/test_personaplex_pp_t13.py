"""PP-T13: query seed, skip HF when local argv is complete, empty voice_prompt skip."""

from __future__ import annotations

from pathlib import Path

from hive_planner.voice_bot import VoiceBotConfig
from hive_planner.voice_moshi_server import personaplex_handshake_url

_SERVER = (
    Path(__file__).resolve().parents[1]
    / "code-improvements"
    / "personaplex-migrate"
    / "moshi"
    / "moshi"
    / "server.py"
)


def test_pp_t13_seed_comes_from_query_not_mapping():
    src = _SERVER.read_text(encoding="utf-8")
    assert 'request["seed"]' not in src
    assert "request.query.get(\"seed\")" in src


def test_pp_t13_local_complete_skips_hf_config_voices_and_dist():
    src = _SERVER.read_text(encoding="utf-8")
    assert "local_complete = bool(args.moshi_weight and args.mimi_weight and args.tokenizer)" in src
    assert 'if local_complete and args.static is None:' in src
    assert 'args.static = "none"' in src
    assert "if not local_complete:" in src
    cfg_block = src.split("if not local_complete:", 1)[1].split("logger.info(\"loading mimi\")", 1)[0]
    assert "config.json" in cfg_block
    assert "hf_hub_download" in cfg_block
    assert 'if local_complete and not args.voice_prompt_dir:' in src
    assert "args.voice_prompt_dir = None" in src


def test_pp_t13_empty_voice_prompt_skips_load():
    src = _SERVER.read_text(encoding="utf-8")
    assert 'voice_prompt_filename = request.query.get("voice_prompt")' in src
    assert "if voice_prompt_filename:" in src
    assert 'request.query["voice_prompt"]' not in src
    assert 'request.query.get("voice_prompt")' in src


def test_pp_t13_hive_handshake_always_has_prompt_keys():
    cfg = VoiceBotConfig(
        speech_child="personaplex",
        personaplex_src="C:/src",
        personaplex_weights="C:/w.safetensors",
        personaplex_mimi="C:/m.safetensors",
        personaplex_tokenizer="C:/t.model",
        moshi_url="ws://127.0.0.1:8998/api/chat",
    )
    url = personaplex_handshake_url(cfg.moshi_url, cfg)
    assert "text_prompt=" in url
    assert "voice_prompt=" in url


def test_pp_t13_does_not_add_vite_idle_timeout():
    src = _SERVER.read_text(encoding="utf-8")
    assert "idle" not in src.lower()
    assert "10 second" not in src.lower()
    assert "idle_timeout" not in src

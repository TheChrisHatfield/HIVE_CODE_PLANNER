"""PP-T15: local .pt/wav persona; voice change is a new handshake basename (G182)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from hive_planner.voice_bot import VoiceBotConfig, VoiceBotError
from hive_planner.voice_moshi import moshi_listen_gate
from hive_planner.voice_moshi_server import personaplex_handshake_url

_ROOT = Path(__file__).resolve().parents[1]
_SERVER = _ROOT / "code-improvements" / "personaplex-migrate" / "moshi" / "moshi" / "server.py"
_EXPORT = _ROOT / "code-improvements" / "personaplex-migrate" / "moshi" / "moshi" / "export_voice_pt.py"


def test_pp_t15_server_loads_pt_or_wav_and_has_no_midcall_opcode():
    src = _SERVER.read_text(encoding="utf-8")
    assert "load_voice_prompt_embeddings" in src
    assert "load_voice_prompt(" in src
    assert 'endswith(".pt")' in src.replace("'", '"') or "endswith('.pt')" in src
    assert "kind == 1" in src
    tree = ast.parse(src)
    kinds: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            left = ast.dump(node.left)
            if "kind" in left:
                for cmp_ in node.comparators:
                    if isinstance(cmp_, ast.Constant) and isinstance(cmp_.value, int):
                        kinds.add(cmp_.value)
    assert 1 in kinds
    assert 7 not in kinds  # no mid-call voice opcode


def test_pp_t15_export_helper_refuses_hf_and_missing_local():
    text = _EXPORT.read_text(encoding="utf-8")
    assert "hf_hub_download" not in text
    spec = ast.parse(text)
    names: set[str] = set()
    for node in ast.walk(spec):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".", 1)[0])
    assert "huggingface_hub" not in names
    import importlib.util

    mod_spec = importlib.util.spec_from_file_location("export_voice_pt", _EXPORT)
    assert mod_spec and mod_spec.loader
    mod = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(mod)
    with pytest.raises(SystemExit, match="no HF"):
        mod.require_local_files("", "", "", "")
    assert mod.pt_out_path("C:/voices/a.wav") == "C:/voices/a.pt"


def test_pp_t15_voice_change_is_new_handshake_basename():
    base = dict(
        speech_child="personaplex",
        personaplex_src="C:/src",
        personaplex_weights="C:/w.safetensors",
        personaplex_mimi="C:/m.safetensors",
        personaplex_tokenizer="C:/t.model",
        moshi_url="ws://127.0.0.1:8998/api/chat",
    )
    a = VoiceBotConfig(**base, personaplex_voice_prompt="D:/voices/NATF0.pt")
    b = VoiceBotConfig(**base, personaplex_voice_prompt="D:/voices/NATF1.pt")
    ua = personaplex_handshake_url(a.moshi_url, a)
    ub = personaplex_handshake_url(b.moshi_url, b)
    assert "voice_prompt=NATF0.pt" in ua
    assert "voice_prompt=NATF1.pt" in ub
    assert ua != ub


def test_pp_t15_missing_voice_file_hive_preflight(tmp_path: Path, monkeypatch):
    from hive_planner.voice_moshi_server import MoshiServerProcess
    import hive_planner.voice_moshi as vm

    src = tmp_path / "src"
    src.mkdir()
    for name in ("w.safetensors", "m.safetensors", "t.model"):
        (tmp_path / name).write_bytes(b"x")
    calls: list = []
    server = MoshiServerProcess(popen=lambda cmd, **k: calls.append(cmd) or None, ready_timeout_s=0.2, poll_s=0.05)
    monkeypatch.setattr(vm, "SERVER", server)
    cfg = VoiceBotConfig(
        voice_layer="moshi",
        moshi_url="ws://127.0.0.1:1/api/chat",
        moshi_autostart=True,
        speech_child="personaplex",
        personaplex_src=str(src),
        personaplex_weights=str(tmp_path / "w.safetensors"),
        personaplex_mimi=str(tmp_path / "m.safetensors"),
        personaplex_tokenizer=str(tmp_path / "t.model"),
        personaplex_voice_prompt=str(tmp_path / "missing.pt"),
        retrieval_enabled=False,
    )
    assert moshi_listen_gate(cfg) == "personaplex_voice_prompt_missing"
    assert calls == []
